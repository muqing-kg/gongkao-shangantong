# -*- coding: utf-8 -*-
"""修复下载时写坏的图片（224 张）。

根因：CDN 对这些请求返回了 brotli 压缩内容，而 localize_images.py 的 download()
只判了「响应非空」，把压缩字节原样存盘 → 浏览器认不出，图片全裂。

修复：
  1. 少数是「前 3~4 字节垃圾 + 完整图片」→ 掐掉前缀
  2. 多数是 brotli 压缩体 → 解压
两种都按魔数复验，成功才写回。
"""
import glob, os, sys

PNG = bytes([0x89]) + b'PNG'
JPEG = b'\xff\xd8\xff'
GIFS = (b'GIF87a', b'GIF89a')


def is_image(d):
    if len(d) < 12:
        return False
    if d[:4] == PNG:
        return True
    if d[:3] == JPEG:
        return True
    if d[:6] in GIFS:
        return True
    if d[:4] == b'RIFF' and d[8:12] == b'WEBP':
        return True
    if d[:2] == b'BM':
        return True
    if b'<svg' in d[:400] or d[:5] == b'<?xml':
        return True
    return False


def find_sig(d, limit=4096):
    for s in (PNG, JPEG, b'GIF87a', b'GIF89a'):
        i = d.find(s)
        if 0 <= i < limit:
            return i
    return -1


def try_brotli(d):
    try:
        import brotli
    except ImportError:
        return None
    for fn in (brotli.decompress,):
        try:
            out = fn(d)
            if is_image(out):
                return out
        except Exception:
            pass
    # 有些是「前缀 + brotli」
    for skip in range(1, 17):
        try:
            out = brotli.decompress(d[skip:])
            if is_image(out):
                return out
        except Exception:
            continue
    return None


def repair_one(path):
    d = open(path, 'rb').read()
    if is_image(d):
        return None                      # 本来是好的

    # 1. 掐前缀
    i = find_sig(d)
    if i > 0:
        cand = d[i:]
        if is_image(cand):
            return cand

    # 2. brotli 解压
    out = try_brotli(d)
    if out:
        return out

    # 3. 整体 brotli 后再掐前缀
    try:
        import brotli
        raw = brotli.decompress(d)
        j = find_sig(raw)
        if j >= 0 and is_image(raw[j:]):
            return raw[j:]
    except Exception:
        pass

    return None


def main():
    files = sorted(glob.glob('assets/img/*'))
    broken = [p for p in files if not is_image(open(p, 'rb').read(16))]
    print(f'=== 待修 {len(broken)} / {len(files)} 张 ===')
    if '--dry' in sys.argv:
        fixed = sum(1 for p in broken if repair_one(p))
        print(f'  可修复: {fixed}   不可修复: {len(broken)-fixed}')
        return

    ok = fail = 0
    failed = []
    for i, p in enumerate(broken, 1):
        out = repair_one(p)
        if out:
            open(p, 'wb').write(out)
            ok += 1
        else:
            fail += 1
            failed.append(os.path.basename(p))
        if i % 50 == 0:
            print(f'  {i}/{len(broken)}  成功 {ok}  失败 {fail}')

    print(f'=== 修好 {ok}，失败 {fail} ===')
    if failed:
        print(f'  失败的: {failed[:20]}')

    # 复验
    still = [p for p in files if not is_image(open(p, 'rb').read(16))]
    print(f'=== 复验：仍有 {len(still)} 张坏图 ===')
    for p in still[:10]:
        print(f'  {os.path.basename(p)}')


main()
