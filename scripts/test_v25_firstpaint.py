# -*- coding: utf-8 -*-
"""致泽学堂 v2.5 首屏瘦身验收。

背景：v2.4 及以前 index.html 同步加载 questions5/7/8.js（约 28.9MB），首屏白屏在
10Mbps 下约 23.7s。v2.5 起这三份并入 lazy-bank 懒加载与 IndexedDB 持久缓存，
题库只收真题：首屏只加载六个模块的空结构，12,908 道真题异步加载。

本测试守住三条：
1. 首屏 JS 体积预算与文件清单（回归时立刻失败，而不是等用户抱怨白屏）；
2. 懒加载合并后题库总量、模块分布、分片数不丢不重；
3. 首屏可交互（题库未就绪时点击练习不白屏、不静默失败）。
"""
import os
import time
from playwright.sync_api import sync_playwright

URL = os.environ.get('SAT_TEST_URL', 'http://127.0.0.1:8140/index.html')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

# 首屏允许同步加载的脚本；questions5/7/8.js 出现在这里即为回归。
# 题库只收真题后，首屏只剩「六个模块的空结构」这一个数据脚本。
FIRST_PAINT_ALLOWED = {
    'questions.js', 'icons.js', 'lazy-bank.js', 'shenlun.js', 'ai.js', 'app.js',    'sync.js',
}
FIRST_PAINT_BUDGET_MB = 1.5
BASE_QUESTIONS = 0
FULL_QUESTIONS = 12908
LAZY_QUESTIONS = 12908
LAZY_CHUNKS = 3
EXPECTED_MODS = {'政治理论': 465, '常识判断': 4182, '言语理解': 2607,
                 '数量关系': 983, '判断推理': 2980, '资料分析': 1691}


fails = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    print(f'[{"PASS" if ok else "FAIL"}] {name} {detail}')
    if not ok:
        fails.append(name)


