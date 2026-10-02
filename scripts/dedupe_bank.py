# -*- coding: utf-8 -*-
"""题库精确去重：合并重复题的多来源标注，删掉多余副本。

背景：题库的去重键是「题干（含图片地址）+ 选项集」。而图片地址里带着 CDN 域名
（fb.fbstatic.cn / fb.fenbike.cn），同一张图在两个域名下算两个不同的地址，
于是同一道题被当成两道题留了下来。图片本地化之后这批重复才暴露出来（814 组）。

本脚本按同样的键找出重复组，保留文件顺序里的第一份，把其余份的来源
并入第一份的 srcs（按「名称+题号」去重），然后删掉其余份。

用法：
  python scripts/dedupe_bank.py --dry-run   # 只看会删多少
  python scripts/dedupe_bank.py
  python scripts/localize_images.py         # 紧接着重算 manifest（幂等，只更新指纹）
"""
import glob
import io
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = '--dry-run' in sys.argv
LINE_RX = re.compile(r'^QUESTION_BANK\["([^"]+)"\]\s*=\s*QUESTION_BANK\["[^"]+"\]\.concat\((\[.*\])\);\s*$')


def nstem(q):
    """与 test_v21_quality.py 里同一个归一化：题干 + 图片指纹"""
    stem = str(q.get('stem', ''))
    imgs = q.get('images') or []

    def repl(m):
        i = int(m.group(1))
        return '[IMG:' + str(imgs[i] if i < len(imgs) else i) + ']'
    stem = re.sub(r'\[图(\d+)\]', repl, stem)
    stem = re.sub(r'<[^>]+>', '', stem)
    return re.sub(r'[\s\u3000　，。；：、！？（）()"“”《》·—-]+', '', stem)


def bank_files():
    out = ['js/questions5.js', 'js/questions7.js', 'js/questions8.js']
    out += sorted(os.path.relpath(p, ROOT).replace('\\', '/')
                  for p in glob.glob(os.path.join(ROOT, 'js/bank/questions6_*.js')))
    out += sorted(os.path.relpath(p, ROOT).replace('\\', '/')
                  for p in glob.glob(os.path.join(ROOT, 'js/bank/questions9_*.js')))
    return [f for f in out if os.path.exists(os.path.join(ROOT, f))]


def main():
    files = bank_files()
    entries = []          # [rel, line_idx, pos, mod, q]
    for rel in files:
        for li, line in enumerate(io.open(os.path.join(ROOT, rel), encoding='utf-8').read().split('\n')):
            m = LINE_RX.match(line.rstrip('\r\n'))
            if not m:
                continue
            for pos, q in enumerate(json.loads(m.group(2))):
                entries.append([rel, li, pos, m.group(1), q])
    print(f'题库共 {len(entries)} 题')

    groups = defaultdict(list)
    for e in entries:
        q = e[4]
        groups[(nstem(q), tuple(sorted(map(str, q.get('options', [])))))].append(e)

    removed = set()
    merged = 0
    for g in groups.values():
        if len(g) < 2:
            continue
        keep = g[0][4]
        have = {(s.get('name'), s.get('num'))
                for s in [keep.get('src')] + list(keep.get('srcs') or []) if isinstance(s, dict)}
        srcs = list(keep.get('srcs') or [])
        for e in g[1:]:
            removed.add((e[0], e[1], e[2]))
            for s in [e[4].get('src')] + list(e[4].get('srcs') or []):
                if not isinstance(s, dict) or not s.get('name'):
                    continue
                k = (s.get('name'), s.get('num'))
                if k in have:
                    continue
                have.add(k)
                srcs.append(s)
                merged += 1
        if srcs:
            keep['srcs'] = srcs

    print(f'重复组 {sum(1 for g in groups.values() if len(g) > 1)}，待删 {len(removed)} 题，'
          f'并入来源 {merged} 条')
    if DRY:
        return 0

    touched = 0
    for rel in files:
        p = os.path.join(ROOT, rel)
        lines = io.open(p, encoding='utf-8').read().split('\n')
        changed = False
        for li, line in enumerate(lines):
            m = LINE_RX.match(line.rstrip('\r\n'))
            if not m:
                continue
            mod = m.group(1)
            qs = json.loads(m.group(2))
            keep = [q for pos, q in enumerate(qs) if (rel, li, pos) not in removed]
            if len(keep) != len(qs):
                lines[li] = (f'QUESTION_BANK["{mod}"] = QUESTION_BANK["{mod}"].concat('
                             f'{json.dumps(keep, ensure_ascii=False)});')
                changed = True
        if changed:
            io.open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
            touched += 1
    print(f'改写了 {touched} 个文件')
    print('接着跑 python scripts/localize_images.py 重算 manifest 指纹')
    return 0


if __name__ == '__main__':
    sys.exit(main())
