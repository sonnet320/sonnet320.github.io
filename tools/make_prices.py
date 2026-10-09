#!/usr/bin/env python3
"""価格CSV(CPU/GPU/ファン等の統合台帳・SSD調査表・標準形式)を、標準列に揃えて data/ に書き出す。

使い方:
  python make_prices.py --out ../website/data 全件価格調査.csv ssd_5stores_prices.csv [--categories CPU,GPU,SSD]

- 入力は列名で自動判別します(古い台帳形式 / SSD形式 / 標準形式)。
- 既存の out/prices_long.csv があれば読み込み、(日付, 製品ID, 店舗) が同じ行は新しい入力で置き換えます。
- グラフに使う価格は「購入できる価格」だけ。在庫なし・取扱終了の参考価格は価格欄に入れません。
- 出力: prices_long.csv(標準列・追記用) と prices.json(グラフ用)。CPU・GPU・SSD 以外(ファン・CPUクーラー・ケースなど)は
  parts_long.csv と parts.json に分けて書く(価格推移ページは使わず、PC構成シートとランキングが使う)
"""
import argparse, csv, json, re, sys
from pathlib import Path

STD = ['日付', 'カテゴリ', '製品ID', '製品名', '型番', '区分', '容量', '店舗',
       '購入可能価格(税込)', '在庫状況', '購入可否', '商品URL', '備考']
KEY = dict(zip(STD, ['date', 'category', 'id', 'name', 'model', 'group', 'capacity', 'store',
                     'price', 'stock', 'status', 'url', 'note']))
STATUSES = ['購入可', '購入不可', '取扱終了', '未確認']
CHIP = re.compile(r'(RTX\s?\d{4}(?:\s?Ti)?(?:\s?SUPER)?|RX\s?\d{4}(?:\s?XT)?(?:\s?GRE)?|Arc\s?[AB]\d{3})', re.I)


def slug(s):
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s or 'x'


def chip_name(name):
    m = CHIP.search(name)
    if not m:
        return ''
    c = re.sub(r'\s+', '', m.group(1))
    c = re.sub(r'^(RTX|RX|Arc)', r'\1 ', c, flags=re.I)
    c = re.sub(r'(Ti|SUPER|XT|GRE)$', r' \1', c)
    return c


def cpu_group(name):
    m = re.match(r'(Ryzen \d|Core Ultra \d|Core i\d)', name)
    return m.group(1) if m else ''


def num(s):
    s = (s or '').replace(',', '').replace('円', '').strip()
    return int(s) if re.fullmatch(r'\d+', s) else None


def day(s):
    m = re.match(r'(\d{4}-\d{2}-\d{2})', s or '')
    return m.group(1) if m else ''


def from_ledger(r):
    """全件価格調査.csv などの台帳形式 (カテゴリ, 対象製品, 店舗, 価格(税込) ...)"""
    if r.get('商品一致判定', '') == '価格未記入・今回対象外':
        return None  # その日は調べていない行
    cat, name = r['カテゴリ'], r['対象製品']
    judge = r.get('購入候補判定', '')
    price = num(r.get('価格(税込)'))
    if judge == '購入候補' and price:
        status = '購入可'
    elif judge.startswith('購入不可'):
        status, price = '購入不可', None
    elif judge.startswith('対象外') or judge.startswith('要確認'):
        status, price = '未確認', None
    else:
        status, price = '未確認', None
    note = (r.get('今回確認メモ') or '').strip()
    if judge.startswith('対象外'):
        note = (note + ' 商品不一致').strip()
    if judge.startswith('要確認'):
        note = (note + ' 派生仕様の可能性').strip()
    pid = {'GPU': 'gpu-', 'CPU': 'cpu-'}.get(cat, slug(cat) + '-') + slug(name)
    group = chip_name(name) if cat == 'GPU' else cpu_group(name) if cat == 'CPU' else ''
    return dict(date=day(r.get('確認日時(JST)')) or day(r.get('確認日')), category=cat, id=pid,
                name=name, model='', group=group, capacity='', store=r['店舗'], price=price,
                stock=r.get('在庫/発送', ''), status=status, url=r.get('商品URL', ''), note=note)


