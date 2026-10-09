"""Draws the app icons (a yellow price tag on the site's green) as PNGs, with no image library needed.
Run: python -I tools/make_icons.py   → icons/icon-192.png, icons/icon-512.png, icons/apple-touch-icon.png
"""
import math
import pathlib
import struct
import zlib

GREEN = (31, 107, 79)
YELLOW = (255, 216, 77)
INK = (42, 35, 0)
OUT = pathlib.Path(__file__).resolve().parents[1] / "icons"


def inside_round_rect(x, y, x0, y0, x1, y1, r):
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def color_at(u, v):
    """Colour at (u, v) in a 0..1 square. The tag is rotated 45°, with a hole and two price lines."""
    # rotate around the centre by -45° so the tag can be drawn axis-aligned
    a = math.radians(-45)
    x, y = u - 0.5, v - 0.5
    rx, ry = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
    in_tag = inside_round_rect(rx, ry, -0.30, -0.17, 0.30, 0.17, 0.05)
    # pointed end on the left
    in_point = -0.42 <= rx <= -0.28 and abs(ry) <= (rx + 0.42) / 0.14 * 0.17
    if in_tag or in_point:
        if (rx + 0.27) ** 2 + ry ** 2 <= 0.035 ** 2:
            return GREEN  # string hole
        if -0.14 <= rx <= 0.22 and (abs(ry + 0.05) <= 0.022 or (abs(ry - 0.06) <= 0.022 and rx <= 0.10)):
            return INK  # price lines
        return YELLOW
    return GREEN


def png(size, path, pad=0.0):
    ss = 4  # supersampling for smooth edges
    rows = []
    for py in range(size):
        row = bytearray([0])
        for px in range(size):
            acc = [0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    u = (px + (sx + 0.5) / ss) / size
                    v = (py + (sy + 0.5) / ss) / size
                    u, v = (u - pad) / (1 - 2 * pad), (v - pad) / (1 - 2 * pad)
                    c = color_at(u, v) if 0 <= u <= 1 and 0 <= v <= 1 else GREEN
                    for i in range(3):
                        acc[i] += c[i]
            row += bytes(round(a / (ss * ss)) for a in acc)
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")
    path.write_bytes(data)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    png(192, OUT / "icon-192.png", pad=0.08)       # padding keeps the tag inside Android's round mask
    png(512, OUT / "icon-512.png", pad=0.08)
    png(180, OUT / "apple-touch-icon.png", pad=0.05)
    print("wrote", sorted(p.name for p in OUT.iterdir()))
