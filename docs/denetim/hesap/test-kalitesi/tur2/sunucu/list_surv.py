import json, sys
S = r"<HOME>\AppData\Local\Temp\claude\44db76dc85e0ce87\6e027af0-22bc-435d-8563-59919183e99e\scratchpad"
d = json.load(open(S + r"\denetim2\mut_server_save.json", encoding="utf-8"))
for k, r in sorted(d["results"].items(), key=lambda kv: int(kv[0])):
    if r.get("full_status", r["status"]) == "survived":
        print(k, r["line"], "|", r["original"][:150])
        print("      ->", r["mutant"][:150])
