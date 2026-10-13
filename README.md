# da2en — offline Danish → English gist translator

Translates Danish documentation text into rough English so you can follow
what a page says. Rule-based only: word lists, morphology rules, and a few
word-order rules. No LLM, no machine learning, no network at runtime.
Danish → English only, in that direction only.

## Use

    ./da2en.py path/to/file.md            # translate a file
    ./da2en.py < input.txt                # translate stdin
    ./da2en.py --debug "sætning her"      # show per-token decisions on stderr

Markdown-aware: fenced code blocks, inline `code`, URLs and links pass
through untouched. Unknown words are left as Danish (many Danish technical
words are close enough to read).

## How it works

1. Dictionary lookup (Danish lemma → English), built from Wiktionary data
   via kaikki.org. Translation choice is POS-matched, plus a small curated
   override list for the highest-frequency words.
2. Inflected forms → lemma (107k forms: plurals, definite forms, past
   tenses, participles).
3. Rule fallbacks: definite suffix stripping (`huset` → `the house`),
   verb endings (`købte` → `buy`), `-s` passive (`konfigureres` →
   `is configure`), `-ering` cognates (`implementering` → `implementing`),
   compound splitting (`pakke` + `håndtering` → `package-handling`).
4. Word-order rules: `i går/i dag/i morgen` → yesterday/today/tomorrow,
   modal+subject swap (`skal du` → `you must`), V2 swap
   (`I går så jeg` → `yesterday I saw`).

## Expect

Gist, not prose. Word order and function words are often off; content
words are mostly right. Good enough to skim a page and know what it tells
you to do. Not good enough to paste into anything.

## Rebuilding the data (optional)

`da2en-data.json` is generated from two kaikki.org extracts:

    curl -o da.jsonl https://kaikki.org/dictionary/Danish/kaikki.org-dictionary-Danish.jsonl
    curl -o en.jsonl https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl
    python3 filter_file.py     # en.jsonl -> en_da.jsonl (edit paths in file)
    python3 build_morph.py     # da.jsonl -> morph.json
    python3 build_data.py      # -> da2en-data.json

Licenses: kaikki.org data is Wiktionary (CC BY-SA / GFDL). The scripts are
yours to do with as you please.
