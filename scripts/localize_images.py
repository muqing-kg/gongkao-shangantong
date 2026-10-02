# -*- coding: utf-8 -*-
"""把题库里引用的外部图片全部本地化。

题库里有两类外部图片（都是粉笔的 CDN，断网或粉笔清理就会裂）：

  1. 题目配图   https://fb.fbstatic.cn/api/tarzan/images/162e6c35bfc7c65.png
                → 存成 assets/img/162e6c35bfc7c65.png
  2. 数学公式   https://fb.fbstatic.cn/api/planet/accessories/formulas?fontSize=18&latex=XXX
                （无扩展名，返回 PNG，约 0.5 KB）→ 存成 assets/img/formula-<url哈希>.png

用法：
  python scripts/localize_images.py            # 下载 + 改写 + 重算 manifest（可反复跑）
  python scripts/localize_images.py --check    # 只检查是否还有外部图片没本地化

改写后按 scripts/rebuild_bank.py 同样的算法重算 q6/q9 manifest 的 build 指纹，
否则老用户的浏览器缓存不会失效、看不到新图。
"""
import concurrent.futures as cf
import glob
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, 'assets', 'img')
CHECK_ONLY = '--check' in sys.argv

# 两类图片地址。tarzan 那条要容忍扩展名后跟查询串（如 .jfif?width=700）
TARZAN_RX = re.compile(
    r'https?://[^"\'\s\\]+?/([0-9a-zA-Z_\-]+\.(?:png|jpe?g|gif|webp|jfif|bmp|svg))(?:\?[^"\'\s\\]*)?',
    re.I)
FORMULA_RX = re.compile(r'https?://[^"\'\s\\]+/api/planet/accessories/formulas\?[^"\'\s\\]+', re.I)


def bank_files():
    out = ['js/questions5.js', 'js/questions7.js', 'js/questions8.js']
    out += sorted(os.path.relpath(p, ROOT).replace('\\', '/')
                  for p in glob.glob(os.path.join(ROOT, 'js/bank/questions6_*.js')))
    out += sorted(os.path.relpath(p, ROOT).replace('\\', '/')
                  for p in glob.glob(os.path.join(ROOT, 'js/bank/questions9_*.js')))
    return [f for f in out if os.path.exists(os.path.join(ROOT, f))]


def formula_name(url):
    """公式图用 URL 的哈希命名（原地址带查询串，不能直接当文件名）"""
    return 'formula-' + hashlib.md5(url.encode('utf-8')).hexdigest()[:12] + '.png'


def collect():
    """返回 {url: 本地文件名}"""
    m = {}
    for rel in bank_files():
        txt = io.open(os.path.join(ROOT, rel), encoding='utf-8', errors='replace').read()
        for mt in TARZAN_RX.finditer(txt):
            m[mt.group(0)] = mt.group(1)
        for mt in FORMULA_RX.finditer(txt):
            m[mt.group(0)] = formula_name(mt.group(0))
    return m