def from_ssd(r):
    """ssd_5stores_prices.csv (調査日_JST, 規格, 製品名, 型番, 容量 ...)"""
    price = num(r.get('購入可能価格_税込円'))
    listed = num(r.get('掲載価格_税込円'))
    stock = r.get('在庫状況', '')
    if price:
        status = '購入可'
    elif '取扱終了' in stock:
        status = '取扱終了'
    elif listed:
        status = '購入不可'
    else:
        status = '未確認'
    model = r['型番']
    return dict(date=r['調査日_JST'], category='SSD', id='ssd-' + slug(model),
                name=f"{r['製品名']} {r['容量']}", model=model, group=r['規格'], capacity=r['容量'],
                store=r['店舗'], price=price, stock=stock, status=status,
                url=r.get('商品URL', ''), note=(r.get('備考') or '').strip())


def from_std(r):
    d = {KEY[k]: r.get(k, '') for k in STD}
    d['price'] = num(d['price'])
    return d


def detect(header):
    h = set(header)
    if '購入可否' in h and '製品ID' in h:
        return from_std
    if '購入可能価格_税込円' in h:
        return from_ssd
    if '対象製品' in h and '価格(税込)' in h:
        return from_ledger
    raise SystemExit('列名から形式を判別できません: ' + ', '.join(header))


def read(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        conv = detect(rd.fieldnames)
        return [x for x in (conv(r) for r in rd) if x]


def write_set(out, base, data, title):
    """data(標準列の行)を out/<base>_long.csv と out/<base>.json に書く。"""
    for r in data:
        assert r['status'] in STATUSES, r
        assert (r['status'] == '購入可') == bool(r['price']), r  # 価格は「購入可」の行だけ
    with open(out / f'{base}_long.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(STD)
        for r in data:
            w.writerow([r[KEY[k]] if r[KEY[k]] is not None else '' for k in STD])
    prods = {}
    for r in data:
        prods.setdefault(r['id'], {k: r[k] for k in ('id', 'category', 'name', 'model', 'group', 'capacity')})
    obs = [{k: r[k] for k in ('date', 'id', 'store', 'price', 'stock', 'status', 'url')} for r in data]
    js = {'schema': 1, 'updated': max(r['date'] for r in data),
          'stores': sorted({r['store'] for r in data}),
          'products': sorted(prods.values(), key=lambda p: (p['category'], p['group'], p['name'])),
          'observations': obs}
    (out / f'{base}.json').write_text(json.dumps(js, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    by = {}
    for r in data:
        by.setdefault((r['date'], r['category']), []).append(r)
    print(f'{title}:合計 {len(data)} 行 / 製品 {len(prods)}')
    for (d, c), v in sorted(by.items()):
        b = sum(1 for r in v if r['status'] == '購入可')
        print(f'  {d} {c}: {len(v)} 行(購入可 {b})')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs', nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--categories', default='CPU,GPU,SSD')
    a = ap.parse_args()
    cats = set(a.categories.split(','))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    # prices.*:価格推移ページの CPU・GPU・SSD。parts.*:それ以外(ファン・CPUクーラー・ケースなど。PC構成シートとランキングが使う)
    rows, parts = {}, {}
    for base, store in (('prices', rows), ('parts', parts)):
        old = out / f'{base}_long.csv'
        if old.exists():
            for r in read(old):
                store[(r['date'], r['id'], r['store'])] = r
    n = 0
    for p in a.inputs:
        for r in read(p):
            if r['date']:
                (rows if r['category'] in cats else parts)[(r['date'], r['id'], r['store'])] = r
                n += 1
    print(f'入力 {n} 行')
    key = lambda r: (r['date'], r['category'], r['id'], r['store'])
    write_set(out, 'prices', sorted(rows.values(), key=key), 'CPU・GPU・SSD')
    if parts:
        write_set(out, 'parts', sorted(parts.values(), key=key), 'ファン・クーラー・ケースなど')


if __name__ == '__main__':
    main()
