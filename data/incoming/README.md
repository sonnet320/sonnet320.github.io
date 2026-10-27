# GPTの価格CSVの取り込み

**このフォルダに、GPTのCSVを直接アップロードしないでください。** リポジトリは公開なので、置いたCSVは、載せない店舗の行を消す前の状態のまま履歴に残ります。

## 取り込みの流れ

1. そねっとさんが、GPTの出したCSV(例 `prices_20261009.csv`)をチャットで Claude に渡す
2. Claude が手元で、自動更新(`.github/workflows/update-prices.yml`)と同じ処理を行う
   - `python tools/make_prices.py --out data --strip-inputs CSVのパス`(載せない店舗の行を消し、`data/prices.json` と `data/prices_long.csv` を作り直す)
   - `python tools/make_price_map.py`
   - 処理したCSVを `data/archive/` に置く
3. Claude が、消したあとのCSVと作り直したデータだけを PR にする。そねっとさんが確認して Merge する

## 決まり

- CSVに決まり違反(購入可なのに価格が空、など)があると変換は止まります。Claude が中身を確かめて、GPTに直してもらうか相談します。
- 同じ日付のCSVをもう一度取り込むと、新しい方で置き換わります。
- アプライド(2026-10-14)とツクモ(2026-10-15)の行は載せません(利用規約のため)。GPTへの価格調査の依頼は、アーク・ドスパラ・パソコン工房の3店だけにし、`_dev/gpt_price_research.md` の決まり(サイトに負荷をかけない調べ方)を守ってもらってください。製品リスト `_dev/price_research_products.csv` を添付します。
- 扱うカテゴリは CPU・GPU・メモリ・SSD・ファン・CPUクーラー・ケースです。少しずつ(20〜30製品ずつ)調べたCSVを何回かに分けて取り込んでかまいません。
- 自動更新のワークフローは、このフォルダにCSVが置かれたときだけ動きます。上の流れでは、このフォルダは空のままなので動きません(予備として残しています)。
