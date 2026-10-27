#!/usr/bin/env python3
"""出典(サイト)ごとに、シートの値をまとめて外すためのスクリプト。

サイトから「データを使わないでほしい」と連絡が来たときに使います。手順は _dev/takedown.md。

使い方(リポジトリの直下で):
  python tools/remove_source.py computerbase.de            # 何が外れるかを表示するだけ(変更しない)
  python tools/remove_source.py computerbase.de --apply    # 実際に外す

- CPU の消費電力(CPU_DATA の idle / game / enc / peak)のうち、出典がそのサイトのものを外します。
  外した場面は、シートが電力上限や使用率から計算する値に戻ります。
- 使われなくなった出典(CPU_SRC)も消します。
- それ以外の場所(GPU の補正・ファン口径・最大回転数・検証記録など)にそのサイトが出てくる行を一覧にします。
  これらは値の決め方がそれぞれ違うため、_dev/takedown.md の手順で手で外します。
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / 'pc-sheet' / 'index.html'
SCENES = ('idle', 'game', 'enc', 'peak')
SCENE_JA = {'idle': 'アイドル', 'game': 'ゲーム', 'enc': '動画の書き出し', 'peak': '最大'}


def dumps(o):
    return json.dumps(o, ensure_ascii=False, separators=(',', ':'))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    apply = '--apply' in sys.argv
    if len(args) != 1:
        print(__doc__)
        return 1
    dom = args[0].lower().removeprefix('https://').removeprefix('http://').removeprefix('www.').split('/')[0]
    s = SHEET.read_text(encoding='utf-8')
    m_src = re.search(r'^const CPU_SRC=(\{.*\});$', s, re.M)
    m_dat = re.search(r'^const CPU_DATA=(\{.*\});$', s, re.M)
    src, data = json.loads(m_src.group(1)), json.loads(m_dat.group(1))

    def hit(url):
        return dom in (url or '').lower()

    removed = []
    for key, cpu in data.items():
        for sc in SCENES:
            x = cpu.get(sc)
            if x and (hit(x.get('u')) or hit(src.get(x.get('s'), {}).get('u'))):
                removed.append(f"{cpu['n']}:{SCENE_JA[sc]}")
                cpu[sc] = None
    used = {cpu.get('spec') for cpu in data.values()}
    used |= {cpu[sc].get('s') for cpu in data.values() for sc in SCENES if cpu.get(sc)}
    gone_src = [k for k, v in src.items() if hit(v.get('u')) and k not in used]
    for k in gone_src:
        del src[k]
    still = [k for k, v in src.items() if hit(v.get('u'))]

    print(f'対象のサイト:{dom}')
    print(f'CPU の消費電力から外す値:{len(removed)}件')
    for r in removed:
        print('  -', r)
    print(f'消す出典(CPU_SRC):{len(gone_src)}件 {gone_src}')
    if still:
        print(f'注意:CPU の仕様(spec)など、ほかの用途でまだ使っている出典があります:{still}')

    print('\nほかにこのサイトが出てくる場所(手で確認する):')
    for p in sorted(ROOT.rglob('*')):
        if p.is_dir() or '.git' in p.parts or p.suffix not in ('.html', '.js', '.json', '.md', '.csv'):
            continue
        try:
            lines = p.read_text(encoding='utf-8').split('\n')
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(lines, 1):
            if dom in line.lower() and not line.startswith(('const CPU_SRC=', 'const CPU_DATA=')):
                print(f'  {p.relative_to(ROOT)}:{i}: {line.strip()[:120]}')

    if apply and (removed or gone_src):
        s = s[:m_dat.start()] + 'const CPU_DATA=' + dumps(data) + ';' + s[m_dat.end():]
        m_src = re.search(r'^const CPU_SRC=(\{.*\});$', s, re.M)
        s = s[:m_src.start()] + 'const CPU_SRC=' + dumps(src) + ';' + s[m_src.end():]
        SHEET.write_text(s, encoding='utf-8')
        print('\npc-sheet/index.html を書き換えました。')
    elif not apply:
        print('\n(表示だけです。外すときは --apply を付けて実行します)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
