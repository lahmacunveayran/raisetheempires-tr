"""Minimal SWF reader/writer for patching DefineFont3 glyphs."""
import struct
import zlib


class BitReader:
    def __init__(self, data, pos=0):
        self.data, self.bytepos, self.bit = data, pos, 0

    def ub(self, n):
        v = 0
        for _ in range(n):
            byte = self.data[self.bytepos]
            v = (v << 1) | ((byte >> (7 - self.bit)) & 1)
            self.bit += 1
            if self.bit == 8:
                self.bit, self.bytepos = 0, self.bytepos + 1
        return v

    def sb(self, n):
        v = self.ub(n)
        return v - (1 << n) if n and v & (1 << (n - 1)) else v

    def align(self):
        if self.bit:
            self.bit, self.bytepos = 0, self.bytepos + 1
        return self.bytepos


class BitWriter:
    def __init__(self):
        self.out, self.cur, self.n = bytearray(), 0, 0

    def ub(self, n, v):
        for i in range(n - 1, -1, -1):
            self.cur = (self.cur << 1) | ((v >> i) & 1)
            self.n += 1
            if self.n == 8:
                self.out.append(self.cur)
                self.cur, self.n = 0, 0

    def sb(self, n, v):
        self.ub(n, v & ((1 << n) - 1))

    def bytes(self):
        if self.n:
            self.out.append(self.cur << (8 - self.n))
            self.cur, self.n = 0, 0
        return bytes(self.out)


def sbits(*vals):
    """Bits needed to store all values as signed."""
    n = 1
    for v in vals:
        n = max(n, (v if v >= 0 else ~v).bit_length() + 1)
    return n


# ---------- glyph shapes ----------
# glyph = list of contours; contour = {"start": (x, y), "edges": [("L", x, y) | ("Q", cx, cy, x, y)]}
# Coordinates are absolute, in font units (DefineFont3: 20480 per em), y grows downwards.

def parse_shape(data):
    r = BitReader(data)
    nfill, nline = r.ub(4), r.ub(4)
    contours, x, y = [], 0, 0
    while True:
        if r.ub(1) == 0:
            new_styles, s_line, s_f1, s_f0, s_move = r.ub(1), r.ub(1), r.ub(1), r.ub(1), r.ub(1)
            if not (new_styles or s_line or s_f1 or s_f0 or s_move):
                break
            if new_styles:
                raise ValueError("new styles in glyph")
            if s_move:
                nb = r.ub(5)
                x, y = r.sb(nb), r.sb(nb)
            if s_f0:
                r.ub(nfill)
            if s_f1:
                r.ub(nfill)
            if s_line:
                r.ub(nline)
            if s_move or not contours:
                contours.append({"start": (x, y), "edges": []})
        else:
            if r.ub(1):  # straight
                nb = r.ub(4) + 2
                if r.ub(1):
                    dx, dy = r.sb(nb), r.sb(nb)
                elif r.ub(1):
                    dx, dy = 0, r.sb(nb)
                else:
                    dx, dy = r.sb(nb), 0
                x, y = x + dx, y + dy
                contours[-1]["edges"].append(("L", x, y))
            else:
                nb = r.ub(4) + 2
                cdx, cdy, adx, ady = r.sb(nb), r.sb(nb), r.sb(nb), r.sb(nb)
                cx, cy = x + cdx, y + cdy
                x, y = cx + adx, cy + ady
                contours[-1]["edges"].append(("Q", cx, cy, x, y))
    return [c for c in contours if c["edges"]]


