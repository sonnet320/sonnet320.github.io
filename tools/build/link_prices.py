#!/usr/bin/env python3
"""毎日の価格データ(GPTの調査)を、PC構成シート・ランキングの製品に結び付けて data/sheet-prices.json を作る。

usage: python3 tools/build/link_prices.py [--check]

入力
  data/prices.json   CPU・GPU・SSD(価格推移ページと同じデータ)
  data/parts.json    ファン・CPUクーラー・ケースなど(あれば)
  data/id-map.json   価格データの製品ID → シートのID の対応表(自動で結び付かないものだけ書く)
  src/pc-sheet.html  シートの製品一覧(tools/build/catalog.cjs で取り出す)

決まり
  - 製品ごとに、いちばん新しい調査日の「購入可」の最安値を使う。その日に買える店がなければ使わない(シートの目安のまま)。
  - 結び付け:CPUは製品名のまま。GPUは gpu-<ブランド>-<シリーズ>-<rtx|rx>-<チップ> → シートのカードID。
    ファン・クーラーは名前を正規化して完全一致。ケースはシートのケース名の判定(CASE_WORDS)。どれでもなければ id-map.json。
  - 結び付かなかった製品は unmatched に入れ、画面に一覧を出す(id-map.json に足せば次から結び付く)。

出力 data/sheet-prices.json
  {updated, cpu:{名前:価格}, gpuCard:{カードID:価格}, cooler:{ID:価格}, fan:{ID:価格}, case:{ケースの種類:価格},
   date:{種類/ID:調査日}, unmatched:[{id,name,category}]}"""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'sheet-prices.json')


def load(name, default=None):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default


def catalog():
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, 'cat.json')
        subprocess.run(['node', os.path.join(ROOT, 'tools', 'build', 'catalog.cjs'),
                        os.path.join(ROOT, 'src', 'pc-sheet.html'), tmp], check=True)
        return json.load(open(tmp, encoding='utf-8'))


def norm(t):
    t = re.sub(r'[（(][^)）]*[)）]', '', t or '')
    return re.sub(r'[^0-9a-z぀-ヿ一-鿿]+', '', t.lower())


def kind_of(p):
    c, i = p.get('category', ''), p.get('id', '')
    if c == 'CPU' or i.startswith('cpu-'): return 'cpu'
    if c == 'GPU' or i.startswith('gpu-'): return 'gpu'
    if c == 'SSD' or i.startswith('ssd-'): return 'ssd'
    if i.startswith('fan-') or c in ('ファン', 'ケースファン'): return 'fan'
    if i.startswith('cooler-') or 'クーラー' in c: return 'cooler'
    if i.startswith('case-') or c == 'ケース': return 'case'
    return None


def latest_low(data):
    """製品ID → (調査日, 最安値 or None)。いちばん新しい調査日だけを見る。"""
    last, low = {}, {}
    for o in data.get('observations', []):
        if o['date'] > last.get(o['id'], ''):
            last[o['id']] = o['date']
    for o in data.get('observations', []):
        if o['date'] == last[o['id']] and o.get('status') == '購入可' and o.get('price'):
            low[o['id']] = min(low.get(o['id'], 10 ** 9), int(o['price']))
    return {i: (d, low.get(i)) for i, d in last.items()}


def build():
    cat = catalog()
    idmap = load('id-map.json', {}) or {}
    idmap = {k: v for k, v in idmap.items() if not k.startswith('_')}
    cards = {c['id'] for c in cat['gpuCards']}
    fans = {norm(f['name']): f['id'] for f in cat['fans']}
    coolers = {}
    for c in cat['coolers']:
        coolers[norm(c['brand'] + c['name'])] = c['id']
        if c.get('alias'): coolers[norm(c['brand'] + c['alias'])] = c['id']
    cases = [(re.compile(src, re.I if 'i' in flags else 0), k) for src, flags, k in cat['cases']]
    out = {'updated': None, 'cpu': {}, 'gpuCard': {}, 'cooler': {}, 'fan': {}, 'case': {}, 'date': {}, 'unmatched': []}
    for data in (load('prices.json', {}), load('parts.json', {})):
        if not data: continue
        prods = {p['id']: p for p in data.get('products', [])}
        for pid, (day, price) in latest_low(data).items():
            p = prods.get(pid, {'id': pid, 'name': pid, 'category': ''})
            k = kind_of(p)
            if k in (None, 'ssd'): continue
            target = idmap.get(pid)
            if k == 'cpu':
                target = target or p['name']
            elif k == 'gpu' and not target:
                g = re.sub(r'^gpu-', '', pid)
                g = re.sub(r'-(rtx|rx)-(\d{4})(-(ti|xt|gre))?$', lambda m: '-' + m.group(2) + (m.group(4) or ''), g)
                g = re.sub(r'-(rtx|rx|arc)-', '-', g)
                target = g if g in cards else ('kuro-' + g) if ('kuro-' + g) in cards else None   # 玄人志向: kuro-<型番>
            elif k == 'fan' and not target:
                target = fans.get(norm(p['name']))
            elif k == 'cooler' and not target:
                target = coolers.get(norm(p['name']))
            elif k == 'case' and not target:
                target = next((key for rx, key in cases if rx.search(p['name'] + ' ' + p.get('model', ''))), None)
            if not target:
                out['unmatched'].append({'id': pid, 'name': p.get('name', ''), 'category': p.get('category', '')})
                continue
            key = 'gpuCard' if k == 'gpu' else k
            out['date'][f'{key}/{target}'] = day
            out['updated'] = max(out['updated'] or day, day)
            if price is not None:
                prev = out[key].get(target)
                out[key][target] = price if prev is None else min(prev, price)
    out['unmatched'].sort(key=lambda x: x['id'])
    return out


def main(argv):
    out = build()
    js = json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + '\n'
    if '--check' in argv:
        same = os.path.exists(OUT) and open(OUT, encoding='utf-8').read() == js
        print('最新です' if same else '作り直しが必要: data/sheet-prices.json')
        return 0 if same else 1
    changed = not os.path.exists(OUT) or open(OUT, encoding='utf-8').read() != js
    if changed:
        open(OUT, 'w', encoding='utf-8').write(js)
    n = {k: len(out[k]) for k in ('cpu', 'gpuCard', 'cooler', 'fan', 'case')}
    print(('更新' if changed else '変更なし'), 'data/sheet-prices.json', out['updated'], n)
    for u in out['unmatched']:
        print(f"::warning::シートの製品に結び付かない価格データ: {u['id']}({u['name']})→ data/id-map.json に足すと結び付きます")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
