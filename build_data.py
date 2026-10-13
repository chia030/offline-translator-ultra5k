#!/usr/bin/env python3
"""Build da2en-data.json from kaikki.org extracts.

Inputs (same directory unless given as args):
  en_da.jsonl  - English-Wiktionary entries that carry Danish translations
                 (produced by filter_file.py)
  morph.json   - Danish inflected-form map + Danish POS (from da.jsonl)

Translation choice: among all English words offered for a Danish lemma,
prefer ones whose POS matches the Danish lemma's POS, then most votes,
then shortest. A curated override list fixes high-frequency homographs.
"""
import json, sys, collections, os

HERE = os.path.dirname(os.path.abspath(__file__))
en_da = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "en_da.jsonl")
morph_p = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "morph.json")
out_path = os.path.join(HERE, "da2en-data.json")

# hand-curated: highest-frequency words where Wiktionary's vote picks a
# wrong homograph or an archaic sense
OVERRIDES = {
    "jeg": "I", "du": "you", "han": "he", "hun": "she", "vi": "we", "de": "they",
    "man": "you", "det": "it", "den": "it", "dette": "this", "denne": "this",
    "disse": "these", "min": "my", "mit": "my", "din": "your", "dit": "your",
    "sin": "its", "vores": "our", "deres": "their", "i": "in", "at": "to",
    "som": "that", "der": "there", "og": "and", "eller": "or", "men": "but",
    "for": "for", "med": "with", "af": "of", "på": "on", "til": "to", "fra": "from",
    "ikke": "not", "er": "is", "var": "was", "ville": "would", "kan": "can",
    "kunne": "could", "skal": "must", "skulle": "should", "må": "may", "bør": "should",
    "have": "have", "har": "has", "havde": "had", "bliver": "becomes",
    "hvis": "if", "når": "when", "fordi": "because", "så": "so", "som": "that",
    "også": "also", "meget": "very", "mere": "more", "kun": "only", "endnu": "still",
    "alle": "all", "enhver": "any", "ingen": "no", "hver": "each", "nogle": "some",
    "ja": "yes", "nej": "no", "her": "here", "der": "there", "nu": "now",
    "starte": "start", "køre": "run", "genstarte": "restart", "installere": "install",
    "opdatere": "update", "konfigurere": "configure", "fejlfinding": "troubleshooting",
    "tjeneste": "service", "enhed": "device", "fil": "file", "mappe": "folder",
    "kommando": "command", "krav": "requirement", "kræve": "require",
    "hukommelse": "memory", "forbindelse": "connection",
    "internetforbindelse": "internet connection", "vejledning": "guide",
    "beskrive": "describe", "kontrollere": "check", "opfylde": "meet",
    "program": "program", "system": "system", "installation": "installation",
    "bruge": "use", "gøre": "do", "finde": "find", "tage": "take", "give": "give",
    "kalde": "call", "holde": "keep", "begynde": "begin", "lykkes": "succeed",
    "åbne": "open", "lukke": "close", "velg": "select", "vælge": "select",
    "tilføj": "add", "tilføje": "add", "fjern": "remove", "fjerne": "remove",
    "ændre": "change", "gemme": "save", "gem": "save", "indlæse": "load",
    "hente": "fetch", "sende": "send", "modtage": "receive", "køre": "run",
    "strøm": "power", "indstilling": "setting", "enten": "either",
    "kabel": "cable", "afbryde": "break", "konfiguration": "configuration",
    "manuelt": "manually", "se": "see", "nedenfor": "below", "ovenfor": "above",
    "ugyldig": "invalid", "gyldig": "valid", "forhindre": "prevent",
    "oplysning": "information", "yderligere": "further", "tilslutte": "connect",
    "værdi": "value", "række": "row", "rækkevidde": "range", "forudsætter": "requires",
    "forudsætning": "requirement", "betingelse": "condition", "standardværdi": "default value",
    "standard": "default", "som standard": "by default", "forud": "pre",
    "advarsel": "warning", "bemærk": "note", "obs": "note", "eksempel": "example",
    "skærmbillede": "screenshot", "vindue": "window", "knap": "button",
    "menu": "menu", "faneblad": "tab", "felt": "field", "liste": "list",
    "side": "page", "websted": "website", "værtsmaskine": "host machine",
    "netværk": "network", "trådløs": "wireless", "kablet": "wired",
    "strømforbindelse": "power connection", "netværkskabel": "network cable",
    "påkrævet": "required", "såsom": "such as", "filoverførsel": "file transfer",
    "relæforbindelse": "relay connection", "prioriteringsrækkefølge": "priority order",
    "søgning": "search", "tydeliggøre": "clarify", "skærmbillede": "screenshot",
    "målmappe": "target folder", "understøttes": "is supported",
    "hjælpefunktion": "helper function", "netværksforbindelse": "network connection",
    "pakkehåndtering": "package manager", "understøtte": "support",
    "dine": "your", "komme": "come", "velkommen": "welcome",
    "årsag": "cause", "utilstrækkelig": "insufficient", "understøttelse": "support",
    "udskrift": "printing", "udskriftstjeneste": "print service",
}

