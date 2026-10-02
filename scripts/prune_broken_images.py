# -*- coding: utf-8 -*-
"""删掉引用了缺失图片的题目。

这些题的配图文件不在盘上（141 张，全在 2008-2011 国考题里），题目对象又没留原始地址，
补不回来。留着它们的害处不是占地方，而是**污染学习数据**：
一道「关于图中示意的自然现象，下列说法错误的是」没有图，只能瞎猜，
必然进错题本、进能力画像、进失分结构——把诊断功能带偏。

用法：
  python scripts/prune_broken_images.py --dry-run
  python scripts/prune_broken_images.py
  python scripts/localize_images.py        # 紧接着重算 manifest
"""
import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, 'assets', 'img')
DRY = '--dry-run' in sys.argv
LINE_RX = re.compile(r'^QUESTION_BANK\["([^"]+)"\]\s*=\s*QUESTION_BANK\["[^"]+"\]\.concat\((\[.*\])\);\s*$')


def bank_files():
    out = ['js/questions5.js', 'js/questions7.js', 'js/questions8.js']
    out += sorted(os.path.relpath(p, ROOT).replace('\\', '/')
                  for p in glob.glob(os.path.join(ROOT, 'js/bank/questions6_*.js')))
    out += sorted(os.path.relpath(p, ROOT).replace('\\', '/')
                  for p in glob.glob(os.path.join(ROOT, 'js/bank/questions9_*.js')))
    return [f for f in out if os.path.exists(os.path.join(ROOT, f))]


def local_images(q):
    out = []
    for k in ('images', 'mat_images', 'opt_images'):
        stack = [q.get(k)]
        while stack:
            x = stack.pop()
            if isinstance(x, str):
                if x.startswith('assets/img/'):
                    out.append(os.path.basename(x))
            elif isinstance(x, list):
                stack.extend(x)
    return out


def main():
    on_disk = set(os.listdir(IMG_DIR))
    files = bank_files()
    removed = 0
    by_mod = {}
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
            keep = [q for q in qs if not any(n not in on_disk for n in local_images(q))]
            gone = len(qs) - len(keep)
            if gone:
                by_mod[mod] = by_mod.get(mod, 0) + gone
                removed += gone
                if not DRY:
                    lines[li] = (f'QUESTION_BANK["{mod}"] = QUESTION_BANK["{mod}"].concat('
                                 f'{json.dumps(keep, ensure_ascii=False)});')
                    changed = True
        if changed:
            io.open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
    print(f'{"将删除" if DRY else "已删除"} {removed} 道缺图题')
    print('按模块:', by_mod)
    if not DRY:
        print('接着跑 python scripts/localize_images.py 重算 manifest 指纹')
    return 0


if __name__ == '__main__':
    sys.exit(main())
