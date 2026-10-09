#!/usr/bin/env python3
"""サイト(sonnet320.github.io)に置くパーツ価格シート・ファン・クーラーランキングを、サイトの色に合わせる。
usage: python3 site_theme.py <price-sheet/index.html> <fan-ranking/index.html> ...(上書き)
- サイトの assets/style.css の色(生成り・深緑)に合わせた色を、ページの色の定義の後ろに足す。
- サイトはライト表示だけなので、ダーク表示は使わない(data-theme="light")。
- フォントはサイトの assets/fonts.css を使う(Google Fonts は読まない)。
- サイトのページに埋め込まれているときは、シート自身のタイトルを隠す(ページの見出しと重なるため)。単独で開いたときは出す。
何度実行しても同じ結果になる(前に足した分は置き換える)。Artifact版には使わない。"""
import re, sys

THEME = """<style id="site-theme">
/* sonnet320.github.io の色に合わせる(assets/style.css:--bg #F5F2EB, --card #FFFDF8, --line #E2DCCF, --ink #22251F, --muted #5F6458, --green #1F6B57, --selected #E1EEE8) */
:root,:root[data-theme]{color-scheme:light;
  --bg:#F7F5EF;--stage:#F3F0E8;--panel:#FFFDF8;--line:#E2DCCF;--ink:#22251F;--muted:#5F6458;--soft:#ECE8DD;
  --accent:#1F6B57;--hl:#E1EEE8;--hl-line:#B9D8CB;--grid:#ECE8DD;--cross:#8E927E;
  --bar:#1F6B57;--bar2:#BFD3C8;--up:#C8283F;--down:#1F6B57;
  --s1:#1F6B57;--s3:#2a78d6;
  --gold:#A87A12;--silver:#6E746A;--bronze:#9C5A33;--warn:#8A6512;
  --shadow:0 1px 2px rgba(34,37,31,.05),0 6px 18px rgba(18,63,51,.05)}
/* inside a site page, the page heading already names the sheet: hide the sheet's own title, keep its date line */
html.embedded .head>div:first-child{display:none}
html.embedded .head{justify-content:flex-end;padding-bottom:6px;border-bottom-width:1px}
</style>
<script>if(window.parent!==window)document.documentElement.classList.add('embedded');</script>"""

def theme(s):
    """ページの文字列にサイトの色を付けて返す(何度かけても同じ)。"""
    s = re.sub(r'\n?<style id="site-theme">.*?</style>(\n<script>if\(window\.parent!==window\)[^<]*</script>)?', '', s, flags=re.S)
    # fonts from the site, not Google Fonts
    s = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/[^"]*">', '<link rel="stylesheet" href="../assets/fonts.css">', s)
    # light only, like the site
    if 'data-theme="light"' not in s.split('>', 2)[1] + s.split('>', 2)[0]:
        s = re.sub(r'<html lang="ja"(?![^>]*data-theme)', '<html lang="ja" data-theme="light"', s, count=1)
    assert '</head>' in s
    return s.replace('</head>', THEME + '\n</head>', 1)


if __name__ == '__main__':
    for path in sys.argv[1:]:
        s = open(path, encoding='utf-8').read()
        open(path, 'w', encoding='utf-8').write(theme(s))
        print('themed', path)
