"""Adds the missing Turkish glyphs (Ğ ğ Ş ş İ) to the Futura fonts embedded in the game SWF.

Usage: python yazi_tipi_yamala.py <input.swf> <output.swf> [preview.svg]

The glyphs are composed from parts of each font itself:
  Ş ş  = S s + the cedilla contour of Ç ç
  İ    = I + one dot of the Ö dieresis
  Ğ ğ  = G g + a breve drawn to match the font's weight, placed where the Ö/ö dieresis sits
"""
import math
import sys

from swf import (read_swf, write_swf, parse_font3, encode_font3, parse_shape, encode_shape, bbox, transform,
                 contour_points, parse_align_zones, encode_align_zones)

# new code -> base letter whose advance width and align zone it reuses
NEW_GLYPHS = {0x011E: "G", 0x011F: "g", 0x0130: "I", 0x015E: "S", 0x015F: "s"}  # Ğ ğ İ Ş ş


def glyph(font, ch):
    return parse_shape(font["shapes"][font["codes"].index(ord(ch))])


def center_x(contours):
    b = bbox(contours)
    return (b[0] + b[2]) / 2


def signed_area(contour):
    pts = contour_points(contour)
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))


def reverse(contour):
    """Same outline, opposite direction."""
    pts = [contour["start"]]
    for e in contour["edges"]:
        pts.append((e[-2], e[-1]))
    edges = []
    for k in range(len(contour["edges"]) - 1, -1, -1):
        e, (x, y) = contour["edges"][k], pts[k]
        edges.append(("L", x, y) if e[0] == "L" else ("Q", e[1], e[2], x, y))
    return {"start": pts[-1], "edges": edges}


def cedilla(font, ch):
    """Contours of Ç/ç that lie below the baseline."""
    return [c for c in glyph(font, ch) if bbox([c])[1] > 0]


def dieresis_dots(font, ch):
    """The two dot contours of Ö/ö, left to right."""
    letter_top = bbox(glyph(font, "O" if ch == "Ö" else "o"))[1]
    dots = [c for c in glyph(font, ch) if bbox([c])[3] < letter_top]
    assert len(dots) == 2, ch
    return sorted(dots, key=lambda c: bbox([c])[0])


def arc(cx, cy, rx, ry, a0, a1, steps):
    """Quadratic approximation of an elliptical arc (degrees; y grows downwards)."""
    edges = []
    da = (a1 - a0) / steps
    for k in range(steps):
        s, e = math.radians(a0 + k * da), math.radians(a0 + (k + 1) * da)
        m, f = (s + e) / 2, 1 / math.cos((e - s) / 2)
        edges.append(("Q", round(cx + rx * f * math.cos(m)), round(cy + ry * f * math.sin(m)),
                      round(cx + rx * math.cos(e)), round(cy + ry * math.sin(e))))
    return edges


def breve(cx, bottom, width, height, thickness):
    """U-shaped breve with flat ends; its lowest point is at `bottom`."""
    rx, top = width / 2, bottom - height
    irx, iry = rx - thickness, height - thickness
    start = (round(cx - rx), round(top))
    edges = arc(cx, top, rx, height, 180, 0, 8)  # outer: left -> bottom -> right
    edges.append(("L", round(cx + irx), round(top)))
    edges += arc(cx, top, irx, iry, 0, 180, 8)  # inner: right -> bottom -> left
    edges.append(("L", start[0], start[1]))
    return {"start": start, "edges": edges}


