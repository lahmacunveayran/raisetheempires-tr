"""Adds the Turkish letters (and a few other accented ones) to small embedded font subsets in the game's asset SWFs.

Usage: python yazi_tipi_tamamla.py <donor ZGame swf (already patched)> <assets dir> <output dir> [report.svg]

Many dialog SWFs embed a ~114 glyph subset (ASCII only) of a Futura weight for text fields that render with
embedded outlines, so every non-ASCII letter of the translation is invisible there. For each such font:

  1. Pick the donor font (from ZGame) that fits best: for a set of reference letters find the scale k that maps
     donor advances to target advances (median of the ratios), then measure the mean error of the scaled glyph
     bounding boxes and advances. Lowest error wins.
  2. Build each missing letter from the target's OWN base letter (c, o, s, g, I, ...) plus the diacritic mark
     contours of the donor's composed letter (ç = c + cedilla, ...), scaled by k and placed so that the mark keeps
     its offset from the base letter's centre. ı is the target's own i without its dot.

Only fonts without static DefineText usage are changed (inserting glyphs shifts glyph indices).
"""
import os
import statistics
import sys

from swf import (read_swf, write_swf, parse_font3, encode_font3, parse_shape, encode_shape, bbox, transform,
                 parse_align_zones, encode_align_zones)

# letter -> (base letter in the target font, composed letter in the donor font whose extra contours are the mark)
COMPOSED = {
    "ç": ("c", "ç"), "Ç": ("C", "Ç"), "ö": ("o", "ö"), "Ö": ("O", "Ö"), "ü": ("u", "ü"), "Ü": ("U", "Ü"),
    "ş": ("s", "ş"), "Ş": ("S", "Ş"), "ğ": ("g", "ğ"), "Ğ": ("G", "Ğ"), "İ": ("I", "İ"),
    "â": ("a", "â"), "Â": ("A", "Â"), "û": ("u", "û"), "î": ("ı", "î"),
}
REFERENCE = "ABCDEHKMNORSTWabcdeghmnorstw0123456789"


def glyphs(font):
    return {chr(c): (parse_shape(font["shapes"][i]), font["layout"]["advance"][i], i)
            for i, c in enumerate(font["codes"])}


def fit(target, donor):
    """(scale, mean error in font units) of donor -> target over the reference letters."""
    t, d = glyphs(target), glyphs(donor)
    letters = [ch for ch in REFERENCE if ch in t and ch in d and d[ch][1]]
    if len(letters) < 10:
        return None, float("inf")
    k = statistics.median(t[ch][1] / d[ch][1] for ch in letters)
    errors = []
    for ch in letters:
        tb, db = bbox(t[ch][0]), bbox(d[ch][0])
        errors += [abs(tb[j] - k * db[j]) for j in range(4)] + [abs(t[ch][1] - k * d[ch][1])]
    return k, statistics.mean(errors)


def center_x(contours):
    b = bbox(contours)
    return (b[0] + b[2]) / 2


def mark_contours(donor_glyphs, composed, base):
    """Contours of the donor's composed letter that are not part of its base letter (the diacritic)."""
    # Purely geometric: a mark lies entirely above the base letter (dots, breve, circumflex) or entirely below the
    # baseline (cedilla). Comparing contours with the base letter is not reliable: some composed letters redraw the
    # base slightly differently, which would make e.g. the inner ring of Ö look like a mark.
    comp = donor_glyphs[composed][0]
    top = bbox(donor_glyphs[base][0])[1]  # y grows downwards
    tolerance = 0.01 * 20480
    return [c for c in comp if bbox([c])[3] <= top + tolerance or bbox([c])[1] >= -tolerance]


def dotless_i(target_glyphs):
    contours = target_glyphs["i"][0]
    if len(contours) < 2:
        return None
    dot = min(contours, key=lambda c: bbox([c])[1])  # highest contour (y grows downwards)
    return [c for c in contours if c is not dot]


