# -*- coding: utf-8 -*-
"""致泽学堂 v2.14 申论真题验收。

App 原先申论是零练习。数据来自 GitHub 公开仓库的国考申论真题（2022-2025
副省/地市/行政执法），导入器只取 12 份结构完整的卷，刻意丢掉该仓库的
「申论100题」（stem 只是标题标签、reference 混着答案与材料片段）。

守三件事：
1. 数据按需加载，不拖累首屏；
2. 先做后看：材料与参考答案默认收起，避免直接看答案；
3. AI 批改复用已有的「申论练笔」，题目要求自动带入。
"""
import os
from playwright.sync_api import sync_playwright

URL = os.environ.get('SAT_TEST_URL', 'http://127.0.0.1:8140/index.html')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

fails = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    print(f'[{"PASS" if ok else "FAIL"}] {name} {detail}')
    if not ok:
        fails.append(name)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(URL, wait_until='domcontentloaded', timeout=120000)

    # ---------- 1. 首屏不带申论数据 ----------
    check('首屏未加载申论数据',
          page.evaluate("() => typeof window.SHENLUN_PAPERS === 'undefined'"))

    # ---------- 2. 入口 ----------
    page.evaluate("switchTab('shenlun')")
    page.wait_for_timeout(300)
    check('申论书房出现真题入口', '申论真题' in page.locator('#view').inner_text())

    page.click('button:has-text("去做真题")')
    page.wait_for_timeout(2500)
    txt = page.locator('#view').inner_text()
    check('按需加载后卷列表出现', '国考申论真题' in txt, txt[:120])
    check('加载后数据在内存里',
          page.evaluate("() => Array.isArray(window.SHENLUN_PAPERS)"))
    n = page.evaluate("() => window.SHENLUN_PAPERS.length")
    check('12 份卷', n == 12, str(n))
    total = page.evaluate("() => window.SHENLUN_PAPERS.reduce((s,p)=>s+p.questions.length,0)")
    check('59 道题', total == 59, str(total))
    withref = page.evaluate("() => window.SHENLUN_PAPERS.reduce((s,p)=>s+p.questions.filter(q=>q.reference).length,0)")
    check('58 道有参考答案', withref == 58, str(withref))
    check('卷列表渲染 12 条', page.locator('#view .sl-item').count() == 12,
          str(page.locator('#view .sl-item').count()))

    # ---------- 3. 打开一份卷 ----------
    page.click('#view .sl-item button:has-text("打开")')
    page.wait_for_timeout(600)
    txt = page.locator('#view').inner_text()
    check('进入卷详情', '给定材料' in txt and '作答要求' in txt)
    check('显示返回按钮', page.locator('button:has-text("返回卷列表")').count() == 1)
    mats = page.locator('#view .sl-item').count()
    check('材料与题目都渲染了', mats > 5, str(mats))

    # ---------- 4. 材料默认收起 ----------
    check('材料默认收起', '（展开阅读）' in txt)
    body_before = page.evaluate("() => document.querySelector('#view .sl-item .sl-body')?.textContent.length || 0")
    page.click('button:has-text("展开")')
    page.wait_for_timeout(500)
    body_after = page.evaluate("() => document.querySelector('#view .sl-item .sl-body')?.textContent.length || 0")
    check('展开材料后正文变长', body_after > body_before, f'{body_before} -> {body_after}')

    # ---------- 5. 参考答案默认收起 ----------
    check('参考答案默认收起', '对照参考答案' in page.locator('#view').inner_text())
    check('收起时不显示参考答案正文',
          '参考答案：' not in page.locator('#view').inner_text())
    page.click('button:has-text("对照参考答案")')
    page.wait_for_timeout(500)
    t2 = page.locator('#view').inner_text()
    check('展开后显示参考答案', '参考答案：' in t2)
    has_points = page.evaluate("""() => {
      const ps = window.SHENLUN_PAPERS.flatMap(p => p.questions).filter(q => q.points && q.points.length);
      return ps.length;
    }""")
    check('数据里带评分要点', has_points > 0, str(has_points))

    # ---------- 6. AI 批改复用申论练笔 ----------
    page.click('button:has-text("让 AI 批改")')
    page.wait_for_timeout(700)
    check('跳到申论练笔页', page.locator('#essayBody').count() == 1)
    req = page.input_value('#essayReq')
    check('题目要求已带入', '第 1 题' in req and len(req) > 30, req[:80])

    # ---------- 7. 加载失败可重试 ----------
    page2 = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page2.route('**/shenlun-papers.js*', lambda r: r.abort('failed'))
    page2.goto(URL, wait_until='domcontentloaded', timeout=120000)
    page2.evaluate("switchTab('shenlun'); renderShenlunPapers()")
    page2.wait_for_timeout(1500)
    t3 = page2.locator('#view').inner_text()
    check('数据加载失败时给出提示', '加载失败' in t3, t3[:100])
    check('失败后提供重试按钮', page2.locator('button:has-text("重试")').count() == 1)
    page2.close()

    check('无 JS 运行错误', not errors, str(errors[:3]))
    browser.close()

print(f'==== v2.14 申论真题验收：通过 {checks - len(fails)}/{checks}，失败 {fails or "无"} ====')
raise SystemExit(1 if fails else 0)