def compose(font):
    new = {}
    for code, base, src, ref in ((0x015E, "S", "Ç", "C"), (0x015F, "s", "ç", "c")):
        ced = cedilla(font, src)
        # keep the cedilla's offset from the letter centre the same as in Ç/ç
        dx = center_x(glyph(font, base)) - center_x(glyph(font, ref))
        new[code] = glyph(font, base) + transform(ced, dx=dx)

    I = glyph(font, "I")
    dot = dieresis_dots(font, "Ö")[0]
    new[0x0130] = I + transform([dot], dx=center_x(I) - center_x([dot]))

    stem = bbox(I)[2] - bbox(I)[0]
    for code, base_ch, diaer in ((0x011E, "G", "Ö"), (0x011F, "g", "ö")):
        base = glyph(font, base_ch)
        d0, d1 = (bbox([c]) for c in dieresis_dots(font, diaer))
        span, dot_h = d1[2] - d0[0], d0[3] - d0[1]
        width = 0.78 * span
        height = min(1.1 * dot_h, 0.42 * width)
        thickness = min(0.85 * stem, 0.8 * dot_h)
        if base_ch == "g":  # centre over the bowl, not the whole glyph including the tail
            cx = center_x([min(base, key=lambda c: bbox([c])[2] - bbox([c])[0])])
        else:
            cx = center_x(base)
        mark = breve(cx, d0[3], width, height, thickness)
        if (signed_area(mark) > 0) != (signed_area(dieresis_dots(font, diaer)[0]) > 0):
            mark = reverse(mark)
        new[code] = base + [mark]
    return new


def patch_font(font, zones):
    if any(c in font["codes"] for c in NEW_GLYPHS):
        return False
    L = font["layout"]
    for code, contours in sorted(compose(font).items()):
        base_index = font["codes"].index(ord(NEW_GLYPHS[code]))
        pos = next((k for k, c in enumerate(font["codes"]) if c > code), len(font["codes"]))
        xmin, ymin, xmax, ymax = bbox(contours)
        font["codes"].insert(pos, code)
        font["shapes"].insert(pos, encode_shape(contours))
        L["advance"].insert(pos, L["advance"][base_index])
        L["bounds"].insert(pos, (xmin, xmax, ymin, ymax))
        if zones is not None:
            zones.insert(pos, zones[base_index])
    assert font["codes"] == sorted(font["codes"])
    return True


def svg_preview(fonts, path, chars="GĞgğ SŞsş Iİi Ağaç Işık Şeker"):
    scale = 64 / 20480
    parts = []
    for r, font in enumerate(fonts):
        x, y = 12, 96 + r * 120
        parts.append('<text x="12" y="%d" font-family="sans-serif" font-size="13" fill="#666">%s</text>'
                     % (y - 76, font["name"].rstrip(b"\0").decode()))
        for ch in chars:
            if ch == " " or ord(ch) not in font["codes"]:
                x += 24
                continue
            i = font["codes"].index(ord(ch))
            d = ""
            for c in parse_shape(font["shapes"][i]):
                d += "M%d %d " % c["start"]
                for e in c["edges"]:
                    d += ("L%d %d " % e[1:]) if e[0] == "L" else ("Q%d %d %d %d " % e[1:])
                d += "Z "
            color = "#c0392b" if ord(ch) > 127 else "#222"
            parts.append('<path transform="translate(%.1f %d) scale(%f)" d="%s" fill="%s"/>' % (x, y, scale, d, color))
            x += font["layout"]["advance"][i] * scale + 2
    with open(path, "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="%d" style="background:#fff">%s</svg>'
                % (40 + len(fonts) * 120, "".join(parts)))


def main(src, dst, preview=None):
    swf = read_swf(src)
    fonts = {}
    for t in swf["tags"]:
        if t[0] == 75:
            font = parse_font3(t[1])
            if font["shapes"] and font["name"].startswith(b"Futura") and font["layout"]:
                fonts[font["id"]] = (t, font)
    zone_tags = {int.from_bytes(t[1][:2], "little"): t for t in swf["tags"] if t[0] == 73}
    patched = []
    for fid, (t, font) in fonts.items():
        zt = zone_tags.get(fid)
        hint, zones = None, None
        if zt:
            _, hint, zones = parse_align_zones(zt[1], len(font["codes"]))
        if patch_font(font, zones):
            t[1] = encode_font3(font)
            if zt:
                zt[1] = encode_align_zones(fid, hint, zones)
            patched.append(font)
            print("patched", font["name"].rstrip(b"\0").decode(), "->", len(font["codes"]), "glyphs")
    write_swf(swf, dst)
    if preview:
        svg_preview(patched, preview)


if __name__ == "__main__":
    main(*sys.argv[1:])
