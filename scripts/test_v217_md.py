# -*- coding: utf-8 -*-
"""致泽学堂 v2.16 AI 输出的 Markdown 渲染验收。

AI 回答的都是 Markdown，此前用 esc() 原样显示，`**加粗**`、`## 标题` 都成了字面量。
本测试守两件事：

1. **安全**：必须先 esc() 再替换。AI 输出里的 HTML/事件属性不能被当成标签执行，
   否则「渲染 Markdown」就变成了一个注入点。
2. **语法覆盖**：AI 实际会用的那几种——标题、有序/无序列表、加粗、斜体、行内码、引用。
"""
import json
import os
from playwright.sync_api import sync_playwright

URL = os.environ.get('SAT_TEST_URL', 'http://127.0.0.1:8140/index.html')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

MD = """## 最关键的 2 个问题

1. **资料分析太慢**：平均 100 秒一题。
2. *数量关系* 该放最后。

- 先练取舍
- 再补知识点

> 记住：时间优先留给有把握的题。

行内代码 `smartQuiz()` 也支持。
"""

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
    page.on('dialog', lambda d: d.dismiss())
    page.goto(URL, wait_until='domcontentloaded', timeout=120000)

    # ---------- 1. 安全：先转义再替换 ----------
    xss = page.evaluate('''() => {
      const out = {};
      out.script = mdToHtml('<script>alert(1)<\\/script>');
      out.img = mdToHtml('**<img src=x onerror=alert(1)>**');
      out.attr = mdToHtml('- <a href="javascript:alert(1)">点我</a>');
      out.amp = mdToHtml('a & b < c');
      return out;
    }''')
    check('script 标签被转义', '<script' not in xss['script'] and '&lt;script' in xss['script'],
          xss['script'][:80])
    check('加粗里的 img 被转义', '<img' not in xss['img'] and '&lt;img' in xss['img'],
          xss['img'][:90])
    check('列表里的 javascript: 链接被转义',
          '<a ' not in xss['attr'] and '&lt;a ' in xss['attr'], xss['attr'][:90])
    check('裸 & 与 < 被转义', '&amp;' in xss['amp'] and '&lt;' in xss['amp'], xss['amp'])

    # 真的插进 DOM 也不产生可执行节点
    dom = page.evaluate('''() => {
      const d = document.createElement('div');
      d.innerHTML = mdToHtml('**<img src=x onerror=window.__pwned=1>**\\n\\n<script>window.__pwned=1<\\/script>');
      document.body.appendChild(d);
      const r = {img: d.querySelectorAll('img').length, script: d.querySelectorAll('script').length,
                 pwned: !!window.__pwned};
      d.remove();
      return r;
    }''')
    check('DOM 里没有注入的 img/script', dom['img'] == 0 and dom['script'] == 0, str(dom))
    check('没有代码被执行', dom['pwned'] is False, str(dom))

    # ---------- 2. 语法覆盖 ----------
    html = page.evaluate('(md) => mdToHtml(md)', MD)
    check('二级标题', 'md-h md-h2' in html and '最关键的 2 个问题' in html)
    check('加粗', '<b>资料分析太慢</b>' in html)
    check('斜体', '<i>数量关系</i>' in html)
    check('有序列表', '<ol class="md-ol">' in html and html.count('<li>') >= 4, str(html.count('<li>')))
    check('无序列表', '<ul class="md-ul">' in html)
    check('引用', '<div class="md-quote">' in html)
    check('行内代码', '<code>smartQuiz()</code>' in html)
    check('空行成段间距', 'md-gap' in html)
    check('列表正确闭合', html.count('<ul') == html.count('</ul>') and html.count('<ol') == html.count('</ol>'))

    # ---------- 3. 真接到 AI 回答上 ----------
    page.route('**/chat/completions', lambda r: r.fulfill(
        status=200, content_type='application/json',
        body=json.dumps({"choices": [{"message": {"content": MD}}]}, ensure_ascii=False)))
    page.evaluate("AI.saveCfg({url:'https://api.deepseek.com/v1/chat/completions', model:'m', key:'k'})")
    page.evaluate("switchTab('ai')")
    page.wait_for_timeout(300)
    page.fill('#ask-ai', '怎么提速')
    page.click('[data-send="ai"]')
    page.wait_for_timeout(1500)
    box = page.locator('.ask-answer[data-answer="ai"] .ask-answer-body')
    check('AI 回答渲染出真实标签',
          box.locator('b').count() >= 1 and box.locator('ol li').count() >= 2
          and box.locator('.md-h2').count() == 1,
          f"b={box.locator('b').count()} li={box.locator('ol li').count()}")
    check('页面上看不到字面量星号',
          '**' not in box.inner_text() and '##' not in box.inner_text(),
          box.inner_text()[:80])

    check('无 JS 运行错误', not errors, str(errors[:3]))
    browser.close()

print(f'==== v2.16 Markdown 渲染验收：通过 {checks - len(fails)}/{checks}，失败 {fails or "无"} ====')
raise SystemExit(1 if fails else 0)