POS_MAP = {"interjection": "intj", "adp": "adposition"}

def norm_pos(p):
    return POS_MAP.get(p, p)

m = json.load(open(morph_p, encoding="utf-8"))
da_pos = m.get("lemma_pos", {})

votes = collections.defaultdict(collections.Counter)   # da -> Counter(en)
enpos = collections.defaultdict(collections.Counter)   # (da,en) -> Counter(pos)

for line in open(en_da, encoding="utf-8"):
    e = json.loads(line)
    en = (e.get("word") or "").strip().lower()
    p = norm_pos(e.get("pos") or "")
    if not en:
        continue
    for h in e.get("da", []):
        daw = h["w"].lower().strip()
        if not daw:
            continue
        votes[daw][en] += 1
        if p:
            enpos[(daw, en)][p] += 1

d = {}
en_pos = {}
for daw, c in votes.items():
    dp = norm_pos(da_pos.get(daw, ""))
    def rank(en):
        ep = enpos[(daw, en)].most_common(1)
        ep = ep[0][0] if ep else ""
        match = 1 if (dp and ep and dp == ep) else 0
        return (-match, -c[en], len(en))
    best = sorted(c, key=rank)[0]
    d[daw] = best
    ep = enpos[(daw, best)].most_common(1)
    if ep:
        en_pos[daw] = ep[0][0]

for daw, en in OVERRIDES.items():
    d[daw] = en
    ep = enpos.get((daw, en))
    if ep:
        en_pos[daw] = ep.most_common(1)[0][0]
OVR_VERBS = {"starte", "køre", "genstarte", "installere", "opdatere", "konfigurere",
             "bruge", "gøre", "finde", "tage", "give", "kalde", "holde", "begynde",
             "lykkes", "åbne", "lukke", "vælge", "tilføje", "fjerne", "ændre",
             "gemme", "indlæse", "hente", "sende", "modtage", "beskrive",
             "kontrollere", "opfylde", "kræve", "afbryde", "tilslutte", "forhindre",
             "redigere", "slå til", "tilbageføre", "tydeliggøre", "understøtte", "komme"}
OVR_NOUNS = {"tjeneste", "enhed", "fil", "mappe", "kommando", "krav", "fejlfinding",
             "installation", "program", "system", "vejledning", "forbindelse",
             "internetforbindelse", "hukommelse", "strøm", "indstilling", "kabel",
             "konfiguration", "oplysning", "værdi", "forudsætning", "betingelse",
             "standardværdi", "advarsel", "eksempel", "skærmbillede", "vindue",
             "knap", "menu", "faneblad", "felt", "liste", "side", "websted",
             "værtsmaskine", "netværk", "strømforbindelse", "netværkskabel",
             "række", "rækkevidde", "filoverførsel", "relæforbindelse",
             "prioriteringsrækkefølge", "søgning", "målmappe", "hjælpefunktion",
             "netværksforbindelse", "pakkehåndtering", "årsag", "udskrift", "udskriftstjeneste",
             "understøttelse"}
for daw in OVERRIDES:
    if daw not in en_pos:
        en_pos[daw] = "verb" if daw in OVR_VERBS else "noun" if daw in OVR_NOUNS else ""
pos = {w: norm_pos(p) for w, p in da_pos.items() if p}
data = {"dict": d, "pos": pos, "en_pos": en_pos, "form2lemma": m["form2lemma"],
        "meta": {"da_lemmas": len(d), "built_from": "kaikki.org (Wiktionary)"}}
json.dump(data, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
print(f"dict: {len(d)} danish lemmas, pos for {len(pos)}; data -> {out_path}")