def complete_font(font, donor, k, zones):
    t, d = glyphs(font), glyphs(donor)
    added = []
    new = {}
    if "ı" not in t and "i" in t and "ı" in d:
        contours = dotless_i(t)
        if contours:
            new["ı"] = (contours, t["i"][1], t["i"][2])
            t["ı"] = (contours, t["i"][1], t["i"][2])
    for ch, (base, composed) in COMPOSED.items():
        if ch in t or base not in t or composed not in d or (base not in d and base != "ı"):
            continue
        donor_base = base if base in d else "i"
        marks = mark_contours(d, composed, donor_base)
        if not marks:
            continue
        dx = center_x(t[base][0]) - k * center_x(d[donor_base][0])
        placed = transform(transform(marks, scale=k), dx=dx)
        new[ch] = (t[base][0] + placed, t[base][1], t[base][2])
    L = font["layout"]
    for ch, (contours, advance, _) in sorted(new.items(), key=lambda kv: ord(kv[0])):
        code = ord(ch)
        pos = next((i for i, c in enumerate(font["codes"]) if c > code), len(font["codes"]))
        xmin, ymin, xmax, ymax = bbox(contours)
        zone = zones[font["codes"].index(ord("I" if ch.isupper() else "i"))] if zones is not None else None
        font["codes"].insert(pos, code)
        font["shapes"].insert(pos, encode_shape(contours))
        L["advance"].insert(pos, advance)
        L["bounds"].insert(pos, (xmin, xmax, ymin, ymax))
        if zones is not None:
            zones.insert(pos, zone)
        added.append(ch)
    assert font["codes"] == sorted(font["codes"])
    return added


def donor_fonts(path):
    out = []
    for code, tag in read_swf(path)["tags"]:
        if code == 75:
            f = parse_font3(tag)
            if f["shapes"] and f["layout"] and f["name"].startswith(b"Futura"):
                out.append(f)
    return out


def outline_font_ids(swf):
    """Fonts used by dynamic text fields that render embedded outlines, and fonts used by static text."""
    import struct
    from swf import BitReader
    outlined, static = set(), set()
    for code, tag in swf["tags"]:
        if code == 37:
            r = BitReader(tag, 2)
            nb = r.ub(5)
            for _ in range(4):
                r.sb(nb)
            p = r.align()
            if tag[p] & 0x01 and tag[p + 1] & 0x01:
                outlined.add(struct.unpack_from("<H", tag, p + 2)[0])
        elif code in (11, 33):
            static.add(None)  # any static text: be conservative
    return outlined, static


def process(path, donors, out_path, log):
    swf = read_swf(path)
    outlined, static = outline_font_ids(swf)
    if not outlined or static:
        return []
    zone_tags = {int.from_bytes(t[1][:2], "little"): t for t in swf["tags"] if t[0] == 73}
    changed = []
    for t in swf["tags"]:
        if t[0] != 75:
            continue
        try:
            font = parse_font3(t[1])
        except ValueError as error:
            log("  skip font (%s)" % error)
            continue
        if font["id"] not in outlined or not font["layout"] or len(font["codes"]) < 60:
            continue
        best = min(((fit(font, d), d) for d in donors), key=lambda x: x[0][1])
        (k, err), donor = best
        if k is None or err > 0.03 * 20480:
            log("  font %d %s: no donor fits (error %.0f)" % (font["id"], font["name"], err))
            continue
        zt = zone_tags.get(font["id"])
        hint, zones = (None, None)
        if zt:
            _, hint, zones = parse_align_zones(zt[1], len(font["codes"]))
        added = complete_font(font, donor, k, zones)
        if added:
            t[1] = encode_font3(font)
            if zt:
                zt[1] = encode_align_zones(font["id"], hint, zones)
            changed.append(font)
            log("  font %d %s: donor %s k=%.4f err=%.2f%% em, added %s" % (
                font["id"], font["name"].rstrip(b"\0").decode(), donor["name"].rstrip(b"\0").decode(), k,
                err / 20480 * 100, "".join(added)))
    if changed:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        write_swf(swf, out_path)
    return changed


def main(donor_path, assets_dir, out_dir, report=None):
    donors = donor_fonts(donor_path)
    results = []
    for root, _, files in os.walk(assets_dir):
        for name in files:
            if not name.lower().endswith(".swf"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, assets_dir)
            lines = []
            try:
                changed = process(path, donors, os.path.join(out_dir, rel), lines.append)
            except Exception as error:  # unusual SWFs: leave them alone
                lines.append("  skipped: %r" % error)
                changed = []
            if changed or any("no donor" in l for l in lines):
                print(rel)
                for l in lines:
                    print(l)
            if changed:
                results.append((rel, changed))
    print(len(results), "files patched")
    if report and results:
        from yazi_tipi_yamala import svg_preview
        svg_preview([f for _, fonts in results[:6] for f in fonts][:6], report, "Turkce: çÇğĞıİöÖşŞüÜ âÂî")


if __name__ == "__main__":
    main(*sys.argv[1:])