def encode_shape(contours):
    w = BitWriter()
    w.ub(4, 1)  # NumFillBits
    w.ub(4, 0)  # NumLineBits
    first = True
    for c in contours:
        sx, sy = c["start"]
        w.ub(1, 0)  # style change record
        w.ub(1, 0)  # StateNewStyles
        w.ub(1, 0)  # StateLineStyle
        w.ub(1, 1 if first else 0)  # StateFillStyle1
        w.ub(1, 0)  # StateFillStyle0
        w.ub(1, 1)  # StateMoveTo
        nb = sbits(sx, sy)
        w.ub(5, nb)
        w.sb(nb, sx)
        w.sb(nb, sy)
        if first:
            w.ub(1, 1)  # FillStyle1 = 1
            first = False
        x, y = sx, sy
        for e in c["edges"]:
            w.ub(1, 1)  # edge record
            if e[0] == "L":
                dx, dy = e[1] - x, e[2] - y
                w.ub(1, 1)
                nb = max(2, sbits(dx, dy))
                w.ub(4, nb - 2)
                if dx and dy:
                    w.ub(1, 1)
                    w.sb(nb, dx)
                    w.sb(nb, dy)
                elif dx == 0:
                    w.ub(1, 0)
                    w.ub(1, 1)
                    w.sb(nb, dy)
                else:
                    w.ub(1, 0)
                    w.ub(1, 0)
                    w.sb(nb, dx)
                x, y = e[1], e[2]
            else:
                cdx, cdy, adx, ady = e[1] - x, e[2] - y, e[3] - e[1], e[4] - e[2]
                w.ub(1, 0)
                nb = max(2, sbits(cdx, cdy, adx, ady))
                w.ub(4, nb - 2)
                for v in (cdx, cdy, adx, ady):
                    w.sb(nb, v)
                x, y = e[3], e[4]
    w.ub(6, 0)  # EndShapeRecord
    return w.bytes()


def contour_points(c):
    pts = [c["start"]]
    for e in c["edges"]:
        pts += [(e[1], e[2])] if e[0] == "L" else [(e[1], e[2]), (e[3], e[4])]
    return pts


def bbox(contours):
    """(xmin, ymin, xmax, ymax)"""
    pts = [p for c in contours for p in contour_points(c)]
    if not pts:
        return (0, 0, 0, 0)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def transform(contours, dx=0, dy=0, scale=1.0, ox=0, oy=0):
    """Scale around (ox, oy), then translate by (dx, dy)."""
    def t(x, y):
        return int(round(ox + (x - ox) * scale + dx)), int(round(oy + (y - oy) * scale + dy))
    out = []
    for c in contours:
        edges = [("L",) + t(e[1], e[2]) if e[0] == "L" else ("Q",) + t(e[1], e[2]) + t(e[3], e[4])
                 for e in c["edges"]]
        out.append({"start": t(*c["start"]), "edges": edges})
    return out


# ---------- SWF container ----------

def read_swf(path):
    d = open(path, "rb").read()
    sig, ver = d[:3], d[3]
    if sig not in (b"CWS", b"FWS"):
        raise ValueError("unsupported SWF " + repr(sig))
    body = zlib.decompress(d[8:]) if sig == b"CWS" else d[8:]
    nbits = body[0] >> 3
    hdr_len = (5 + 4 * nbits + 7) // 8 + 4
    tags, pos = [], hdr_len
    while pos < len(body):
        tc = struct.unpack_from("<H", body, pos)[0]
        pos += 2
        code, ln = tc >> 6, tc & 0x3F
        if ln == 0x3F:
            ln = struct.unpack_from("<I", body, pos)[0]
            pos += 4
        tags.append([code, body[pos:pos + ln]])
        pos += ln
        if code == 0:
            break
    return {"sig": sig, "ver": ver, "header": body[:hdr_len], "tags": tags}


def write_swf(swf, path):
    body = bytearray(swf["header"])
    for code, data in swf["tags"]:
        if len(data) < 0x3F:
            body += struct.pack("<H", (code << 6) | len(data))
        else:
            body += struct.pack("<HI", (code << 6) | 0x3F, len(data))
        body += data
    out = swf["sig"] + bytes([swf["ver"]]) + struct.pack("<I", len(body) + 8)
    out += zlib.compress(bytes(body), 9) if swf["sig"] == b"CWS" else bytes(body)
    with open(path, "wb") as f:
        f.write(out)


# ---------- DefineFont3 / DefineFontAlignZones ----------

