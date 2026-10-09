#!/usr/bin/env python3
"""GPTに渡す価格調査キット(ZIP)を作る。

usage: python3 tools/build/make_research_kit.py <出力.zip> [--date YYYY-MM-DD]

中身
  README_GPT.md        GPTへの依頼文と決まり(そのまま貼れる)
  調査対象.csv          PC構成シートに載っている製品の一覧(製品IDは価格データとシートに自動で結び付くもの)
                        優先度 A = これまで調べている製品、B = シートにあるがまだ調べていない製品
  回答テンプレート.csv   答えのCSVの列(1行目だけ)
  これまでの価格.csv     今までの調査結果(data/prices_long.csv と data/parts_long.csv)

製品IDの付け方はシート側(tools/build/link_prices.py)の結び付け方に合わせてあり、
このスクリプトは作った一覧が全部シートの製品に結び付くことを確かめてから書き出す(結び付かなければ止まる)。
製品をシートに追加したら、これを実行し直せば調査対象に入る。"""
import csv, io, json, os, re, subprocess, sys, tempfile, zipfile
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'build'))
import link_prices  # noqa: E402

STD = ['日付', 'カテゴリ', '製品ID', '製品名', '型番', '区分', '容量', '店舗',
       '購入可能価格(税込)', '在庫状況', '購入可否', '商品URL', '備考']
LIST = ['優先度', 'カテゴリ', '製品ID', '製品名', '型番', '区分', '容量', '前回の最安値(税込)', '前回の調査日', '備考']
# 単体で売られているケース(BTO専用のケースは調べない)。型番は黒。白などは備考の型番で調べてよい
RETAIL_CASES = {
    'h5flow24': ('CC-H52FB-01', '白は CC-H52FW-01'),
    's100tg': ('CA-1Q9-00S1WN-00', 'Snow Edition(白)は CA-1Q9-00S6WN-00'),
    'haf2500': ('H500G2-KGNN-S00', ''),
}


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-') or 'x'


def short_chip(name):
    return re.sub(r'^(GeForce|Radeon|Intel)\s+', '', name)


def cpu_group(name):
    m = re.match(r'(Ryzen \d|Core Ultra \d|Core i\d)', name)
    return m.group(1) if m else ''


def latest(data):
    """製品ID → (調査日, 最安値 or None, 製品)"""
    prods = {p['id']: p for p in data.get('products', [])}
    return {i: (d, p, prods.get(i, {})) for i, (d, p) in link_prices.latest_low(data).items()}


