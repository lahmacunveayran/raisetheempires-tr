t = open("quest_trees.py", "rb").read()
i = t.index(b"if quest not in started")
print(repr(t[i - 10:i + 80]), t.count(b"\r"))
