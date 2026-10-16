"""Turkish translation helper for the game's en_US.xml.

  python ceviri.py cikar <en_US.xml>            -> writes kaynak/parca_NNN.json (texts still to translate)
  python ceviri.py kontrol <en_US.xml>          -> validates ceviri/parca_NNN.json against the sources
  python ceviri.py uret <en_US.xml> <out.xml>   -> writes the Turkish XML (untranslated strings stay English)

Translations live in ceviri/parca_NNN.json as {"<source text>": "<Turkish text>"}.
"""
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(HERE, "kaynak")
TR_DIR = os.path.join(HERE, "ceviri")
BATCH = 250

UI_PACKAGES = ["Main", "Dialogs", "Tooltips", "Combat", "Levels", "Narrator", "Preloader", "Footer", "Objects",
               "Decorations", "Gifts", "BuildingParts", "DailyQuests", "VisitorHelp", "WorldEvents", "Leaderboards",
               "Letters", "Requests", "Crews", "Promo", "ZMC", "FeedPopups", "MegaUnit"]
ITEM_SUFFIXES = ("_menuName", "_sentenceName", "_description", "_override", "_map")
PLAYABLE_TREES = {"028", "036", "040", "042", "044", "046", "047"}
QUEST_PACKAGES = ["Quests", "QuestTrees", "Megaseries", "Speeches", "Conversations"]

INTENTIONALLY_EMPTY = {"The"}  # "The <name> Alliance" -> "<name> İttifakı"

TOKEN = re.compile(r"\{[^}]*\}|<[^>]+>|%\w|\\n|&\w+;|\n")


def tokens(text):
    return sorted(TOKEN.findall(text or ""))


def active_quest_prefixes():
    path = os.path.join(HERE, "aktif_gorevler.json")
    if not os.path.exists(path):
        return ()
    prefixes = []
    for n in json.load(open(path)):
        prefixes.append(n + "_")
        if n.startswith("Q") and n[1:].isdigit():
            prefixes.append("quest_" + n[1:] + "_")
    return tuple(prefixes)


def menu_key_for(pkg, key, menu_names):
    """Turkish has no articles and uses the singular after numbers, so every variation of a
    _sentenceName ("a Wood", "some Wood", "the Wood", ...) is filled with the translated _menuName.
    Returns the (pkg, menu key) to copy from, or None."""
    for suffix, menus in (("_sentenceName_override", ("_menuName_override", "_menuName")),
                          ("_sentenceName", ("_menuName",))):
        if key.endswith(suffix):
            base = key[:-len(suffix)]
            return next(((pkg, base + m) for m in menus if (pkg, base + m) in menu_names), None)
    return None


def wanted(pkg, key, quest_prefixes, menu_names):
    if menu_key_for(pkg, key, menu_names):
        return False
    # Speeches are keyed by speaker + quest number (Speech_Cross_0670_01_Body), so the quest prefixes never match them
    if pkg in UI_PACKAGES or pkg.startswith("Season_") or pkg in ("Items", "Episodes", "Speeches",
                                                                       "Conversations", "Megaseries",
                                                                       "MessageOfTheDay"):
        return True
    if pkg == "Campaign":
        return not key.endswith("_desc") or not key.count("_") == 2  # skip "C001 Campaign Description" stubs
    if pkg == "Quests":  # all of them, so quests that unlock later are Turkish too
        return True
    if pkg == "QuestTrees":  # shared mini series texts and the mini series the server can offer (quest_trees.PLAYABLE)
        tree = re.search(r'(?:QT|MS|questhook|Miniseries|QH)_?0?(\d{2,3})', key)
        return tree is None or tree.group(1).zfill(3) in PLAYABLE_TREES
    if pkg in QUEST_PACKAGES:
        return bool(quest_prefixes) and key.startswith(quest_prefixes)
    return False


def menu_names_of(root):
    """{(pkg, "<item>_menuName[_override]"): text}"""
    return {(p.get("name"), s.get("key")): s[0].text for p in root for s in p
            if s.get("key").endswith(("_menuName", "_menuName_override")) and len(s)}


def texts(root):
    """Yields (element, text) for every translatable text node in scope."""
    prefixes = active_quest_prefixes()
    menu_names = menu_names_of(root)
    for pkg in root:
        for s in pkg:
            if not wanted(pkg.get("name"), s.get("key"), prefixes, menu_names):
                continue
            for e in s:
                if e.text and re.search(r"[A-Za-z]", TOKEN.sub("", e.text)):
                    yield e, e.text


