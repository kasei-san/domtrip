#!/usr/bin/env python3
"""cram-sheet.md の観光地理リスト ＋ tools/src/geo_spots.tsv（座標）→ geo_quiz_data.js（window.GEO_QUIZ）。

3D日本地図 japan-map.html の観光地当てクイズ用。座標は japan_geo.js と同じ投影（沖縄は枠へ移動）にそろえる。
座標が項目の県の外（かつ5km以上離れている or 別の県の中）ならエラーにして、県違いの問題を作らない。
"""
import io
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_japan_geo as jg  # noqa: E402
from build_ox_data import parse_geo, pref_label  # noqa: E402

ROOT = jg.ROOT
SPOTS_TSV = os.path.join(ROOT, "tools", "src", "geo_spots.tsv")
OUT = os.path.join(ROOT, "geo_quiz_data.js")
NEAR_DEG = 0.05  # 県の輪郭からこれ以内なら可（小島は地図データから省かれている／海沿いの名所のため）


def load_spots():
    spots = {}
    with io.open(SPOTS_TSV, encoding="utf-8") as f:
        for no, ln in enumerate(f, 1):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            if ln.count("\t") != 1:
                sys.exit(f"geo_spots.tsv {no}行目: 「項目名<TAB>座標」の形になっていない")
            name, coords = ln.split("\t")
            pts = [] if coords == "-" else [tuple(map(float, c.split(","))) for c in coords.split(";")]
            spots[name] = pts
    return spots


def load_outlines():
    """県ごとの外周リング（経緯度・島を省かない）。"""
    with open(jg.SRC, encoding="utf-8") as f:
        topo = json.load(f)
    arcs = jg.decode_arcs(topo)
    out = {}
    for g in topo["objects"]["japan"]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        out[g["properties"]["nam_ja"]] = (g["properties"]["id"], [jg.ring_coords(arcs, p[0]) for p in polys])
    return out


def inside(pt, ring):
    x, y = pt
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def dist(pt, ring):
    px, py = pt
    kx = math.cos(math.radians(py))
    best = 1e9
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        ax, ay, bx, by = (x1 - px) * kx, y1 - py, (x2 - px) * kx, y2 - py
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def main():
    spots = load_spots()
    outlines = load_outlines()
    items, errors, near, used = [], [], [], set()
    for _region, prefs in parse_geo():
        for pref, places in prefs:
            full = pref_label(pref)
            pid, rings = outlines[full]
            for place in places:
                if place not in spots:
                    errors.append(f"{place}: geo_spots.tsv に座標がない")
                    continue
                used.add(place)
                pts = []
                for lat, lon in spots[place]:
                    p = (lon, lat)
                    if not any(inside(p, r) for r in rings):
                        others = [n for n, (_, rs) in outlines.items() if n != full and any(inside(p, r) for r in rs)]
                        d = min(dist(p, r) for r in rings)
                        if others or d > NEAR_DEG:
                            errors.append(f"{place}（{full}）: 座標 {lat},{lon} が{others[0] if others else '県外'}にある")
                            continue
                        near.append(place)
                    shift = jg.OKINAWA_SHIFT if pid == jg.OKINAWA_ID else (0, 0)
                    pts.append(list(jg.project(lon, lat, shift)))
                m = re.search(r"[（(](.*?)[）)]", place)
                items.append({
                    "name": re.sub(r"[（(].*?[）)]", "", place).strip(),
                    "hint": m.group(1) if m else "",
                    "pref": full, "prefId": pid, "points": pts,
                })
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=1))
        sys.exit(1)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// 自動生成: python3 tools/build_geo_quiz.py（手で編集しない。座標は tools/src/geo_spots.tsv）\n")
        f.write("window.GEO_QUIZ = " + json.dumps(items, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(json.dumps({"items": len(items), "withPoints": sum(1 for i in items if i["points"]),
                      "noPoints": [i["name"] for i in items if not i["points"]], "nearEdge": near,
                      "unusedSpots": sorted(set(spots) - used)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
