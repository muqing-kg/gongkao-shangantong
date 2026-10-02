# -*- coding: utf-8 -*-
"""致泽学堂 v2.12 申论练笔（AI 批改）验收。

申论占省考笔试一半，而 App 里原先一道申论练习都没有。本功能不依赖申论题库——
考生自己贴题目与作文，AI 按测评维度给反馈。

这是 AI 风险最高的落点（申论没有标准答案），所以守两条硬约束：
1. **绝不给分数或档次预测**；
2. 每个维度必须**先引用考生原文为证**，不许空泛评价。

不需要真实 Key：拦截 /chat/completions 验证发出去的内容与渲染。
"""
import json
import os
from playwright.sync_api import sync_playwright

URL = os.environ.get('SAT_TEST_URL', 'http://127.0.0.1:8140/index.html')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
FAKE_KEY = 'sk-essay-test-000'

REQUIREMENT = '请结合给定资料，以「让基层治理更有温度」为题，写一篇文章。'
# 300 余字的示例作文（用于触发提交门槛）
BODY = ('基层治理的温度，来自把群众的急难愁盼放在心上。' * 3
        + '社区工作者多跑一趟，群众就少跑一趟；把小事办实，把难事办成，治理才有温度。' * 3
        + '因此，要让基层治理更有温度，既要完善机制，也要俯下身子。' * 2)
