import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))['results']
for k, r in d.items():
    if r['status'] == 'survived' and r['line'] in (32, 124, 126, 136, 245, 247, 484, 1135, 1395, 1403, 1415, 1443, 1448, 1451):
        print(r['line'], '|', r['original'], '|', r['mutant'])
