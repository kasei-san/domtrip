#!/usr/bin/env python3
"""tools/src/japan.topojson → japan_geo.js（window.JAPAN_GEO）を生成する。

出典: 地球地図日本（国土地理院）を dataofjapan/land が都道府県別 TopoJSON に変換したもの
      https://github.com/dataofjapan/land
3D日本地図ページ japan-map.html 用。沖縄県は天気図のように左上の枠へ移し、
東京都の小笠原諸島など北緯30度より南の島は本土の縮尺が潰れるので省く。
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "src", "japan.topojson")
OUT = os.path.join(ROOT, "japan_geo.js")

LON0, LAT0 = 137.0, 37.0
KX = math.cos(math.radians(LAT0))
OKINAWA_ID = 47
TOKYO_ID = 13
# 沖縄県の移動量（経度・緯度の度数で。北西の日本海側の枠に収める）
OKINAWA_SHIFT = (3.2, 13.8)
MIN_AREA = 0.0004  # 度^2 未満の小島は省く（約 4km^2 相当。数を減らしてブラウザを軽くする）

REGIONS = {
    "北海道": [1], "東北": [2, 3, 4, 5, 6, 7], "関東": [8, 9, 10, 11, 12, 13, 14],
    "中部": [15, 16, 17, 18, 19, 20, 21, 22, 23], "近畿": [24, 25, 26, 27, 28, 29, 30],
    "中国": [31, 32, 33, 34, 35], "四国": [36, 37, 38, 39], "九州・沖縄": [40, 41, 42, 43, 44, 45, 46, 47],
}


def decode_arcs(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def ring_coords(arcs, idxs):
    ring = []
    for i in idxs:
        pts = arcs[i] if i >= 0 else arcs[~i][::-1]
        ring.extend(pts if not ring else pts[1:])
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring.pop()
    return ring


def area(ring):
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        s += x1 * y2 - x2 * y1
    return s / 2


def project(lon, lat, shift=(0, 0)):
    return (round((lon + shift[0] - LON0) * KX, 3), round(lat + shift[1] - LAT0, 3))


def main():
    topo = json.load(open(SRC, encoding="utf-8"))
    arcs = decode_arcs(topo)
    region_of = {pid: r for r, ids in REGIONS.items() for pid in ids}
    prefs = []
    stats = {}
    for g in topo["objects"]["japan"]["geometries"]:
        pid = g["properties"]["id"]
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        shift = OKINAWA_SHIFT if pid == OKINAWA_ID else (0, 0)
        out = []
        for poly in polys:
            rings = [ring_coords(arcs, r) for r in poly]
            outer = rings[0]
            if len(set(outer)) < 3 or abs(area(outer)) < MIN_AREA:
                continue
            clat = sum(p[1] for p in outer) / len(outer)
            if pid == TOKYO_ID and clat < 30:
                continue
            holes = [h for h in rings[1:] if len(set(h)) >= 3 and abs(area(h)) > 0]
            out.append([[project(*p, shift) for p in r] for r in [outer] + holes])
        props = g["properties"]
        prefs.append({"id": pid, "name": props["nam_ja"], "region": region_of[pid], "polygons": out})
        stats[props["nam_ja"]] = [len(out), sum(len(r) for p in out for r in p)]
    prefs.sort(key=lambda p: p["id"])

    # 沖縄の枠（天気図の区切り線）を沖縄県の外接矩形から作る
    oki = [pt for poly in prefs[OKINAWA_ID - 1]["polygons"] for r in poly for pt in r]
    xs, ys = [p[0] for p in oki], [p[1] for p in oki]
    m = 0.35
    inset = [round(min(xs) - m, 3), round(min(ys) - m, 3), round(max(xs) + m, 3), round(max(ys) + m, 3)]

    data = {
        "source": "地球地図日本（国土地理院）/ dataofjapan/land",
        "projection": {"lon0": LON0, "lat0": LAT0, "kx": round(KX, 6)},
        "okinawaInset": inset,
        "prefectures": prefs,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// 自動生成: python3 tools/build_japan_geo.py（手で編集しない）\n")
        f.write("// 出典: 地球地図日本（国土地理院） https://github.com/dataofjapan/land\n")
        f.write("window.JAPAN_GEO = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    total = sum(v[1] for v in stats.values())
    print(json.dumps({"prefectures": len(prefs), "points": total, "bytes": os.path.getsize(OUT),
                      "okinawaInset": inset, "perPref": stats}, ensure_ascii=False))


if __name__ == "__main__":
    main()
