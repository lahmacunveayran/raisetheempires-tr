"""Makes the missing PvP defeat dialog (PU_Pvp_Defeat.swf) from the one that is kept (PU_Pvp_Defeat2.swf).

Usage: python pvp_yenilgi.py <PU_Pvp_Defeat2.swf> <PU_Pvp_Defeat.swf>

Losing a PvP battle opens BattleChallengeLostPopup. Without the unit buy back experiment it loads PU_Pvp_Defeat.swf,
which is lost, and the battle stays dark forever. PU_Pvp_Defeat2.swf is the same dialog with unit buy back. The
popup without buy back writes "units lost x/y" in details_tf and leaves out the buy back parts, so the buy back
dialog gets that name and loses those parts:
  card: no discount
  dialog: title02_tf -> details_tf, no "buy all" button, discount or "last chance" text
Nothing else is renamed: renaming more of the card's and dialog's names broke the popup in the game.
"""
import sys

from swf import read_swf, write_swf

RENAMES = {"title02_tf": "details_tf"}
REMOVED = {"message_tf", "discount_tf"}
REMOVED_FROM_DIALOG = {"emp_bt"}  # the buy all button; the cards' own emp_bt is hidden by the popup
DIALOG_MARK = "lost_tf_0"
DEFINE_SPRITE, PLACE_OBJECT2, PLACE_OBJECT3, REMOVE_OBJECT, REMOVE_OBJECT2 = 39, 26, 70, 5, 28
HAS_NAME, HAS_CHARACTER, MOVE = 0x20, 0x02, 0x01


def sprite_tags(data):
    tags, pos = [], 4
    while pos < len(data):
        tc = int.from_bytes(data[pos:pos + 2], "little")
        pos += 2
        code, ln = tc >> 6, tc & 0x3F
        if ln == 0x3F:
            ln = int.from_bytes(data[pos:pos + 4], "little")
            pos += 4
        tags.append([code, data[pos:pos + ln]])
        pos += ln
        if code == 0:
            break
    return tags


def encode_tags(tags):
    out = bytearray()
    for code, data in tags:
        if len(data) < 0x3F:
            out += ((code << 6) | len(data)).to_bytes(2, "little")
        else:
            out += ((code << 6) | 0x3F).to_bytes(2, "little") + len(data).to_bytes(4, "little")
        out += data
    return bytes(out)


def depth(code, data):
    offset = {PLACE_OBJECT2: 1, PLACE_OBJECT3: 2, REMOVE_OBJECT2: 0, REMOVE_OBJECT: 2}.get(code)
    return None if offset is None else int.from_bytes(data[offset:offset + 2], "little")


def bits_end(data, pos, fields):
    """Where a bit record (MATRIX, CXFORMWITHALPHA) starting at the byte pos ends, byte aligned. fields(read) reads
    it with read(n) -> the next n bits as a number."""
    bit = pos * 8

    def read(n):
        nonlocal bit
        value = 0
        for _ in range(n):
            value = value << 1 | data[bit // 8] >> (7 - bit % 8) & 1
            bit += 1
        return value
    fields(read)
    return (bit + 7) // 8


def matrix(read):
    if read(1):  # HasScale
        n = read(5)
        read(2 * n)
    if read(1):  # HasRotate
        n = read(5)
        read(2 * n)
    n = read(5)  # translate
    read(2 * n)


def color_transform(read):
    add, mult, n = read(1), read(1), read(4)
    read(4 * n * (add + mult))


def name_span(code, data):
    """(start, end) of the name a PlaceObject2/3 gives its object, end at the zero byte; None without a name."""
    if code not in (PLACE_OBJECT2, PLACE_OBJECT3) or not data[0] & HAS_NAME:
        return None
    flags = data[0]
    pos = 3
    if code == PLACE_OBJECT3:
        pos = 4
        if data[1] & 0x08 or (data[1] & 0x10 and flags & HAS_CHARACTER):  # HasClassName, HasImage
            pos = data.index(b"\x00", pos) + 1
    if flags & HAS_CHARACTER:
        pos += 2
    if flags & 0x04:  # HasMatrix
        pos = bits_end(data, pos, matrix)
    if flags & 0x08:  # HasColorTransform
        pos = bits_end(data, pos, color_transform)
    if flags & 0x10:  # HasRatio
        pos += 2
    return pos, data.index(b"\x00", pos)


def name_of(code, data):
    span = name_span(code, data)
    return data[span[0]:span[1]].decode("latin1") if span else None


def named(code, data, names):
    """Whether this placement gives its object one of the names."""
    return name_of(code, data) in names


def patch_sprite(data):
    tags = sprite_tags(data)
    removed = REMOVED | (REMOVED_FROM_DIALOG if any(named(c, t, [DIALOG_MARK]) for c, t in tags) else set())
    kept, hidden, changed = [], set(), set()  # hidden: depths of removed objects, until they leave the stage
    for code, tag in tags:
        d = depth(code, tag)
        new_object = code in (PLACE_OBJECT2, PLACE_OBJECT3) and tag[0] & HAS_CHARACTER and not tag[0] & MOVE
        if named(code, tag, removed):
            hidden.add(d)
            changed.add(name_of(code, tag))
            continue
        if d in hidden:
            if new_object:
                hidden.discard(d)
            else:
                if code in (REMOVE_OBJECT, REMOVE_OBJECT2):
                    hidden.discard(d)
                continue
        if named(code, tag, RENAMES):
            old, (start, end) = name_of(code, tag), name_span(code, tag)
            changed.add(old)
            tag = tag[:start] + RENAMES[old].encode() + tag[end:]
        kept.append([code, tag])
    return data[:4] + encode_tags(kept), sorted(changed)


def main(source, target):
    swf = read_swf(source)
    for tag in swf["tags"]:
        if tag[0] == DEFINE_SPRITE:
            tag[1], changed = patch_sprite(tag[1])
            if changed:
                print("sprite", int.from_bytes(tag[1][:2], "little"), "changed:", ", ".join(changed))
    write_swf(swf, target)


if __name__ == "__main__":
    main(*sys.argv[1:3])
