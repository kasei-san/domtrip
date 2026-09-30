#!/usr/bin/env python3
"""観光地当てクイズの写真を Wikipedia から探し、記事名とサムネイルURLを tools/src/geo_images.json に保存する。

画像そのものはリポジトリに置かず、ページ表示時に Wikimedia から読む（記事へのリンクを出典として表示）。
記事名は項目名（括弧と「・」以降を除く）で引き、写真がなければ全文検索の1件目を使う。
結果がずれていたら geo_images.json の title を直して --only <項目名> で取り直す（県の記事に当たると答えがばれるので注意）。
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_ox_data import parse_geo, pref_label  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "src", "geo_images.json")
API = "https://ja.wikipedia.org/w/api.php"
UA = {"User-Agent": "domtrip-quiz-build/1.0 (https://kasei-san.com/domtrip/)"}


def api(**params):
    params.update(format="json", formatversion="2")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


# 地図・図表の画像は県の位置がばれるので使わない
NG_IMAGE = re.compile(r"map|relief|topographic|_adm|\.svg|blocks", re.I)


PREF_TITLES = {pref_label(p) for _r, ps in parse_geo() for p, _ in ps}


def pick(pages):
    for p in pages:
        if p["title"] in PREF_TITLES:  # 県の記事の写真は答えそのもの
            continue
        if "thumbnail" in p and not NG_IMAGE.search(urllib.parse.unquote(p["thumbnail"]["source"])):
            return p["title"], p["thumbnail"]["source"]
    return None


def by_title(title):
    d = api(action="query", titles=title, redirects=1, prop="pageimages", piprop="thumbnail", pithumbsize=800)
    return pick(d["query"]["pages"])


def by_search(q):
    d = api(action="query", generator="search", gsrsearch=q, gsrlimit=1,
            prop="pageimages", piprop="thumbnail", pithumbsize=800)
    return pick(d.get("query", {}).get("pages", []))


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    out = dict(old)
    for _region, prefs in parse_geo():
        for pref, places in prefs:
            for place in places:
                if only and place != only:
                    continue
                if not only and place in old:
                    continue
                title = old.get(place, {}).get("title") or re.split(r"[・]", re.sub(r"[（(].*?[）)]", "", place))[0].strip()
                hit = by_title(title) or (None if only else by_search(f"{title} {pref_label(pref)}"))
                out[place] = {"title": hit[0], "thumb": hit[1]} if hit else {"title": title, "thumb": None}
                print(place, "→", out[place]["title"], "" if hit else "（写真なし）")
                time.sleep(0.2)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
