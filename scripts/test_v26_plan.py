# -*- coding: utf-8 -*-
"""致泽学堂 v2.6 学习计划验收。

设计要点：计划只持久化目标本身（考试名 / 日期 / 每日题量），
每日任务与完成度全部由 store.checkins 推导。本测试守住三件事：
1. 目标能存、能读、非法输入被夹住；
2. 今日进度与本周达标确实由 checkins 推导（不是另存一份状态）；
3. 计划随导出/导入备份一起走，不丢。
"""
import json
import os
import time
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
    ctx = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))

    page.goto(URL, wait_until='domcontentloaded', timeout=120000)

    # ---------- 1. 入口 ----------
    page.evaluate("switchTab('growth')")
    page.wait_for_timeout(200)
    check('修业成长页出现学习计划卡',
          page.locator('.feature-card h3:has-text("学习计划")').count() == 1)
    page.click('.feature-card:has(h3:text("学习计划")) button')
    page.wait_for_timeout(300)
    check('计划页渲染', page.locator('#view').inner_text().count('学习计划') >= 1)
    check('未设日期时给出引导',
          '尚未设定考试日期' in page.locator('#view').inner_text())
    check('表单三项就位',
          page.locator('#planExam').count() == 1
          and page.locator('#planDate').count() == 1
          and page.locator('#planDaily').count() == 1)
    check('日期用原生 date 控件',
          page.get_attribute('#planDate', 'type') == 'date')

    # ---------- 2. 保存目标 ----------
    page.fill('#planExam', '2026 国考')
    page.fill('#planDate', '2026-11-29')
    page.fill('#planDaily', '80')
    page.click('button:has-text("保存计划")')
    page.wait_for_timeout(300)
    stored = page.evaluate('() => JSON.parse(localStorage.getItem("shangan_tong_v1")).plan')
    check('目标写入 localStorage',
          stored == {'exam': '2026 国考', 'date': '2026-11-29', 'daily': 80}, str(stored))
    left = page.evaluate('() => planDaysLeft()')
    check('倒计时按日期推导', isinstance(left, int) and left > 0, f'{left} 天')
    check('倒计时文案已更新',
          '还有' in page.locator('#view').inner_text()
          and '2026 国考' in page.locator('#view').inner_text())
    check('保存后重新渲染计划页', page.locator('#planExam').count() == 1)

    # ---------- 3. 非法输入被夹住 ----------
    page.fill('#planDaily', '1000')
    page.click('button:has-text("保存计划")')
    page.wait_for_timeout(250)
    check('题量上限夹到 200',
          page.evaluate('() => store.plan.daily') == 200,
          str(page.evaluate('() => store.plan.daily')))
    page.fill('#planDaily', '3')
    page.click('button:has-text("保存计划")')
    page.wait_for_timeout(250)
    check('题量下限夹到 10', page.evaluate('() => store.plan.daily') == 10,
          str(page.evaluate('() => store.plan.daily')))

    page.evaluate('''() => { store.plan={exam:'X',date:'',daily:60}; save(); renderPlan(); }''')
    page.wait_for_timeout(200)
    check('空日期不产生倒计时', page.evaluate('() => planDaysLeft()') is None)
    check('空日期回到引导文案',
          '尚未设定考试日期' in page.locator('#view').inner_text())

    # ---------- 4. 进度与达标确实由 checkins 推导 ----------
    derived = page.evaluate('''() => {
      const t = today();
      store.checkins[t] = {answered:45, correct:30};
      store.checkins[fmtDate(-1)] = {answered:60, correct:40};
      store.checkins[fmtDate(-2)] = {answered:10, correct:5};
      save();
      return {done: planDone(), target: planTarget(), hit7: planHitDays(7), hit2: planHitDays(2)};
    }''')
    check('今日完成量取自 checkins', derived['done'] == 45, str(derived))
    check('每日目标读取正确', derived['target'] == 60, str(derived))
    check('达标回算（昨日 60 达标 / 前日 10 未达标）',
          derived['hit7'] == 1 and derived['hit2'] == 1, str(derived))

    page.evaluate('renderPlan()')
    page.wait_for_timeout(200)
    txt = page.locator('#view').inner_text()
    check('今日进度显示 45 / 60', '45 / 60' in txt, txt[:120])
    check('进度百分比为 75%', '75%' in txt, txt[:200])
    check('本周达标显示 1 天', '最近 7 天有 1 天' in txt, txt[:300])

    # 不落库每日任务：plan 里只有三个字段
    check('计划对象只有目标字段',
          sorted(page.evaluate('() => Object.keys(store.plan)')) == ['daily', 'date', 'exam'],
          str(page.evaluate('() => Object.keys(store.plan)')))

    # ---------- 5. 开始今日计划 ----------
    status = wait_loaded(page)
    check('题库加载无错误', not status.get('error'), str(status.get('error')))
    page.evaluate('''() => { store.plan={exam:'2026 国考',date:'2026-11-29',daily:60};
      store.checkins[today()]={answered:45,correct:30}; save(); renderPlan(); }''')
    page.wait_for_timeout(200)
    check('剩余题量按目标减已完成',
          '还剩 15 题' in page.locator('#view').inner_text(),
          page.locator('#view').inner_text()[:200])
    page.click('button:has-text("开始今日计划")')
    page.wait_for_timeout(600)
    check('进入答题层', page.locator('#quizLayer:not(.hidden)').count() == 1)
    check('练习题为剩余题量',
          '15 题' in page.locator('#quizTitle').inner_text(),
          page.locator('#quizTitle').inner_text())
    page.click('#quizClose')
    page.wait_for_timeout(300)

    # 已完成超过目标时按钮改为继续加练
    page.evaluate('''() => { store.checkins[today()]={answered:99,correct:70}; save(); renderPlan(); }''')
    page.wait_for_timeout(200)
    check('超额完成时改为继续加练',
          '继续加练' in page.locator('#view').inner_text())

    # ---------- 6. 备份往返 ----------
    plan_before = page.evaluate('() => JSON.stringify(store.plan)')
    roundtrip = page.evaluate('''() => {
      const dump = JSON.parse(JSON.stringify(store));
      const back = normalizeStore(dump, true);
      return JSON.stringify(back.plan);
    }''')
    check('normalizeStore 保留计划', roundtrip == plan_before, f'{plan_before} -> {roundtrip}')

    bad = page.evaluate('''() => {
      const back = normalizeStore({plan:{exam:'y'.repeat(80), date:'2026/11/29', daily:-5}, stats:{}, wrongs:{}}, true);
      return back.plan;
    }''')
    # 负数/0 是脏数据 -> 回默认 60；1..9 是「填小了」-> 夹到下限 10；超上限 -> 夹到 200。
    check('导入脏数据被规范化',
          len(bad['exam']) == 30 and bad['date'] == '' and bad['daily'] == 60, str(bad))
    clamped = page.evaluate('''() => [
      normalizeStore({plan:{daily:3}, stats:{}, wrongs:{}}, true).plan.daily,
      normalizeStore({plan:{daily:0}, stats:{}, wrongs:{}}, true).plan.daily,
      normalizeStore({plan:{daily:999}, stats:{}, wrongs:{}}, true).plan.daily,
      normalizeStore({plan:{}, stats:{}, wrongs:{}}, true).plan.daily,
      normalizeStore({stats:{}, wrongs:{}}, true).plan.daily
    ]''')
    check('题量边界与缺省一致', clamped == [10, 60, 200, 60, 60], str(clamped))

    check('无 JS 运行错误', not errors, str(errors[:3]))
    browser.close()

print(f'==== v2.6 学习计划验收：通过 {checks - len(fails)}/{checks}，失败 {fails or "无"} ====')
raise SystemExit(1 if fails else 0)