def wait_loaded(page, timeout=240):
    end = time.time() + timeout
    while time.time() < end:
        st = page.evaluate('() => window.LAZY_BANK_STATUS')
        if st and (st.get('loaded') or st.get('error')):
            return st
        time.sleep(.2)
    raise TimeoutError('题库加载超时')


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))

    # 题库瘦身后（只剩真题 3 份 / 约 29MB）本机加载只要几百毫秒，
    # 靠时序赌「未就绪」已经不可靠——拦住最后一份分片，让题库停在加载中，
    # 之后放行还能顺带验证「就绪后自动补进答题层」。
    held = {}
    def hold_chunk(route):
        held['route'] = route
    page.route('**/js/questions8.js', hold_chunk)
    page.goto(URL, wait_until='domcontentloaded', timeout=120000)

    # ---------- 1. 首屏体积预算 ----------
    first = page.evaluate('''() => {
      const dcl = Math.round(performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd);
      const js = performance.getEntriesByType('resource')
        .map(r => ({name: r.name.split('/').pop().split('?')[0],
                    decoded: Math.round(r.decodedBodySize || 0),
                    start: r.startTime}))
        .filter(r => r.name.endsWith('.js') && r.start < dcl);
      return {dcl, js, total: js.reduce((s, r) => s + r.decoded, 0),
              bankStatus: window.LAZY_BANK_STATUS.loaded};
    }''')
    names = {r['name'] for r in first['js']}
    mb = first['total'] / 1048576
    check('首屏 JS 体积在预算内', mb <= FIRST_PAINT_BUDGET_MB, f"{mb:.2f}MB / 预算 {FIRST_PAINT_BUDGET_MB}MB")
    check('首屏脚本清单与预期一致', names == FIRST_PAINT_ALLOWED,
          f"多出={sorted(names - FIRST_PAINT_ALLOWED)} 缺少={sorted(FIRST_PAINT_ALLOWED - names)}")
    check('首屏未同步加载真题库', not names & {'questions5.js', 'questions7.js', 'questions8.js'})
    check('首屏可见时完整题库尚未就绪', first['bankStatus'] is False, str(first['bankStatus']))
    check('首屏基础题量为 0', page.evaluate('() => allQuestions().length') == BASE_QUESTIONS,
          str(page.evaluate('() => allQuestions().length')))

    # ---------- 2. 首屏可交互：题库未就绪时点击练习不白屏 ----------
    page.click('button.gb:has-text("随机刷题")')
    page.wait_for_timeout(300)
    toast = page.locator('#toast')
    check('题库未就绪时给出加载提示', toast.count() == 1 and '加载' in toast.inner_text(),
          toast.inner_text() if toast.count() else '无 toast')
    check('题库未就绪时不弹空答题层', page.locator('#quizLayer.hidden').count() == 1)

    # ---------- 3. 懒加载合并后题库完整 ----------
    # 放行被拦住的分片，题库随之就绪
    page.wait_for_timeout(600)
    if 'route' in held:
        held['route'].continue_()
    page.unroute('**/js/questions8.js', hold_chunk)
    status = wait_loaded(page)
    check('题库加载无错误', not status.get('error'), str(status.get('error')))
    check('懒加载题量 12908', status.get('totalQuestions') == LAZY_QUESTIONS, str(status.get('totalQuestions')))
    check('懒加载分片数 3', status.get('totalChunks') == LAZY_CHUNKS, str(status.get('totalChunks')))
    check('分片全部就位', status.get('loadedChunks') == status.get('totalChunks'),
          f"{status.get('loadedChunks')}/{status.get('totalChunks')}")
    check('签名含真题库指纹', 'zt:' in (status.get('signature') or ''), str(status.get('signature')))
    check('全库题量 12908', page.evaluate('() => allQuestions().length') == FULL_QUESTIONS,
          str(page.evaluate('() => allQuestions().length')))
    mods = page.evaluate('''() => Object.fromEntries(
      Object.entries(QUESTION_BANK).map(([m, a]) => [m, a.length]))''')
    for mod, expect in EXPECTED_MODS.items():
        check(f'模块题量 {mod}={expect}', mods.get(mod) == expect, f"实际{mods.get(mod)}")
    try:
        # .hidden 即不可见，必须用 attached 等待，visible 会永远等不到。
        page.wait_for_selector('#bankProgress.hidden', state='attached', timeout=10000)
        hidden = True
    except Exception:
        hidden = False
    check('题库就绪后加载提示消失', hidden)

    # 首屏点过的那次练习应在题库就绪后自动进入答题层
    page.wait_for_timeout(500)
    check('题库就绪后补进答题层', page.locator('#quizLayer:not(.hidden)').count() == 1)
    check('无 JS 运行错误', not errors, str(errors[:3]))

    # ---------- 4. 缓存命中后题量不重复 ----------
    end = time.time() + 240
    while time.time() < end:
        s = page.evaluate('() => LAZY_BANK_STATUS')
        if s.get('cacheStored') or s.get('cacheError'):
            break
        time.sleep(.25)
    check('首次加载后缓存写入成功', page.evaluate('() => LAZY_BANK_STATUS.cacheStored'),
          str(page.evaluate('() => LAZY_BANK_STATUS.cacheError')))

    page.reload(wait_until='domcontentloaded', timeout=120000)
    second = wait_loaded(page)
    check('刷新命中 IndexedDB 缓存',
          second.get('cacheHit') and second.get('source') == 'indexeddb', str(second.get('source')))
    check('缓存恢复题量无重复', page.evaluate('() => allQuestions().length') == FULL_QUESTIONS,
          str(page.evaluate('() => allQuestions().length')))
    check('缓存恢复后仍无 JS 错误', not errors, str(errors[:3]))

    browser.close()

print(f'==== v2.5 首屏瘦身验收：通过 {checks - len(fails)}/{checks}，失败 {fails or "无"} ====')
raise SystemExit(1 if fails else 0)