def download(url, dst):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.fenbi.com/'})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if not data:
                raise ValueError('空响应')
            with open(dst, 'wb') as fh:
                fh.write(data)
            return True
        except Exception:
            time.sleep(1 + attempt)
    return False


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    urls = collect()
    todo = {u: n for u, n in urls.items()
            if not (os.path.exists(os.path.join(IMG_DIR, n)) and os.path.getsize(os.path.join(IMG_DIR, n)) > 0)}
    print(f'题库引用的外部图片 {len(urls)} 个，其中 {len(todo)} 个还没下载')

    if CHECK_ONLY:
        if todo:
            print('  仍未下载的前 5 个:', list(todo)[:5])
            return 1
        print('检查通过：所有外部图片都已本地化')
        return 0

    failed = []
    if todo:
        t0 = time.time()
        done = {'ok': 0}

        def one(item):
            u, n = item
            if download(u, os.path.join(IMG_DIR, n)):
                done['ok'] += 1
            else:
                failed.append(u)

        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(one, todo.items()))
        print(f'  下载完成 {done["ok"]} 个，失败 {len(failed)} 个，耗时 {time.time()-t0:.0f} 秒')
        if failed:
            print('  失败清单前 5:', failed[:5])
            print('  → 失败项未改写，重跑本脚本可续传')
    else:
        print('  无需下载')

    # ---------- 改写 ----------
    # 先清掉历史遗留的脏路径：assets/img/X.png?width=700 → assets/img/X.png
    # （早期版本的正则只匹配到扩展名，把查询串留在了路径里）
    DIRTY_RX = re.compile(r'(assets/img/[^"\'\s\\?]+)\?[^"\'\s\\]*')
    total = 0
    for rel in bank_files():
        p = os.path.join(ROOT, rel)
        txt = io.open(p, encoding='utf-8', errors='replace').read()
        txt2, n_dirty = DIRTY_RX.subn(r'\1', txt)
        if n_dirty:
            io.open(p, 'w', encoding='utf-8', newline='\n').write(txt2)
            total += n_dirty
    if total:
        print(f'  清掉路径里残留的查询串 {total} 处')

    for rel in bank_files():
        p = os.path.join(ROOT, rel)
        txt = io.open(p, encoding='utf-8', errors='replace').read()
        n = 0

        def sub_tarzan(mt):
            nonlocal n
            if os.path.exists(os.path.join(IMG_DIR, mt.group(1))):
                n += 1
                return 'assets/img/' + mt.group(1)
            return mt.group(0)

        def sub_formula(mt):
            nonlocal n
            u = mt.group(0)
            name = formula_name(u)
            if os.path.exists(os.path.join(IMG_DIR, name)):
                n += 1
                return 'assets/img/' + name
            return u

        txt = TARZAN_RX.sub(sub_tarzan, txt)
        txt = FORMULA_RX.sub(sub_formula, txt)
        if n:
            io.open(p, 'w', encoding='utf-8', newline='\n').write(txt)
            total += n
    print(f'  改写 {total} 处')

    # ---------- 重算 q6/q9 manifest ----------
    def write_manifest(pattern, out_name):
        files = sorted(glob.glob(os.path.join(ROOT, pattern)))
        if not files:
            return                      # 该题库已下线（如模拟题已全部移除），不写空 manifest
        chunks, tot, digest = [], 0, hashlib.sha256()
        for fp in files:
            raw = open(fp, 'rb').read()
            digest.update(raw)
            cnt, mods = 0, set()
            for line in raw.decode('utf-8').split('\n'):
                m = re.match(r'^QUESTION_BANK\["([^"]+)"\] = QUESTION_BANK\["[^"]+"\]\.concat\((\[.*\])\);\s*$', line)
                if m:
                    mods.add(m.group(1))
                    try:
                        cnt += len(json.loads(m.group(2)))
                    except Exception:
                        pass
            tot += cnt
            chunks.append({'file': os.path.relpath(fp, ROOT).replace('\\', '/'),
                           'module': '、'.join(sorted(mods)), 'count': cnt,
                           'bytes': os.path.getsize(fp)})
        man = {'version': 4, 'build': digest.hexdigest()[:16], 'total': tot, 'chunks': chunks}
        with io.open(os.path.join(ROOT, 'js/bank', out_name), 'w', encoding='utf-8', newline='\n') as f:
            json.dump(man, f, ensure_ascii=False, indent=1)
        print(f'  {out_name}: total={tot} chunks={len(chunks)} build={man["build"]}')

    print('重算 manifest:')
    write_manifest('js/bank/questions6_*.js', 'questions6-manifest.json')
    write_manifest('js/bank/questions9_*.js', 'questions9-manifest.json')

    zt = os.path.join(ROOT, 'js/bank/questions-zhenti-manifest.json')
    man = json.load(io.open(zt, encoding='utf-8'))
    tot = 0
    for c in man['chunks']:
        p = os.path.join(ROOT, c['file'])
        c['bytes'] = os.path.getsize(p)
        cnt = 0
        for line in io.open(p, encoding='utf-8').read().split('\n'):
            m = re.match(r'^QUESTION_BANK\["[^"]+"\] = QUESTION_BANK\["[^"]+"\]\.concat\((\[.*\])\);\s*$', line)
            if m:
                try:
                    cnt += len(json.loads(m.group(1)))
                except Exception:
                    pass
        c['count'] = cnt
        tot += cnt
    man['total'] = tot
    with io.open(zt, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'  questions-zhenti-manifest.json: total={tot}')
    return 0 if not failed else 2


if __name__ == '__main__':
    sys.exit(main())
