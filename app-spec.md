# オフライン学習アプリ 仕様（index.html）

## 目的
通勤中の不安定回線でも使える、**完全オフライン**の間隔反復クイズアプリ。Ankiの代替（iPhone課金不要）。素材は既存の `問題集/`（R03〜R07×3科目・432問）と `cram-sheet.md`。学習履歴は `localStorage` に保存し、クリップボード経由で `dashboard.html` に反映する。

## 成果物
1. **`index.html`** — 問題データ・JS・CSSを全て埋め込んだ単一HTML（外部CDN/フォント/ライブラリ不使用）。
2. **`dashboard.html`（既存に追記）** — エクスポートJSONを貼ると正答率等が更新されるインポート欄。
3. **`tools/build_app_data.py`** — md をパースして問題データを生成し `index.html` に埋め込む再ビルド用スクリプト。

## カードの種類（ビルド時に md → JS の `CARDS` 配列へ）
| 種類 | 元データ | 内容 |
|------|---------|------|
| **mcq（4択）** | 科目1・2 全設問＋科目3で選択肢のある設問 | `{id,subject,year,qno,topic,stem,choices:[{k,text}],answer:[...],explanation}` |
| **review（解答リビュー）** | 科目3の図表依存設問（選択肢なし） | 要点＋正解＋解説を表示→「できた/できない」自己採点 |
| **flash（暗記カード）** | `cram-sheet.md` の地理・数字 | front/back めくり式 |

パーサ仕様（実測済みの揺れに対応）:
- 選択肢マーカー: `^-?\s*[アイウエ][.．、]`（半角/全角ピリオド・先頭「- 」有無を吸収）
- 正解: `\*\*正解[:：]\s*([アイウエ・]+)`（`ア・エ` 等の複数正解は `・` で分割）
- `<details>` 内の解説本文も取り込む
- `【正解要確認】` が残る設問（R06科目3問84）は `flagged:true` を立てアプリ上で注意表示

## 機能
- **モード**: ①過去問4択 ②解答リビュー（科目3図表問）③暗記カード ④苦手復習（box1のみ）
- **絞り込み**: 科目（1/2/3）・年度
- **間隔反復（固定間隔SRS／Leitner風）**: 各札に `box(1〜5)` と `due(次回出題日)`。正解→box+1（間隔 **1→3→7→16→35日**）、不正解→box1（翌日）。セッションは **due札を優先**し、**1日の新規札に上限**（既定20枚・変更可）を設けて出題（滞留での一気破綻を防ぐ）
- **採点**: 4択は選択→正誤判定＋根拠解説。**複数正解の設問は checkbox 複数選択＋「解答」ボタンで完全一致を判定**（単一正解はラジオ的に1つ選択）。review/flashは「できた/できない」自己申告。**自己申告（review/flash）と4択の正答率は統計を分けて表示**（信頼度が違うため）
- **統計（アプリ内）**: 科目別 正答率（correct/answered）・到達度（distinct correct/全札）・周回数（延べ回答/全札）・本日のdue数・連続学習日数

## 永続化（file:// の不確実性を前提に設計）
`localStorage['domtrip_v1']` に保存。**ただし file:// の localStorage は仕様上未定義**（ブラウザ差あり。特にiOS Safariでは Files から開く・ファイルを移動/複製/リネームすると別URL扱いになり進捗が分離・消失し得る）。これを前提に:
- 保存は **try/catch 必須**。`setItem` が `SecurityError` 等で失敗したら **「一時セッションモード」**（メモリ保持のみ・閉じると消える）に切替え、画面上部に警告を出す。
- 起動時に保存可否を診断（テスト書込→読出）し、不可なら大きく注意表示＋「JSONファイルでバックアップしてね」を促す。
- **進捗の唯一の正本はエクスポートJSON**と位置づける（localStorageはあくまでキャッシュ）。だから移行・バックアップ経路を堅牢にする（下記）。

保存データ構造:
```json
{ "schemaVersion": 1, "appId": "domtrip-quiz",
  "cards": {"<id>": {"box":1,"due":"YYYY-MM-DD","seen":N,"correct":N,"wrong":N,"last":"YYYY-MM-DD"}},
  "daily": [{"date":"YYYY-MM-DD","answered":N,"correct":N}],
  "streak": N, "lastStudied": "YYYY-MM-DD" }
```

## エクスポート / インポート（主経路＝JSONファイル、副経路＝クリップボード）
file:// では clipboard API もユーザー操作内＆secure context制約で不安定なため、**壊れにくいファイル経由を主経路**にする。
- **エクスポート（主）**: `Blob` + `<a download="domtrip進捗_YYYY-MM-DD.json">` で **JSONファイルとして保存**。iOSでも「ファイル」アプリに保存できる。
- **エクスポート（副・任意）**: 「クリップボードにコピー」ボタン。①`navigator.clipboard.writeText`（ユーザー操作ハンドラ内で試行）→ ②失敗時は textarea に表示し `select()` で全選択状態にして手動コピー（長押しコピー手順もUI明示）。`execCommand('copy')` はベストエフォートのみ。
- **アプリへのインポート（復元）**: `<input type="file">` でJSON読込（主）＋テキスト貼り付け欄（副）。`schemaVersion`/`appId`/`cardCount` を検証し、**全フィールド（box/due/seen/correct/wrong/last/daily/streak/lastStudied）をそのまま復元**（再構成でなく完全復元）。壊れたJSONは弾いて元データを残す。
- **ダッシュボード反映**: `dashboard.html` に **ファイル読込（主）＋貼り付け欄（副）** を追加。読み込んだ進捗から科目別に集計して `DATA` 更新＋再描画＋ダッシュボード側 localStorage に保存。

