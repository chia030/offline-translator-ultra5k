#!/usr/bin/env python3
"""da2en — offline Danish -> English gist translator.

Rule-based only: finite word lists + morphology rules + a few word-order
rules. No LLM, no ML, no network at runtime.

Usage:
  ./da2en.py file.md [more files]     # translate files
  ./da2en.py < input.txt              # translate stdin
  ./da2en.py --debug "sætning her"    # show per-token decisions
"""
import json, os, re, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "da2en-data.json")

SUBJECTS = {"jeg": "I", "du": "you", "han": "he", "hun": "she", "vi": "we",
            "de": "they", "man": "one", "det": "it", "den": "it", "dette": "this",
            "det samme": "likewise"}

# definite / inflection suffixes, longest first (no bare -s: that's verbs)
DEF_SUFFIXES = ["erne", "enes", "ene", "ens", "ets", "et", "en"]
V_SUFFIXES = ["eredes", "erede", "edes", "ende", "eres", "eres", "er", "te", "de", "r"]

def load_data():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)

class Translator:
    def __init__(self, data, debug=False):
        self.d = data["dict"]            # da lemma -> en word
        self.pos = data.get("pos", {})   # da lemma -> danish pos
        self.epos = data.get("en_pos", {})  # da lemma -> pos of chosen en word
        self.f2l = data["form2lemma"]    # inflected -> lemma
        self.debug = debug
        self.n_tok = self.n_ok = 0       # coverage counters

    def log(self, tok, how, res):
        if self.debug:
            print(f"    [{tok}] {how} -> {res}", file=sys.stderr)

    def lookup(self, w):
        """Return (en, how) or None. w is lowercase."""
        if w in self.d:
            return self.d[w], "dict"
        lem = self.f2l.get(w)
        if lem and lem in self.d:
            en = self.d[lem]
            how = f"form({lem})"
            if self.nounish(lem) and w.endswith(("en", "et", "ene", "erne")):
                en = "the " + en          # definite form: filen -> the file
            return en, how
        # definite suffix: huset -> hus (+the)
        for suf in DEF_SUFFIXES:
            if w.endswith(suf) and len(w) - len(suf) >= 2:
                stem = w[:-len(suf)]
                for cand in (stem, stem + "e"):
                    lem = cand if cand in self.d else self.f2l.get(cand)
                    if lem and lem in self.d:
                        en = self.d[lem]
                        if self.nounish(lem):
                            en = "the " + en
                        return en, f"def({suf})"
        # noun plural: søgninger -> søgning (when forms map lacks it).
        # restricted to æ/ø/å words so English tokens (cups, files) survive.
        if any(ch in w for ch in "æøå"):
            for suf in ("er", "e", "s"):
                if w.endswith(suf) and len(w) - len(suf) >= 3:
                    stem = w[:-len(suf)]
                    lem = stem if stem in self.d else self.f2l.get(stem)
                    if lem and lem in self.d and self.nounish(lem):
                        return self.d[lem], f"plural({suf})"
        # verb suffix: købe -> købe etc.
        for suf in V_SUFFIXES:
            if w.endswith(suf) and len(w) - len(suf) >= 2:
                stem = w[:-len(suf)]
                for cand in (stem, stem + "e"):
                    if cand in self.d and self.verbish(cand):
                        return self.d[cand], f"verb({suf})"
                    c2 = self.f2l.get(cand)
                    if c2 and self.verbish(c2) and c2 in self.d:
                        return self.d[c2], f"verb({suf})"
        # -s passive: døbes -> is baptised
        if w.endswith("s") and len(w) > 4:
            stem = w[:-1]
            lem = self.f2l.get(stem) or (stem if stem in self.d else None)
            if lem and self.verbish(lem):
                return "is " + self.d[lem], "passive-s"
        # technical cognate: implementering -> implement + ing
        if w.endswith("ering") and len(w) > 7:
            stem = w[:-5]
            for cand in (stem + "ere", stem + "er", stem):
                lem = self.f2l.get(cand) or (cand if cand in self.d else None)
                if lem and self.verbish(lem):
                    return self.d[lem] + "ing", "cognate-ering"
        # compound split (noun+noun only, the productive type); skip linking s/e
        if len(w) >= 8:
            for i in range(3, len(w) - 2):
                left, right = w[:i], w[i:]
                le = self.noun_lookup(left)
                ri = self.noun_lookup(right)
                if not ri and right[:1] in ("s", "e") and len(right) > 4:
                    ri = self.noun_lookup(right[1:])
                if le and ri:
                    return le + "-" + ri, f"compound({left}+{right})"
        return None

    def noun_lookup(self, w):
        """en translation if w resolves to a known noun, else None."""
        for cand in (w,):
            if cand in self.d and self.nounish(cand):
                return self.d[cand]
            lem = self.f2l.get(cand)
            if lem and lem in self.d and self.nounish(lem):
                return self.d[lem]
            for suf in DEF_SUFFIXES:
                if cand.endswith(suf) and len(cand) - len(suf) >= 2:
                    stem = cand[:-len(suf)]
                    for s2 in (stem, stem + "e"):
                        lem = s2 if s2 in self.d else self.f2l.get(s2)
                        if lem and lem in self.d and self.nounish(lem):
                            return self.d[lem]
        return None

    def resolve(self, w):
        return self.lookup(w)

    def verbish(self, lem):
        return self.epos.get(lem) == "verb" or self.pos.get(lem) == "verb"

    def nounish(self, lem):
        return self.epos.get(lem) == "noun" or self.pos.get(lem) == "noun"

    def is_verb(self, w):
        lem = self.f2l.get(w, w)
        return self.verbish(lem)

    def translate_line(self, line):
        # keep leading markdown list/quote markers
        m = re.match(r"^(\s*(?:[-*+]\s+|\d+\.\s+|>+ )?)(.*)$", line)
        prefix, text = m.group(1), m.group(2)
        # protect inline code, urls, autolinks
        protected = []
        def stash(mo):
            protected.append(mo.group(0))
            return f"\x00{len(protected)-1}\x00"
        text = re.sub(r"`[^`]+`|https?://\S+|\[[^\]]*\]\([^)]*\)|<[^>\s]+>", stash, text)
        toks = re.findall(r"[A-Za-zÆØÅæøåÄÖäö0-9_'\u00C0-\u024F-]+|\s+|[^\sA-Za-zÆØÅæøåÄÖäö0-9_'\u00C0-\u024F-]", text)
        out = []
        words_idx = [i for i, t in enumerate(toks)
                     if re.match(r"[A-Za-zÆØÅæøåÄÖäö]", t)]
        words_idx_set = set(words_idx)
        for i, t in enumerate(toks):
            if re.match(r"[A-Za-zÆØÅæøåÄÖäö]", t):
                lw = t.lower()
                self.n_tok += 1
                if lw in SUBJECTS and not t[0].isupper():
                    self.n_ok += 1
                    out.append(SUBJECTS[lw]); self.log(t, "pron", SUBJECTS[lw]); continue
                r = self.lookup(lw)
                if r:
                    self.n_ok += 1
                    en, how = r
                    if t[0].isupper() and en and not en[0].isupper():
                        en = en[0].upper() + en[1:]
                    out.append(en); self.log(t, how, en)
                else:
                    out.append(t)  # unknown: leave as-is
            else:
                out.append(t)
        # word-order fixes, applied per sentence segment
        MODALS = {"skal", "kan", "må", "bør", "vil", "ville", "kunne", "skulle"}
        IDIOMS = {"går": "yesterday", "dag": "today", "morgen": "tomorrow",
                  "aften": "tonight", "formiddag": "this morning",
                  "eftermiddag": "this afternoon", "morgen tidlig": "tomorrow morning"}
        word_seq = [(i, toks[i]) for i in words_idx]
        # split word indices into segments at sentence punctuation
        segs, cur = [], []
        for i, t in enumerate(toks):
            if i in words_idx_set:
                cur.append(i)
            elif t.strip() in (".", "!", "?", ":", ";") and cur:
                segs.append(cur); cur = []
        if cur:
            segs.append(cur)
        for seg in segs:
            lw = [toks[i].lower() for i in seg]
            # multi-word idioms
            PHRASES = {("sørg", "for"): "make sure", ("sørge", "for"): "make sure",
                       ("komme", "i", "gang"): "get started",
                       ("træder", "i", "kraft"): "take effect",
                       ("trådte", "i", "kraft"): "took effect",
                       ("har", "i", "gang"): "is running",
                       ("tag", "højde", "for"): "allow for"}
            k = 0
            while k < len(seg):
                for n in (3, 2):
                    ph = PHRASES.get(tuple(lw[k:k + n]))
                    if ph and k + n <= len(seg):
                        out[seg[k]] = ph
                        for j in range(1, n):
                            out[seg[k + j]] = ""
                        self.log(" ".join(lw[k:k + n]), "phrase", ph)
                        k += n
                        break
                else:
                    k += 1
            lw = [toks[i].lower() for i in seg]   # unchanged; kept for swaps below
            # i går / i dag / ... -> single adverb
            if len(seg) >= 2 and lw[0] == "i" and lw[1] in IDIOMS:
                out[seg[0]] = IDIOMS[lw[1]]
                out[seg[1]] = ""
                self.log(" ".join(toks[i] for i in seg[:2]), "idiom", IDIOMS[lw[1]])
            done = set()
            for k in range(1, len(seg) - 1):     # modal+subject, not V1 (questions)
                if lw[k] in MODALS and lw[k + 1] in SUBJECTS:
                    out[seg[k]], out[seg[k + 1]] = out[seg[k + 1]], out[seg[k]]
                    done.update((k, k + 1))
                    self.log(lw[k] + " " + lw[k + 1], "modal-swap", "")
            for k in (1, 2):                     # V2: [x] [verb] [subj] -> [x] [subj] [verb]
                if k + 1 >= len(seg) or k in done or k + 1 in done:
                    continue
                if self.is_verb(lw[k]) and lw[k + 1] in SUBJECTS \
                        and lw[0] not in SUBJECTS and not self.is_verb(lw[0]):
                    out[seg[k]], out[seg[k + 1]] = out[seg[k + 1]], out[seg[k]]
                    self.log(lw[k] + " " + lw[k + 1], "V2-swap", "")
                    break
        translated = "".join(out)
        translated = re.sub(r"  +", " ", translated)
        translated = re.sub(r" ([,.;:!?])", r"\1", translated)
        def unstash(mo):
            return protected[int(mo.group(1))]
        translated = re.sub(r"\x00(\d+)\x00", unstash, translated)
        return prefix + translated

