# PC構成シート Webサイト

YouTubeチャンネル「そねっとの趣味部屋」の Web ツールです。https://sonnet320.github.io/ で公開しています。

温度・風量・騒音・評価・価格は目安です。ケースの形や室温、負荷で結果は変わります。実機での確認と合わせてお使いください。

## ページ

| URL | 中身 | ファイル |
|---|---|---|
| `/` | ホームページ。PC構成シートと、おすすめBTOのカード・計算済みのエアフロー図 | `index.html`、`assets/` |
| `/pc-sheet/` | PC構成シート本体(単体でも開けます) | `pc-sheet/index.html` |
| `/prices/` | パーツ価格(CPU・GPU・SSD などの価格推移) | `prices/`、`price-sheet/` |
| `/ranking/` | ファン・CPUクーラーのランキング | `ranking/`、`fan-ranking/` |

`pc-sheet/?preset=構成ID` のように、構成を指定してシートを開くこともできます。

## 更新のしかた

変更はブランチを作って Pull Request にし、そねっとさんが確認して Merge します。main に直接は書き込みません。作業の決めごとや経緯は `_dev/HANDOFF.md` にあります。

### おすすめBTO(`config.json`)

| 項目 | 内容 |
|---|---|
| id | 重複しない構成ID(半角英数字・ハイフン) |
| name / shop / model / grade | 表示名・ショップ・モデル・グレード |
| cpu / gpu / memory / ssd / cooler / case | カードに表示する仕様 |
| price / priceDate | 税込価格と、確認した日付。価格を載せるときは日付も必ず入れる |
| priceBefore / priceBeforeDate | 値上がりしたときの、値上がり前の価格とその日付。カードの価格の下に「値上がり前」と表示する(今の価格より高いときは表示しない) |
| tier | 価格帯のタブ。20(20万円以下)/ 30(30万円以下)/ 40(40万円以下)/ plus(40万円超) |
| url / affiliateUrl / pr | 販売ページ・アフィリエイトURL・PR対象かどうか |
| sample / genericCase | 表示サンプルか、汎用ケースで計算したか |
| preset / result | 構成データ(`presets/`)と計算結果(`results/`)のパス |
| priceNote / simulationNote | 価格と計算条件の補足 |

構成を追加するとき:

1. シートで構成・ケース・ファン・室温・負荷を入力し、「データをコピー」で得たデータを `presets/構成ID.json` の `state` に入れます。
2. 「計算結果を書き出す」で 2D の計算結果(6秒計算し、続く2秒を平均)を出し、`presetId` を加えて `results/構成ID.json` に置きます。図は同じ名前の画像ファイルにします。
3. `config.json` に追加します。ケースの情報が足りず計算できないときは、結果を `"status": "not_computed"` にして理由を `note` に書きます。

冷却結果の有無にかかわらず、BTOをPC構成シートへ読み込む機能を維持します。冷却情報が不足している場合も、確認済みの部品構成・価格・備考は読み込めるようにします。未確認の冷却設定と製品の確認済み仕様を区別し、`fans: []` は配置未確認として扱います。

### シートの計算を変えたとき

温度の計算(モデル)を変えたら、掲載中のおすすめBTOの計算結果も同じ PR で計算し直します。計算結果の `modelVersion` が、シートの今の版(`pc-sheet/index.html` の `DIAG_VER`)と同じになっているか確認してください。

### 価格

- GPT が調べた価格の CSV は、`data/incoming/` に直接置かず、Claude が手元で変換して(載せない店舗の行を消してから)`data/prices.json` と `data/prices_long.csv` を作り直し、PR にします(手順は `data/incoming/README.md`)。
- PC構成シートの目安の価格も、開いたときに `data/prices.json` の最新の在庫ありの最安値を読みます。部品の対応は `data/price_map.json`(`tools/make_price_map.py` が作る)で、価格の自動更新のたびに作り直されます。シートに部品を追加したときは、このスクリプトを実行し直します。
- 価格グラフに使うのは購入可能価格(在庫あり)だけです。

## 注意

- 計算は 2D(5mm 格子)です。3D は WebGPU が使えるブラウザ(PC の Chrome・Edge)で動きます。
- 入力した構成はブラウザに保存されます。
- 外部ファイルを読み込むため、`index.html` を直接ダブルクリックでは全機能が動きません。公開URLか、このフォルダで `python -m http.server 8000` を実行して http://localhost:8000/ で確認します。

## 同梱ライブラリ・フォント

Three.js r128 と、Zen Kaku Gothic New / JetBrains Mono のフォントを同梱しています。各ライセンスは `assets/` にあります。