### エクスポートJSONスキーマ（アプリ⇔ダッシュボード共通）
アプリの保存データに、ダッシュボード用の集計と検証情報を足したもの。**完全復元できるよう cards のフルstate を含める**。
```json
{ "schemaVersion":1, "appId":"domtrip-quiz", "exportedAt":"YYYY-MM-DD", "cardCount":N,
  "subjects": { "科目1": {"answered":N,"correct":N,"correctDistinct":N}, "科目2": {...}, "科目3": {...} },
  "streak": N, "lastStudied":"YYYY-MM-DD",
  "daily": [{"date":"YYYY-MM-DD","answered":N,"correct":N}],
  "cards": { "<id>": {"box":1,"due":"YYYY-MM-DD","seen":N,"correct":N,"wrong":N,"last":"YYYY-MM-DD"} } }
```
- ダッシュボードは `subjects`・`daily`・`streak` を使用。`cards`（フルstate）はアプリ完全復元用。
- 指標名はアプリ・ダッシュボード・既存 `進捗データ.json` で統一: **answered=延べ回答 / correct=延べ正答 / correctDistinct=正解した異なり札数（到達度の分子）**。

## 実装ステップ
1. `tools/build_app_data.py`: md パース→問題データ生成（件数・型別内訳をログ、1〜2問を目視検証）
2. `index.html`: CARDS埋め込み・UI・SRS・localStorage・export/import・統計
3. `dashboard.html`: インポート欄を追加（共通スキーマ）
4. `CLAUDE.md`: アプリの使い方・再ビルド手順・エクスポート/インポートの流れを追記

## 検証（オフライン動作）
- ブラウザで開き4択を数問解く→正誤判定・解説・統計更新、リロードで進捗保持（localStorage）
- エクスポート→ダッシュボードに貼付→正答率・到達度・周回が更新される
- 複数正解問題の判定／科目3リビュー表示／暗記カードめくり を確認

## ✅ 配信方針（決定）
**GitHub Pages で PWA 配信**に決定。GitHub Pagesに `index.html`＋`app_data.js`＋`sw.js`＋`manifest.webmanifest` を置き、初回オンラインで開く→「ホーム画面に追加」→Service Workerでオフライン動作。iPhoneでも localStorage が正常動作する。Dropbox/file:// 運用は採用しない（iOSで保存不可のため）。

## ⚠️ iPhone運用の重要事実（実機制約・要確認済み）
- **iOS Safariは file:// でHTMLを開くと localStorage アクセス時に `SecurityError` を投げる**（DOM例外18）。Dropbox→ファイルアプリ→開く運用では**進捗が保存できない／毎回消える**。Quick Lookプレビューもアプリとして安定動作しない。
- → iPhoneでオフライン＋進捗保持を両立する堅牢な道は **「httpsで配信し"ホーム画面に追加"（PWA化）」**:
  - GitHub Pages等の無料https に同じHTMLを置く → 初回だけオンラインで開く → **Service Workerでオフラインキャッシュ** → 以降は機内モードでも動作。
  - secure context なので **localStorage 正常動作・clipboard も利用可**。データは端末内に留まる（公開されるのはHTMLのみ、過去問は公開情報）。
- アプリ側の耐性設計（どの経路でも壊れない）:
  - 起動時に localStorage 可否を診断 → 不可なら**セッションモード**＋警告。
  - **進捗の正本はエクスポートJSONファイル**。localStorageが使えない環境でも、JSON保存/読込で学習を継続できる（毎回 開始時に読込→終了時に保存、の運用も可）。
- PC・Android（file://やローカル）では localStorage が概ね動くため、単一HTMLのまま使える。

参照: [Apple Forums: Safari SecurityError accessing localStorage](https://developer.apple.com/forums/thread/87778) ／ [Apple Community: open local HTML on iPhone](https://discussions.apple.com/thread/255549790) ／ [iOS Safari localStorage in private/file mode](https://jonathanmh.com/p/use-ios-safari-localstorage-sessionstorage-private-mode/)

## 実装上の技術メモ（Codexレビュー反映）
- カードデータは JS直書きでなく **`<script type="application/json" id="cards">…</script>`** に埋め込み、起動時に `JSON.parse`。描画は **常に1問だけDOM化**（全件DOM生成しない）。
- 432問テキスト主体なのでサイズは数百KB〜実用範囲。問題なし。
- 配布の最善手は `http://localhost` の簡易サーバだが、要件が「ファイルを開くだけ」なので **file:// で動かしつつ、保存の不確実性はJSONバックアップで担保**する方針。

## 制約
- 完全オフライン（単一HTMLに全埋め込み、外部CDN/フォント/ライブラリ依存ゼロ）
- 既存の指標定義（到達度＝正答数÷全過去問数、周回＝延べ回答÷全札、正答率＝correct÷answered）と整合させる
- file:// の localStorage は保証されない前提。**進捗の正本はエクスポートJSON**、localStorageはキャッシュ。