def main():
    ap = argparse.ArgumentParser(description="Offline Danish->English gist translation")
    ap.add_argument("files", nargs="*", help="files to translate (default: stdin)")
    ap.add_argument("--debug", action="store_true", help="log per-token decisions to stderr")
    ap.add_argument("--stats", action="store_true", help="print coverage to stderr")
    a = ap.parse_args()
    tr = Translator(load_data(), debug=a.debug)
    def lines():
        if not a.files:
            yield from sys.stdin
            return
        in_code = False
        for f in a.files:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.lstrip().startswith("```"):
                        in_code = not in_code
                        yield line, False
                        continue
                    yield line.rstrip("\n"), (not in_code)
    if not a.files:
        for line in sys.stdin:
            print(tr.translate_line(line.rstrip("\n")))
    else:
        for f in a.files:
            fh = sys.stdin if f == "-" else open(f, encoding="utf-8", errors="replace")
            in_code = False
            for line in fh:
                if line.lstrip().startswith("```"):
                    in_code = not in_code
                    print(line.rstrip("\n")); continue
                if in_code:
                    print(line.rstrip("\n")); continue
                print(tr.translate_line(line.rstrip("\n")))
            if fh is not sys.stdin:
                fh.close()
    if a.stats:
        pct = 100 * tr.n_ok / max(tr.n_tok, 1)
        print(f"coverage: {tr.n_ok}/{tr.n_tok} words translated ({pct:.1f}%)", file=sys.stderr)

if __name__ == "__main__":
    main()
