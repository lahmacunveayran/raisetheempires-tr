import json
d = json.load(open('test/init_user.json'))
print(list(d))
w = d['userInfo']['world']
print(w.get('campaign'))
print(list(w))
print([o['itemName'] for o in w['objects']][:30])
print(d['userInfo']['player']['expansions'])
print({k: v for k, v in d['userInfo']['player'].items() if not isinstance(v, (dict, list))})
import sys
sys.argv = ["probe4_kayit"]
es = __import__("empires-server")
for r in es.app.url_map.iter_rules():
    print(r.rule, sorted(r.methods - {"HEAD", "OPTIONS"}), r.endpoint)