def extract(xml_path):
    root = ET.parse(xml_path).getroot()
    tr = Translations()
    todo = [t for t in dict.fromkeys(t for _, t in texts(root)) if tr.get(t) is None]
    todo = list({canon(t): t for t in reversed(todo)}.values())[::-1]  # one representative per sibling group
    os.makedirs(SRC_DIR, exist_ok=True)
    for old in glob.glob(os.path.join(SRC_DIR, "parca_*.json")):
        os.remove(old)
    done = glob.glob(os.path.join(TR_DIR, "parca_*.json"))
    first = max([int(os.path.basename(p)[6:9]) for p in done], default=-1) + 1
    for n in range(0, len(todo), BATCH):
        with open(os.path.join(SRC_DIR, "parca_%03d.json" % (first + n // BATCH)), "w", encoding="utf-8") as f:
            json.dump(todo[n:n + BATCH], f, ensure_ascii=False, indent=0)
    print(len(todo), "texts left,", sum(len(t) for t in todo), "characters,",
          (len(todo) + BATCH - 1) // BATCH, "batches starting at", first)


PLACEHOLDER = re.compile(r"\{(\w+)(?:,[^}]*)?\}")


def canon(text):
    """Texts that differ only in placeholder modifiers ({user,fem} / {user,masc}, {cash,plural} /
    {cash,singular}, ...) are variations of one sentence and share a Turkish translation."""
    return PLACEHOLDER.sub(r"{\1}", text)


class Translations:
    def __init__(self):
        self.tr, self.by_canon = {}, {}
        for path in sorted(glob.glob(os.path.join(TR_DIR, "parca_*.json"))):
            self.tr.update(json.load(open(path, encoding="utf-8")))
        for s, t in self.tr.items():
            self.by_canon.setdefault(canon(s), (s, t))

    def get(self, text):
        """Translation of text, directly or derived from a sibling variation; None if unknown."""
        if text in self.tr:
            return self.tr[text]
        sibling = self.by_canon.get(canon(text))
        if not sibling:
            return None
        src, t = sibling
        mine, theirs = TOKEN.findall(text), TOKEN.findall(src)
        mapping = {}
        for a, b in zip(theirs, mine):
            if mapping.setdefault(a, b) != b:
                return None  # ambiguous
        t = TOKEN.sub(lambda m: mapping.get(m.group(0), m.group(0)), t)
        return t if tokens(t) == tokens(text) else None


def with_placeholders_of(name, variant):
    """`name` with its placeholders replaced by those of `variant`, matched in order by placeholder name
    ("Chief of Staff{user,name}" + variant "...{user,fem}" -> "Kurmay Başkanı{user,fem}"). None if they don't match."""
    mine, theirs = TOKEN.findall(name), TOKEN.findall(variant or "")
    if [canon(t) for t in mine] != [canon(t) for t in theirs]:
        return None
    mapping = dict(zip(mine, theirs))
    return TOKEN.sub(lambda m: mapping.get(m.group(0), m.group(0)), name)


def check(xml_path):
    tr = Translations()
    sources = list(dict.fromkeys(t for _, t in texts(ET.parse(xml_path).getroot())))
    missing = [s for s in sources if tr.get(s) is None]
    known = {canon(s) for s in sources}
    extra = [s for s in tr.tr if canon(s) not in known]
    bad = [(s, t) for s, t in tr.tr.items() if tokens(s) != tokens(t)]
    empty = [s for s, t in tr.tr.items() if not t.strip() and s not in INTENTIONALLY_EMPTY]
    print("translated %d / %d" % (len(sources) - len(missing), len(sources)))
    if extra:
        print(len(extra), "translations are no longer needed (now derived or out of scope)")
    for s, t in bad[:50]:
        print("TOKEN MISMATCH:", repr(s), "->", repr(t), tokens(s), tokens(t))
    for s in empty[:20]:
        print("EMPTY:", repr(s))
    return not (bad or empty)


def build(xml_path, out_path):
    raw = open(xml_path, "rb").read()
    tree = ET.ElementTree(ET.fromstring(raw))
    tr = Translations()
    root = tree.getroot()
    english_names = menu_names_of(root)
    done = 0
    for e, t in list(texts(root)):
        turkish = tr.get(t)
        if turkish is not None:
            e.text = turkish
            done += 1
    turkish_names = menu_names_of(root)
    for pkg in root:
        for s in pkg:
            menu_key = menu_key_for(pkg.get("name"), s.get("key"), english_names)
            if menu_key and turkish_names[menu_key]:
                # Also for names that stay the same in Turkish (Hangar, Pilot, ...): drops "a/the/some".
                variants = [with_placeholders_of(turkish_names[menu_key], e.text) for e in s]
                if all(v is not None for v in variants):
                    for e, v in zip(s, variants):
                        e.text = v
                    done += 1
    tree.write(out_path, encoding="UTF-8", xml_declaration=True)
    print(done, "strings translated ->", out_path)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "cikar":
        extract(sys.argv[2])
    elif cmd == "kontrol":
        sys.exit(0 if check(sys.argv[2]) else 1)
    elif cmd == "uret":
        build(sys.argv[2], sys.argv[3])
