#!/usr/bin/env python3
"""src/pc-sheet.html(PC構成シートの本文)から、サイトの2ページを作り直す。
  pc-sheet/index.html    … PC構成シート(サイト版)
  fan-ranking/index.html … ファン・クーラーランキング(サイト版)

usage:
  python3 tools/build/build_pages.py                 サイトの2ページを作る(GitHub Actions もこれを実行)
  python3 tools/build/build_pages.py --check         作り直した結果が今のファイルと同じか調べる(違えば終了コード1)
  python3 tools/build/build_pages.py --artifact-ranking out.html   Artifact版のランキングを out.html に作る

製品(ファン・クーラー・ケース)の追加は src/pc-sheet.html を直す。このスクリプトが残りを作る。
必要なもの:Python 3、Node.js(ランキングのデータをシートから取り出すため)。"""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, 'tools', 'build')
SRC = os.path.join(ROOT, 'src', 'pc-sheet.html')
sys.path.insert(0, HERE)
from site_theme import theme  # noqa: E402


def read(p):
    return open(p, encoding='utf-8').read()


def sheet_page(src):
    """PC構成シートのサイト版(旧 build_website.py と同じ変換)。"""
    bridge = read(os.path.join(HERE, 'sheet-bridge.js'))
    page = src.replace('BTO構成シート', 'PC構成シート')
    page = page.replace('https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js', '../assets/three.min.js')
    page = page.replace('--mono:"JetBrains Mono",', '--mono:"JetBrains Mono","Zen Kaku Gothic New",')
    page = page.replace('Spec Sheet ／ BTO', 'Spec Sheet ／ PC').replace('Airflow Check ／ BTO', 'Airflow Check ／ PC')
    page = page.replace('<section class="about"', '<section id="about" class="about"', 1)
    assert page.count('boot();\nallocParticles') == 1, 'シートの起動部分が見つかりません'
    page = page.replace('boot();\nallocParticles', bridge + '\nboot();\ninitWebsiteBridge();\nallocParticles')
    page = page.replace('requestAnimationFrame(loop);\n  if(ts-last<14)return;',
                        'requestAnimationFrame(loop);\n  if(websiteOffscreen&&!websiteComputing)return;\n  if(ts-last<14)return;')
    page = page.replace('<button class="btn" id="copy">データをコピー</button>',
                        '<button class="btn" id="copy">データをコピー</button>\n<button class="btn" id="export-result" type="button">計算結果を書き出す</button>')
    head, rest = page.split('<style>', 1)
    head = re.sub(r'<link[^>]+https://fonts\.[^>]+>', '', head)
    head += '\n<link rel="stylesheet" href="../assets/fonts.css">'
    style, body = rest.split('</style>', 1)
    mobile = '''\n/* Embedded sheet: one page scroll on phones, independently scrolling on desktop. */
@media(max-width:899px){body{padding:12px 10px 24px}.wrap{gap:12px}}
'''
    return ('<!doctype html><html lang="ja" data-theme="light"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            + head + '<style>' + style + mobile + '</style></head><body>' + body + '</body></html>')


def ranking_body(src_path, site):
    """ランキングの本文(旧 build_ranking.py と同じ)。データはシートから extract_data.cjs で取り出す。"""
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, 'data.json')
        subprocess.run(['node', os.path.join(HERE, 'extract_data.cjs'), src_path, tmp], check=True)
        data = json.load(open(tmp, encoding='utf-8'))
    tpl = read(os.path.join(HERE, 'ranking-template.html'))
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    assert '/*DATA*/null' in tpl and '/*SITE*/false' in tpl
    return tpl.replace('/*DATA*/null', js).replace('/*SITE*/false', 'true' if site else 'false')


def ranking_page(src_path):
    """ランキングのサイト版:本文を1ページにして、サイトの色にする。"""
    body = ranking_body(src_path, True)
    i = body.index('</style>') + len('</style>')
    page = ('<!doctype html><html lang="ja"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            + body[:i] + '\n</head><body>' + body[i:] + '</body></html>')
    return theme(page)


def main(argv):
    if '--artifact-ranking' in argv:
        out = argv[argv.index('--artifact-ranking') + 1]
        open(out, 'w', encoding='utf-8').write(ranking_body(SRC, False))
        print('wrote', out)
        return 0
    src = read(SRC)
    pages = {
        os.path.join(ROOT, 'pc-sheet', 'index.html'): sheet_page(src),
        os.path.join(ROOT, 'fan-ranking', 'index.html'): ranking_page(SRC),
    }
    if '--check' in argv:
        stale = [os.path.relpath(p, ROOT) for p, s in pages.items() if not os.path.exists(p) or read(p) != s]
        if stale:
            print('作り直しが必要:', ', '.join(stale))
            return 1
        print('最新です')
        return 0
    for p, s in pages.items():
        changed = not os.path.exists(p) or read(p) != s
        if changed:
            open(p, 'w', encoding='utf-8').write(s)
        print(('更新' if changed else '変更なし'), os.path.relpath(p, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
