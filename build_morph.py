#!/usr/bin/env python3
"""Build morph.json from kaikki.org-dictionary-Danish.jsonl.

Maps inflected forms -> lemma and records Danish POS per lemma.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "da.jsonl")

form2lemma, lemma_pos = {}, {}
for line in open(src, encoding="utf-8"):
    e = json.loads(line)
    w = (e.get("word") or "").lower()
    if not w:
        continue
    lemma_pos.setdefault(w, e.get("pos"))
    for fm in e.get("forms", []):
        f = (fm.get("form") or "").lower().strip()
        if not f or f == w or " " in f or "(" in f or "{" in f:
            continue
        form2lemma.setdefault(f, w)

json.dump({"form2lemma": form2lemma, "lemma_pos": lemma_pos},
          open(os.path.join(HERE, "morph.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
print(f"lemmas: {len(lemma_pos)}, forms: {len(form2lemma)}")
