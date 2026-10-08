# ページの作り直し(製品の追加 → あなたの許可 → サイトに反映)

## 分担
- **製品の追加(ファン・クーラー・ケース):Claude。** PC構成シートの本文 `src/pc-sheet.html` を直す。
- **価格の調査:GPT。** これまでどおり、CSVを `data/incoming/` に置く(`.github/workflows/update-prices.yml` が `data/prices.json` を更新する)。
- **公開の許可:あなた。** プルリクエストを Merge したときだけサイトが変わる。

## 流れ
1. Claude が `src/pc-sheet.html` を直して、`main` 以外のブランチ(例 `claude/add-noctua-fan`)に push する。
2. GitHub Actions(`.github/workflows/build-pages.yml`)が、そのブランチで
   `pc-sheet/index.html`(PC構成シート)と `fan-ranking/index.html`(ファン・クーラーランキング)を作り直して保存する。
3. 同じワークフローが `main` へのプルリクエストを作る。この時点ではサイトは変わらない。
4. あなたがプルリクエストの中身を見て **Merge** → 1〜2分でサイトに反映。反映したくなければ Close。
   プルリクエストでは、ページが `src/pc-sheet.html` から作り直した最新のものかも自動で確かめる(古ければ赤い×)。

※ プルリクエストを自動で作るには、リポジトリの Settings → Actions → General →
「Allow GitHub Actions to create and approve pull requests」をオンにする(一度だけ)。オフのままなら、GitHub の画面から作る。

## ファイル
| ファイル | 中身 |
|---|---|
| `src/pc-sheet.html` | PC構成シートの本文(Claude の Artifact と同じもの)。製品のデータ(FAN_DB・COOLERS・CASE_MODELS など)もここ |
| `tools/build/build_pages.py` | 上の2ページを作る。`--check` で最新か確認、`--artifact-ranking out.html` で Artifact 版ランキング |
| `tools/build/sheet-bridge.js` | サイトに埋め込むときのつなぎ(おすすめBTO・ランキングからの受け渡し) |
| `tools/build/ranking-template.html`・`extract_data.cjs` | ランキングのひな形と、シートからデータを取り出すスクリプト |
| `tools/build/site_theme.py` | ランキングをサイトの色(生成り・深緑)にする |

手元で作るとき:`python3 tools/build/build_pages.py`(Python 3 と Node.js が必要)。

## 気をつけること
- `pc-sheet/index.html`・`fan-ranking/index.html` は直接直さない(次に作り直したとき消える)。直すのは `src/` と `tools/build/`。
- Claude の Artifact(PC構成シート・ランキング)はサイトとは別物。Claude が同じ本文で更新する。
- パーツ価格シート(`price-sheet/`)はこの仕組みの対象外(価格のCSVから動く)。