def build_rows():
    cat = link_prices.catalog()
    res = cat['research']
    known = {}
    for name in ('prices.json', 'parts.json'):
        known.update(latest(link_prices.load(name, {}) or {}))
    rows, expect = [], {}   # expect: 製品ID → (シートの種類, シートのID)

    def add(prio, category, pid, name, model, group, cap, prev, note, kind, target):
        d, p = (known[pid][0], known[pid][1]) if pid in known else (None, None)
        if p is None and prev is not None:
            d, p = '2026-10-07', prev
        rows.append(['A' if pid in known or prev is not None else prio, category, pid, name, model, group, cap,
                     p if p is not None else '', d or '', note])
        if kind:
            expect[pid] = (kind, target)

    # CPU: 価格データにあるものと、シートの目安にあるもの
    cpus = {}
    for pid, (_, _, p) in known.items():
        if p.get('category') == 'CPU':
            cpus[p['name']] = pid
    for n in cat['cpu'] + list(res.get('cpu', {})):
        cpus.setdefault(n, 'cpu-' + slug(n))
    for n, pid in sorted(cpus.items(), key=lambda x: (cpu_group(x[0]), x[0])):
        add('B', 'CPU', pid, n, '', cpu_group(n), '', res.get('cpu', {}).get(n), '', 'cpu', n)
    # GPU: シートのカード全部(カード単位で調べる)
    for c in cat['gpuCards']:
        chip = short_chip(c['chipName'])
        head = '' if c['brand'] == '玄人志向' else slug(c['brand']) + '-'
        pid = 'gpu-' + head + slug(c['series']) + '-' + slug(chip)
        name = f"{c['brand']} {c['series']} {chip}"
        add('B', 'GPU', pid, name, '', chip, '', res.get('gpuCard', {}).get(c['id']), '', 'gpuCard', c['id'])
    # SSD: これまで調べているもの
    for pid, (_, _, p) in sorted(known.items()):
        if p.get('category') == 'SSD':
            add('A', 'SSD', pid, p['name'], p.get('model', ''), p.get('group', ''), p.get('capacity', ''), None, '', None, None)
    # CPUクーラー
    for c in cat['coolers']:
        pid = 'cooler-' + slug(c['brand'] + ' ' + c['name'])
        grp = {'air': '空冷(シングルタワー)', 'air2': '空冷(デュアルタワー)', 'top': '空冷(トップフロー)'}.get(c['type'], f"簡易水冷 {c['rad']}mm" if c['type'] == 'aio' else '')
        add('B', 'CPUクーラー', pid, f"{c['brand']} {c['name']}", '', grp, '', res.get('cooler', {}).get(c['id']), '', 'cooler', c['id'])
    # ケースファン(簡易水冷の付属ファン・ケースの付属ファンは除く)
    for f in cat['fans']:
        if f['aio'] or f['bundled']:
            continue
        pid = 'fan-' + slug(re.sub(r'[（(][^)）]*[)）]', '', f['name']))
        if f['rev'] and 'reverse' not in pid:   # リバース羽根(名前の違いが日本語だけのもの)
            pid += '-reverse'
        add('B', 'ファン', pid, f['name'], '', f"{f['size']}mm", '', res.get('fan', {}).get(f['id']),
            '製品名のかっこ内は調べる型(回転数など)', 'fan', f['id'])
    # ケース(単体で売られているもの)
    for k, (model, note) in RETAIL_CASES.items():
        m = cat['caseModels'].get(k)
        if not m:
            continue
        pid = 'case-' + slug(model)
        add('B', 'ケース', pid, m['name'], model, '', '', None, note, 'case', k)
    return rows, expect


def verify(rows, expect):
    """作った一覧を、架空の価格(全部 購入可・1円)で link_prices に通して、狙ったシートの製品に結び付くか確かめる。"""
    prods = [{'id': r[2], 'category': r[1], 'name': r[3], 'model': r[4], 'group': r[5], 'capacity': r[6]} for r in rows]
    obs = [{'date': '2099-01-01', 'id': r[2], 'store': 'テスト', 'price': 1, 'stock': '', 'status': '購入可', 'url': ''} for r in rows]
    with tempfile.TemporaryDirectory() as td:
        main = [p for p in prods if p['category'] in ('CPU', 'GPU', 'SSD')]
        other = [p for p in prods if p['category'] not in ('CPU', 'GPU', 'SSD')]
        for name, ps in (('prices.json', main), ('parts.json', other)):
            ids = {p['id'] for p in ps}
            json.dump({'products': ps, 'observations': [o for o in obs if o['id'] in ids]}, open(os.path.join(td, name), 'w'))
        idmap = os.path.join(link_prices.DATA, 'id-map.json')
        if os.path.exists(idmap):
            json.dump(json.load(open(idmap, encoding='utf-8')), open(os.path.join(td, 'id-map.json'), 'w'))
        old = link_prices.DATA
        link_prices.DATA = td
        try:
            out = link_prices.build()
        finally:
            link_prices.DATA = old
    bad = [u['id'] for u in out['unmatched']]
    for pid, (kind, target) in expect.items():
        if target not in out[kind]:
            bad.append(f'{pid} → {kind}/{target}')
    return bad