FEEDBACK = ('【立意与观点】你写到「把群众的急难愁盼放在心上」，立意扣题。但中心论点出现得偏晚。\n'
            '【结构与层次】你写到「既要完善机制，也要俯下身子」，有分层意识。\n'
            '【论证与素材】你写到「社区工作者多跑一趟」，是细节但缺少数据或案例支撑。\n'
            '【语言与表达】整体通顺，但句式重复偏多。\n'
            '【最该改的一处】把中心论点提到第一段末尾。')

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

    cap = {}
    mode = {'status': 200,
            'body': json.dumps({"choices": [{"message": {"content": FEEDBACK}}]}, ensure_ascii=False)}

    def handle(route):
        cap['url'] = route.request.url
        cap['post'] = route.request.post_data
        route.fulfill(status=mode['status'], content_type='application/json', body=mode['body'])

    page.route('**/chat/completions', handle)
    page.goto(URL, wait_until='domcontentloaded', timeout=120000)
    # 题库加载完成时若停在首页会自动 renderDash()，会覆盖直接渲染的视图；先等题库就绪以消除该竞态
    page.wait_for_function(
        "() => window.LAZY_BANK_STATUS && window.LAZY_BANK_STATUS.loaded", timeout=120000)

    # 等题库加载完、且「完整题库已就绪」toast 自己消失——
    # 否则它会顶掉后面断言的那些 toast 文案
    page.wait_for_function("() => window.LAZY_BANK_STATUS && window.LAZY_BANK_STATUS.loaded", timeout=240000)
    page.wait_for_timeout(2600)

    # ---------- 1. 入口 ----------
    page.evaluate("switchTab('shenlun')")
    page.wait_for_timeout(300)
    check('申论书房出现练笔入口', '申论练笔' in page.locator('#view').inner_text())
    check('未练过时显示 0 篇', '已练 0 篇' in page.locator('#view').inner_text())
    page.click('button:has-text("去练笔")')
    page.wait_for_timeout(300)
    check('练笔页渲染', page.locator('#essayBody').count() == 1 and page.locator('#essayReq').count() == 1)
    check('写明不是分数', '不是官方分数' in page.locator('#view').inner_text())
    check('写明会发送作文', '发送给你自己配置的 AI 接口' in page.locator('#view').inner_text())

    # ---------- 2. 门槛 ----------
    cap.clear()
    page.fill('#essayBody', '太短了')
    page.click('#essayBtn')
    page.wait_for_timeout(400)
    check('作文太短不发起请求', cap.get('url') is None)
    check('作文太短给出提示', '至少 200 字' in page.locator('#toast').inner_text(),
          page.locator('#toast').inner_text())

    page.fill('#essayBody', BODY)
    page.click('#essayBtn')
    page.wait_for_timeout(500)
    check('未配置 AI 时不发起请求', cap.get('url') is None)
    check('未配置 AI 时提示去配置', 'AI 接入' in page.locator('#toast').inner_text(),
          page.locator('#toast').inner_text())

    # ---------- 3. 提交批改 ----------
    page.evaluate("AI.saveCfg({url:'https://api.deepseek.com/v1/chat/completions', model:'deepseek-flash', key:'%s'})" % FAKE_KEY)
    page.fill('#essayReq', REQUIREMENT)
    page.fill('#essayBody', BODY)
    cap.clear()
    page.click('#essayBtn')
    page.wait_for_timeout(1500)

    body = json.loads(cap.get('post') or '{}')
    sysmsg = body.get('messages', [{}])[0].get('content', '')
    user = body.get('messages', [{}, {}])[1].get('content', '')
    check('批改请求已发出', cap.get('url') == 'https://api.deepseek.com/v1/chat/completions')
    check('system 禁止给分数', '不是分数' in sysmsg and '绝对不要给出' in sysmsg, sysmsg[:60])
    check('system 要求引用原文为证', '必须先引用考生原文里的一句话' in sysmsg)
    check('system 列出四个维度',
          all(k in sysmsg for k in ['立意与观点', '结构与层次', '论证与素材', '语言与表达']))
    check('system 要求给出最该改的一处', '【最该改的一处】' in sysmsg)
    check('system 禁止空泛评价', '不要只说「建议加强」' in sysmsg)
    check('user 带题目要求', REQUIREMENT in user)
    check('user 带作文正文', BODY[:30] in user)

    # ---------- 4. 结果与记录 ----------
    txt = page.locator('#view').inner_text()
    check('批改结果渲染', '立意与观点' in txt)
    check('练笔记录出现', '练笔记录（1 篇）' in txt)
    check('记录里含题目要求首行作标题', '请结合给定资料' in txt)
    check('写入 store.essays', page.evaluate("() => (store.essays||[]).length") == 1)
    check('记录带原文与反馈',
          page.evaluate("() => { const e=store.essays[0]; return e.body.length>200 && e.feedback.includes('最该改'); }"))

    # 持久化
    page.reload(wait_until='domcontentloaded', timeout=120000)
    page.evaluate("switchTab('shenlun'); renderEssay()")
    page.wait_for_timeout(300)
    check('刷新后练笔记录仍在', '练笔记录（1 篇）' in page.locator('#view').inner_text())

    # 刷新后 essayOpen 是内存态，条目默认收起——先展开再收起
    check('刷新后默认收起', '最该改的一处' not in page.locator('#view').inner_text())
    page.click('button:has-text("展开")')
    page.wait_for_timeout(300)
    check('展开后显示反馈正文', '最该改的一处' in page.locator('#view').inner_text())
    page.click('button:has-text("收起")')
    page.wait_for_timeout(300)
    check('收起后不显示反馈正文', '最该改的一处' not in page.locator('#view').inner_text())

    # ---------- 5. 数据边界 ----------
    norm = page.evaluate('''() => {
      const ok={id:'a',at:1,body:'x'.repeat(300),feedback:'fb',requirement:'req'};
      const r=normalizeStore({stats:{},wrongs:{},essays:[ok,{id:'',body:'y'.repeat(300)},{id:'c'}]},true);
      return {n:r.essays.length, id:r.essays[0].id};
    }''')
    check('无 id / 无正文的记录被过滤', norm['n'] == 1 and norm['id'] == 'a', str(norm))

    limit = page.evaluate('''() => {
      const many=[]; for(let i=0;i<35;i++) many.push({id:'e'+i,at:i,body:'x'.repeat(300),feedback:'f'});
      const r=normalizeStore({stats:{},wrongs:{},essays:many},true);
      return {n:r.essays.length, first:r.essays[0].id, last:r.essays[r.essays.length-1].id};
    }''')
    check('超上限只留最新 30 篇', limit['n'] == 30 and limit['first'] == 'e5' and limit['last'] == 'e34',
          str(limit))

    # ---------- 6. 删除 ----------
    page.on('dialog', lambda d: d.accept())
    page.evaluate("renderEssay()")
    page.wait_for_timeout(250)
    page.click('button[aria-label="删除这篇练笔"]')
    page.wait_for_timeout(400)
    check('删除后记录清空',
          page.evaluate("() => (store.essays||[]).length") == 0
          and '练笔记录' not in page.locator('#view').inner_text())

    check('无 JS 运行错误', not errors, str(errors[:3]))
    browser.close()

print(f'==== v2.12 申论练笔验收：通过 {checks - len(fails)}/{checks}，失败 {fails or "无"} ====')
raise SystemExit(1 if fails else 0)
