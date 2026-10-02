# -*- coding: utf-8 -*-
"""致泽学堂 v2.13 首次引导与备份提醒验收。

架构选了「学习数据存在用户浏览器」，代价就是换设备/清浏览器数据会全部丢失。
这条取舍的短板必须在界面上主动提醒，不能等出事——所以：

1. 零数据的新用户看到「三步开始」引导；
2. 有数据却从未备份 / 超过 14 天没备份，首页出现「该备份了」；
3. 导出备份后立刻记录时间，提醒消失；超过 14 天自动回来；
4. 备份时间随备份文件往返（属于学习数据）。
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
    ctx = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(URL, wait_until='domcontentloaded', timeout=120000)

    # ---------- 1. 零数据新用户 ----------
    page.evaluate("switchTab('dashboard')")
    page.wait_for_timeout(300)
    txt = page.locator('#view').inner_text()
    check('零数据时显示三步开始', '第一次来？三步开始' in txt, txt[:120])
    check('零数据时不显示备份提醒', '该备份了' not in txt)
    check('零数据时备份状态说明不用备份',
          '还没有学习数据' in page.evaluate("() => backupStatus().text"))
    check('备份状态不告警', page.evaluate("() => backupStatus().warn") is False)

    # ---------- 2. 有数据但从未备份 ----------
    page.evaluate("""() => {
      store.stats.answered = 120; store.stats.correct = 80;
      store.stats.byMod = {'常识判断':{answered:120,correct:80}};
      store.settings.lastExport = 0;
      save(); renderDash();
    }""")
    page.wait_for_timeout(300)
    txt = page.locator('#view').inner_text()
    check('有数据未备份时首页提醒', '该备份了' in txt)
    check('提醒里说明后果', '全部丢失' in txt, txt[:200])
    check('提醒带一键导出按钮', page.locator('button:has-text("立即导出备份")').count() == 1)
    check('有数据后不再显示三步开始', '第一次来？三步开始' not in txt)

    # 我的书斋里也能看到
    page.evaluate("switchTab('more')")
    page.wait_for_timeout(300)
    check('数据管理卡显示备份状态', '从未导出过备份' in page.locator('#view').inner_text())

    # ---------- 3. 导出后提醒消失 ----------
    page.evaluate("switchTab('dashboard')")
    page.wait_for_timeout(250)
    with page.expect_download(timeout=15000):
        page.click('button:has-text("立即导出备份")')
    page.wait_for_timeout(400)
    check('导出后记录备份时间', page.evaluate("() => store.settings.lastExport") > 0)
    check('导出后首页提醒消失', '该备份了' not in page.locator('#view').inner_text())
    check('备份状态显示今天',
          '今天' in page.evaluate("() => backupStatus().text"),
          page.evaluate("() => backupStatus().text"))

    # ---------- 4. 超过 14 天自动回来 ----------
    for days, expect_warn, label in [(13, False, '13 天'), (14, True, '14 天'), (40, True, '40 天')]:
        page.evaluate("(d) => { store.settings.lastExport = Date.now() - d*86400000; save(); renderDash(); }", days)
        page.wait_for_timeout(250)
        warn = page.evaluate("() => backupStatus().warn")
        check(f'{label}未备份时告警={expect_warn}', warn is expect_warn,
              page.evaluate("() => backupStatus().text"))
        if expect_warn:
            check(f'{label}时首页出现提醒', '该备份了' in page.locator('#view').inner_text())
        else:
            check(f'{label}时首页无提醒', '该备份了' not in page.locator('#view').inner_text())
            check(f'{label}时显示天数', '13 天前' in page.evaluate("() => backupStatus().text"))

    # ---------- 5. 备份时间随备份往返 ----------
    rt = page.evaluate('''() => {
      store.settings.lastExport = 1750000000000;
      save();
      const dump = JSON.parse(JSON.stringify(store));
      const back = normalizeStore(dump, true);
      return back.settings.lastExport;
    }''')
    check('备份时间随备份文件往返', rt == 1750000000000, str(rt))

    bad = page.evaluate('''() => normalizeStore({stats:{},wrongs:{},settings:{lastExport:-5}}, true).settings.lastExport''')
    check('非法备份时间归零', bad == 0, str(bad))

    old = page.evaluate('''() => normalizeStore({stats:{},wrongs:{},settings:{}}, true).settings.lastExport''')
    check('旧备份（无该字段）补 0', old == 0, str(old))

    check('无 JS 运行错误', not errors, str(errors[:3]))
    browser.close()

print(f'==== v2.13 首次引导与备份提醒验收：通过 {checks - len(fails)}/{checks}，失败 {fails or "无"} ====')
raise SystemExit(1 if fails else 0)