README = """# PCパーツ価格調査の依頼(PC構成シート用)

あなた(GPT)には、通販5店の価格を調べてCSVで返してもらいます。結果は Claude がサイトの「PC構成シート」「ファン・クーラーランキング」「パーツ価格」に反映します。

## 調べるもの
- `調査対象.csv` の製品すべて。全{n}製品(優先度A {na} / 優先度B {nb})。
  - **A**:これまで毎回調べている製品。必ず調べる。
  - **B**:シートにはあるが、まだ価格を調べていない製品。調べられる分だけでよい(全部でなくてよい。次回の続きでもよい)。
- 店舗:アーク / ツクモ / ドスパラ / パソコン工房 / アプライド(この表記のまま)の通販サイト。
- `これまでの価格.csv` は前回までの結果(参考)。「前回の最安値」と大きく違うときは、別の商品になっていないか確かめる。

## 返すCSV(`回答テンプレート.csv` と同じ列・UTF-8・1行目は列名)
```
{header}
```
- 1行 = 1日・1製品・1店舗。調べていない製品・店舗の行は作らない(「未確認」は、調べたが確かめられなかったときだけ)。
- **製品ID・カテゴリ・製品名・型番・区分・容量は `調査対象.csv` の値をそのまま写す。** 製品IDは絶対に変えない
  (サイトはこのIDで製品を見分けます。変えると価格がシートに入りません)。
- 購入可否は 購入可 / 購入不可 / 取扱終了 / 未確認 のどれか。
  - 購入可:商品が一致し、在庫あり(当日出荷・取り寄せ可を含む)→ 価格を入れる。
  - 購入不可:在庫なし・売り切れ → **価格は空欄**(参考価格を入れない)。
  - 取扱終了:販売終了 → 価格は空欄。
  - 未確認:商品ページが見つからない・別商品の疑い・型が違う(回転数違い・色違いなど)→ 価格は空欄。理由を備考に。
- 購入可能価格:税込・1個(ファンは1個パックの価格。3個パックしかない場合は「未確認」にして備考に3個パックの価格を書く)。
  カンマ・円記号なし。クーポン・ポイント適用前の価格。
- 日付は日本時間の調査日(YYYY-MM-DD)。
- 備考:気づいた点(色の違い、セット品、要納期確認、クーポン適用前 など)。

## カテゴリごとの注意
- CPU:BOX版。区分はシリーズ(Ryzen 7 など)。
- GPU:メーカー・シリーズ・チップが同じカード(VRAM容量違いがある場合は備考に書く)。区分はチップ名(RTX 5080 など)。
- SSD:型番で確認。区分は Gen4/Gen5。
- CPUクーラー:製品名の型(色違いは同じ製品でよい。備考に色)。
- ファン:製品名のかっこ内(回転数・モード)は型の手がかり。単品(1個)の価格。ケース付属品・簡易水冷付属品は対象外。
- ケース:型番は黒。備考に書いた白などの型番が安ければ、その価格でよい(備考にどちらの色かを書く)。

## 返し方
- CSVファイルを1つ(例 `prices_{date}.csv`)。カテゴリは混ぜてよい。
- 調べきれなかった優先度Bの製品は、行を作らずに残してよい(返答の最後に「未調査:◯件」と書く)。
"""


def main(argv):
    out = argv[0]
    day = argv[argv.index('--date') + 1] if '--date' in argv else date.today().isoformat()
    rows, expect = build_rows()
    bad = verify(rows, expect)
    if bad:
        print('シートの製品に結び付かない製品IDがあります:', *bad, sep='\n  ')
        return 1
    order = {'CPU': 0, 'GPU': 1, 'SSD': 2, 'CPUクーラー': 3, 'ファン': 4, 'ケース': 5}
    dup = [i for i in {r[2] for r in rows} if sum(1 for r in rows if r[2] == i) > 1]
    if dup:
        print('製品IDが重なっています:', *dup)
        return 1
    rows.sort(key=lambda r: (r[0], order[r[1]]))
    na = sum(1 for r in rows if r[0] == 'A')

    def to_csv(header, body):
        b = io.StringIO()
        w = csv.writer(b, lineterminator='\n')
        w.writerow(header)
        w.writerows(body)
        return '﻿' + b.getvalue()

    hist = []
    for name in ('prices_long.csv', 'parts_long.csv'):
        p = os.path.join(link_prices.DATA, name)
        if os.path.exists(p):
            r = list(csv.reader(open(p, encoding='utf-8-sig')))
            hist += r[1:]
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('README_GPT.md', README.format(n=len(rows), na=na, nb=len(rows) - na, header=','.join(STD), date=day.replace('-', '')))
        z.writestr('調査対象.csv', to_csv(LIST, rows))
        z.writestr('回答テンプレート.csv', to_csv(STD, []))
        z.writestr('これまでの価格.csv', to_csv(STD, sorted(hist)))
    by = {}
    for r in rows:
        by.setdefault((r[1], r[0]), 0)
        by[(r[1], r[0])] += 1
    print('wrote', out, len(rows), '製品', {f'{c}/{p}': n for (c, p), n in sorted(by.items(), key=lambda x: (order[x[0][0]], x[0][1]))})
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
