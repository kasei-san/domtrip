#!/usr/bin/env python3
# ox-cards.md（手書きの1行暗記＋○×）と cram-sheet.md の観光地理リスト（自動生成）から
# ox.html 用の ox_data.js を生成する。
# 出力: ox_data.js  (const OX_DATA = {...};)
#
# カードIDは ox-cards.md の見出し（### <id> <title>）に書かれた明示IDをそのまま使う。
# 地理カードは "geo-<都道府県>" で固定。どちらも位置に依存しないので、途中に追加しても進捗はずれない。
import io, os, re, json, sys, datetime, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_MD = os.path.join(ROOT, "ox-cards.md")
CRAM_MD = os.path.join(ROOT, "cram-sheet.md")
OUT = os.path.join(ROOT, "ox_data.js")

SECTION_RE = re.compile(r"^##\s+(科目[123])\s*$")
CARD_RE = re.compile(r"^###\s+([A-Za-z0-9\-]+)\s+(.+?)\s*$")
FACT_RE = re.compile(r"^覚える[:：]\s*(.+?)\s*$")
STMT_RE = re.compile(r"^-\s*([○×])\s+(.+?)\s*$")


def parse_cards():
    cards, errors = [], []
    subject, cur = None, None
    in_body = False  # 「## 科目1」以降だけを読む（冒頭の書式説明を無視する）
    with io.open(CARDS_MD, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            ln = raw.rstrip("\n")
            m = SECTION_RE.match(ln)
            if m:
                subject, in_body = m.group(1), True
                continue
            if not in_body:
                continue
            m = CARD_RE.match(ln)
            if m:
                cur = {"id": m.group(1), "title": m.group(2), "subject": subject, "fact": "", "statements": [], "gen": False}
                cards.append(cur)
                continue
            if cur is None:
                continue
            m = FACT_RE.match(ln)
            if m:
                if cur["fact"]:
                    errors.append(f"L{lineno}: {cur['id']} に覚える行が2つある")
                cur["fact"] = m.group(1)
                continue
            m = STMT_RE.match(ln)
            if m:
                cur["statements"].append({"text": m.group(2), "answer": m.group(1) == "○"})
    return cards, errors


# ---- 観光地理（cram-sheet.md）から自動生成 ----
GEO_HEAD = "### 観光地理 暗記リスト"
REGION_RE = re.compile(r"^####\s+(.+?)\s*$")
PREF_RE = re.compile(r"^-\s*\*\*(.+?)\*\*[:：]\s*(.+?)\s*$")


def pref_label(p):
    if p == "北海道":
        return p
    if p in ("京都", "大阪"):
        return p + "府"
    if p == "東京":
        return p + "都"
    return p + "県"


def parse_geo():
    regions = []  # [(region, [(pref, [places])])]
    in_geo = False
    cur_region = None
    with io.open(CRAM_MD, encoding="utf-8") as f:
        for raw in f:
            ln = raw.rstrip("\n")
            if ln.startswith("### "):
                in_geo = ln.startswith(GEO_HEAD)
                continue
            if not in_geo:
                continue
            m = REGION_RE.match(ln)
            if m:
                cur_region = (m.group(1), [])
                regions.append(cur_region)
                continue
            m = PREF_RE.match(ln)
            if m and cur_region is not None:
                pref, rest = m.group(1), m.group(2)
                places = []
                for item in rest.split("/"):
                    item = item.strip()
                    if not item:
                        continue
                    # 「（※高野山は和歌山）」のような別県注記付きの項目は誤った○になるので捨てる
                    if "（※" in item or "(※" in item:
                        continue
                    # 末尾の「※白神山地は…」注記（県境またぎ）は本体だけ残す
                    if "※" in item:
                        item = item.split("※", 1)[0].strip()
                        if not item:
                            continue
                    places.append(item)
                if places:
                    cur_region[1].append((pref, places))
    return regions


def stable_pick(key, n):
    # 生成結果を毎回同じにするため、ハッシュで決める（random は使わない）
    return int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % n


def gen_geo_cards(regions):
    cards = []
    all_pairs = [(pref, places, region) for region, lst in regions for pref, places in lst]
    place_owner = {}
    for pref, places, _ in all_pairs:
        for p in places:
            place_owner.setdefault(p, set()).add(pref)
    for pref, places, region in all_pairs:
        # ×に使う「別の県」は同じ地方から選ぶ（ひっかけとして現実的）。同地方に他県がなければ全体から
        same_region = [q for q, _, r in all_pairs if r == region and q != pref]
        pool = same_region or [q for q, _, _ in all_pairs if q != pref]
        stmts = []
        for i, place in enumerate(places):
            # 問題文では「屈斜路湖（最大カルデラ湖）」のような補足を落とす（ヒントになる／読む量を減らす）
            name = re.sub(r"[（(].*?[）)]", "", place).strip()
            if i % 2 == 0:
                stmts.append({"text": f"「{name}」は{pref_label(pref)}。", "answer": True})
            else:
                cand = [q for q in pool if q not in place_owner.get(place, set())]
                if not cand:
                    stmts.append({"text": f"「{name}」は{pref_label(pref)}。", "answer": True})
                    continue
                other = cand[stable_pick(pref + place, len(cand))]
                stmts.append({"text": f"「{name}」は{pref_label(other)}。", "answer": False})
        cards.append({
            "id": f"geo-{pref}",
            "title": f"観光地理 {pref}",
            "subject": "科目3",
            "fact": f"{pref_label(pref)}: " + " / ".join(places),
            "statements": stmts,
            "gen": True,
            "region": region,
        })
    return cards


def main():
    cards, errors = parse_cards()
    for c in cards:
        if not c["fact"]:
            errors.append(f"{c['id']}: 覚える行がない")
        if not c["statements"]:
            errors.append(f"{c['id']}: ○×問題がない")
        elif not (any(s["answer"] for s in c["statements"]) and any(not s["answer"] for s in c["statements"])):
            errors.append(f"{c['id']}: ○と×の両方を用意する（片方だけだと押す前に答えが決まる）")
    geo = gen_geo_cards(parse_geo())
    cards += geo
    n_true = sum(1 for c in cards for s in c["statements"] if s["answer"])
    n_all = sum(len(c["statements"]) for c in cards)
    if n_all and not (0.4 <= n_true / n_all <= 0.6):
        errors.append(f"全体の○比率 {n_true/n_all:.2f} が 0.4〜0.6 を外れている（×連打で解けてしまう）")
    ids = [c["id"] for c in cards]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errors.append("id 重複: " + ", ".join(dup))
    if errors:
        print("\n".join("ERROR " + e for e in errors), file=sys.stderr)
        sys.exit(1)

    data = {
        "generatedAt": datetime.date.today().isoformat(),
        "cards": cards,
    }
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("// 自動生成: python3 tools/build_ox_data.py（ox-cards.md / cram-sheet.md を編集後に再実行。手で編集しない）\n")
        f.write("const OX_DATA = ")
        f.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        f.write(";\nwindow.OX_DATA = OX_DATA;\n")

    # 集計（○×比が偏ると「×連打」で解けてしまうので、比率を出して目視確認する）
    summary = {}
    for c in cards:
        k = ("地理(自動)" if c["gen"] else c["subject"])
        s = summary.setdefault(k, {"cards": 0, "stmts": 0, "true": 0})
        s["cards"] += 1
        s["stmts"] += len(c["statements"])
        s["true"] += sum(1 for st in c["statements"] if st["answer"])
    total = {"cards": len(cards), "stmts": sum(len(c["statements"]) for c in cards)}
    total["true"] = sum(1 for c in cards for st in c["statements"] if st["answer"])
    total["trueRatio"] = round(total["true"] / total["stmts"], 2) if total["stmts"] else 0
    print(json.dumps({"out": os.path.relpath(OUT, ROOT), "perSection": summary, "total": total}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
