#!/usr/bin/env python3
"""価格データ(data/prices.json)の製品を、PC構成シートのパーツに結びつける対応表 data/price_map.json を作る。

使い方(リポジトリの直下で):
  python tools/make_price_map.py

- シート(pc-sheet/index.html)に登録されたCPU・グラボ・CPUクーラー・ファン・ケースと、
  価格データの製品名を照らし合わせます。名前が完全に一致したものだけを結びつけます(推測で結びつけない)。
- シートは開いたときに prices.json と price_map.json を読み、最新の「在庫ありの最安値」を目安の価格に使います。
- 価格データやシートのパーツを増やしたら、このスクリプトを実行し直します(価格の自動更新でも実行されます)。
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / 'pc-sheet' / 'index.html'
PRICES = ROOT / 'data' / 'prices.json'
OUT = ROOT / 'data' / 'price_map.json'

CHIPS = {  # 価格データの group → シートのチップのキー
    'RTX 5090': '5090', 'RTX 5080': '5080', 'RTX 5070 Ti': '5070ti', 'RTX 5070': '5070',
    'RTX 5060 Ti': '5060ti', 'RTX 5060': '5060',
    'RX 9070 XT': '9070xt', 'RX 9070': '9070', 'RX 9060 XT': '9060xt',
    'RTX PRO 4000 SFF': 'rtxpro4000sff',
}
TWO_SIZES = {'5060ti', '9060xt'}  # 8GB と 16GB を別に扱うチップ(何も書いていなければ 16GB)
CHIP_TEXT = {v: k for k, v in CHIPS.items()}
CASE_MODELS = {  # 価格データの型番 → シートのケースのキー
    'H500G2-KGNN-S00': 'haf2500', 'CC-H52FB-01': 'h5flow24', 'CA-1Q9-00S1WN-00': 's100tg',
}


def words(t):
    return tuple(sorted(re.sub(r'[^a-z0-9]+', ' ', t.lower()).split()))


def slug(t):
    return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')


def gb(name):
    m = re.search(r'(\d{1,2})\s*GB', name, re.I)
    return int(m.group(1)) if m else None


def main():
    s = SHEET.read_text(encoding='utf-8')
    data = json.loads(PRICES.read_text(encoding='utf-8'))
    cpu_data = json.loads(re.search(r'^const CPU_DATA=(\{.*\});$', s, re.M).group(1))
    cpu_names = {v['n'] for v in cpu_data.values()}
    coolers = {words(f'{b} {n}'): k for k, b, n in
               re.findall(r"""id:["']([a-z0-9-]+)["'],brand:["']([^"']*)["'],name:["']([^"']*)["'],[^{}]*?type:["'](?:air|air2|aio|top)["']""", s)}
    fans = {words(n): k for k, n in re.findall(r"""id:["']([a-z0-9]+)["'],name:["']([^"']*)["'],size:\d+""", s)}
    cards = {}
    for b, se, ch in re.findall(r"\['([^']*)','([^']*)','([a-z0-9]+)',[\d.]+,[\d.]+,[\d.]+,\d,\d+,'[^']*'\]", s):
        cards[(words(f'{b} {se} {CHIP_TEXT.get(ch, ch)}'), ch)] = f"{slug(b) or 'kuro'}-{slug(se)}-{ch}"

    out = {'source': 'data/prices.json', 'cpu': {}, 'gpuChip': {}, 'gpuCard': {}, 'cooler': {}, 'fan': {}, 'case': {}}
    miss = {}
    for p in data['products']:
        cat, name, pid = p['category'], p['name'], p['id']
        key = None
        if cat == 'CPU':
            key = name if name in cpu_names else None
            if key:
                out['cpu'][pid] = key
        elif cat == 'GPU':
            ch = CHIPS.get(p.get('group', ''))
            if ch:
                size = gb(name)
                out['gpuChip'][pid] = f'{ch}-8gb' if ch in TWO_SIZES and size == 8 else ch
                key = out['gpuChip'][pid]
                # カードの価格は、そのチップのふつうのメモリ量(16GB)の製品だけ
                if not (ch in TWO_SIZES and size == 8):
                    w = words(re.sub(r'\d{1,2}\s*GB', '', name, flags=re.I))
                    card = cards.get((w, ch))
                    if card:
                        out['gpuCard'][pid] = card
        elif cat == 'CPUクーラー':
            key = coolers.get(words(name))
            if key:
                out['cooler'][pid] = key
        elif cat == 'ファン':
            key = fans.get(words(name))
            if key:
                out['fan'][pid] = key
        elif cat == 'ケース':
            key = CASE_MODELS.get(p.get('model', ''))
            if key:
                out['case'][pid] = key
        if key is None and cat not in ('SSD', 'メモリ'):
            miss.setdefault(cat, []).append(name)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    n = {k: len(v) for k, v in out.items() if isinstance(v, dict)}
    print('結びつけた数:', n)
    for cat, names in miss.items():
        print(f'シートにない/名前が一致しない {cat}: {len(names)}件', '、'.join(names[:8]) + ('…' if len(names) > 8 else ''))


if __name__ == '__main__':
    sys.exit(main())