def parse_font3(tag):
    fid, flags, lang, nl = struct.unpack_from("<HBBB", tag, 0)
    name = tag[5:5 + nl]
    p = 5 + nl
    n = struct.unpack_from("<H", tag, p)[0]
    p += 2
    if n == 0:  # device font reference, no glyph data
        return {"id": fid, "flags": flags, "lang": lang, "name": name, "shapes": [], "codes": [], "layout": None}
    wide_off = bool(flags & 0x08)
    of, osz = ("<I", 4) if wide_off else ("<H", 2)
    offs = [struct.unpack_from(of, tag, p + i * osz)[0] for i in range(n + 1)]
    shapes = [tag[p + offs[i]:p + offs[i + 1]] for i in range(n)]
    q = p + offs[n]
    if not flags & 0x04:
        raise ValueError("expected wide codes")
    codes = list(struct.unpack_from("<%dH" % n, tag, q))
    q += 2 * n
    font = {"id": fid, "flags": flags, "lang": lang, "name": name, "shapes": shapes, "codes": codes, "layout": None}
    if flags & 0x80:
        asc, desc, lead = struct.unpack_from("<hhh", tag, q)
        q += 6
        adv = list(struct.unpack_from("<%dh" % n, tag, q))
        q += 2 * n
        bounds = []
        for _ in range(n):
            r = BitReader(tag, q)
            nb = r.ub(5)
            bounds.append((r.sb(nb), r.sb(nb), r.sb(nb), r.sb(nb)))  # xmin, xmax, ymin, ymax
            q = r.align()
        kc = struct.unpack_from("<H", tag, q)[0]
        q += 2
        kern = [struct.unpack_from("<HHh", tag, q + 6 * i) for i in range(kc)]
        q += 6 * kc
        font["layout"] = {"ascent": asc, "descent": desc, "leading": lead, "advance": adv,
                          "bounds": bounds, "kerning": kern}
    if q != len(tag):
        raise ValueError("trailing data in DefineFont3: %d != %d" % (q, len(tag)))
    return font


def encode_rect(xmin, xmax, ymin, ymax):
    w = BitWriter()
    nb = sbits(xmin, xmax, ymin, ymax)
    w.ub(5, nb)
    for v in (xmin, xmax, ymin, ymax):
        w.sb(nb, v)
    return w.bytes()


def encode_font3(font):
    n = len(font["shapes"])
    wide_off = 2 * (n + 1) + sum(len(s) for s in font["shapes"]) > 0xFFFF
    flags = (font["flags"] & ~0x08) | (0x08 if wide_off else 0)
    of, osz = ("<I", 4) if wide_off else ("<H", 2)
    out = bytearray(struct.pack("<HBBB", font["id"], flags, font["lang"], len(font["name"])))
    out += font["name"]
    out += struct.pack("<H", n)
    off = osz * (n + 1)
    for s in font["shapes"]:
        out += struct.pack(of, off)
        off += len(s)
    out += struct.pack(of, off)
    for s in font["shapes"]:
        out += s
    out += struct.pack("<%dH" % n, *font["codes"])
    L = font["layout"]
    if L:
        out += struct.pack("<hhh", L["ascent"], L["descent"], L["leading"])
        out += struct.pack("<%dh" % n, *L["advance"])
        for b in L["bounds"]:
            out += encode_rect(*b)
        out += struct.pack("<H", len(L["kerning"]))
        for k in L["kerning"]:
            out += struct.pack("<HHh", *k)
    return bytes(out)


def parse_align_zones(tag, n):
    fid, hint = struct.unpack_from("<HB", tag, 0)
    zones, p = [], 3
    for _ in range(n):
        size = 1 + 4 * tag[p] + 1
        zones.append(tag[p:p + size])
        p += size
    if p != len(tag):
        raise ValueError("unexpected DefineFontAlignZones size")
    return fid, hint, zones


def encode_align_zones(fid, hint, zones):
    return struct.pack("<HB", fid, hint) + b"".join(zones)
