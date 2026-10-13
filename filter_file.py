import sys, json

inp = open('/home/bot/.hermes/profiles/chiara/cache/scratch/da2en/en.jsonl', encoding='utf-8', errors='replace')
out = open('/home/bot/.hermes/profiles/chiara/cache/scratch/da2en/en_da.jsonl', 'w', encoding='utf-8')
n = kept = 0
for line in inp:
    n += 1
    if '"Danish"' not in line:
        continue
    try:
        e = json.loads(line)
    except Exception:
        continue
    hits = []
    for si, sense in enumerate(e.get('senses', [])):
        for t in sense.get('translations', []):
            if t.get('lang_code') == 'da':
                w = t.get('word')
                if w:
                    hits.append({'w': w, 'si': si})
    if hits:
        kept += 1
        out.write(json.dumps({'word': e.get('word'), 'pos': e.get('pos'), 'da': hits}, ensure_ascii=False) + '\n')
out.close()
print('scanned', n, 'kept', kept)
