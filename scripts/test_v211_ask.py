# -*- coding: utf-8 -*-
"""致泽学堂 v2.11 问泽接通验收。

问泽原来只是个 UI 壳（sendAsk 只改状态文案）。现在接通 AI，分两种上下文：

- **逐题讲解**：把题干、选项、我的答案与**题库原始解析**一起发出去，
  system 里写死「题库原始解析是唯一权威答案，不许自己重新判断答案」——
  这是防止 AI 讲错题的关键约束。
- **通用问答**（首页 / 问泽页）：只回答备考方法类问题，涉及具体题目答案时
  要求 AI 引导用户去逐题讲解问，不许凭印象给答案。

不需要真实 Key：拦截 /chat/completions 验证发出去的内容与渲染。
"""
import json
import os
from playwright.sync_api import sync_playwright

URL = os.environ.get('SAT_TEST_URL', 'http://127.0.0.1:8140/index.html')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
FAKE_KEY = 'sk-ask-test-000'

STEM = '某市 2025 年数字经济核心产业增加值占 GDP 比重为 12.3%，比上年提高 1.1 个百分点。'
ANALYSIS = '考点：比重变化。比重提高的百分点为 1.1，故答案选 B。注意区分「比重」与「增长率」。'

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
    mode = {'status': 200, 'body': '{"choices":[{"message":{"content":"因为题干问的是比重变化，不是增长率。"}}]}'}

    def handle(route):
        cap['url'] = route.request.url
        cap['headers'] = route.request.headers
        cap['post'] = route.request.post_data
        route.fulfill(status=mode['status'], content_type='application/json', body=mode['body'])

    page.route('**/chat/completions', handle)
    page.goto(URL, wait_until='domcontentloaded', timeout=120000)

    # ---------- 1. 未配置时的行为 ----------
    page.evaluate("switchTab('ai')")
    page.wait_for_timeout(300)
    check('未配置时标注尚未接入', '尚未接入服务' in page.locator('#view').inner_text())
    page.fill('#ask-ai', '怎么提高做题速度')
    page.click('[data-send="ai"]')
    page.wait_for_timeout(400)
    check('未配置时给出配置引导并保留草稿',
          '还没配置 AI 接口' in page.locator('.ask-status[data-context="ai"]').inner_text()
          and page.input_value('#ask-ai') == '怎么提高做题速度',
          page.locator('.ask-status[data-context="ai"]').inner_text())

    # ---------- 2. 配置后：通用问答 ----------
    page.evaluate("AI.saveCfg({url:'https://api.deepseek.com/v1/chat/completions', model:'deepseek-flash', key:'%s'})" % FAKE_KEY)
    page.evaluate("switchTab('ai')")
    page.wait_for_timeout(300)
    check('配置后标注已接入', '已接入 AI' in page.locator('#view').inner_text())
    cap.clear()
    page.fill('#ask-ai', '资料分析总是做太慢怎么办')
    page.click('[data-send="ai"]')
    page.wait_for_timeout(1200)
    body = json.loads(cap.get('post') or '{}')
    check('通用问答发出请求', cap.get('url') == 'https://api.deepseek.com/v1/chat/completions')
    check('通用问答用通用 system',
          '公考（省考）备考助手' in body['messages'][0]['content'],
          body['messages'][0]['content'][:50])
    check('通用 system 禁止凭印象给题目答案',
          '逐题讲解' in body['messages'][0]['content'] and '不要凭印象给答案' in body['messages'][0]['content'])
    check('通用问答 user 就是问题本身',
          body['messages'][1]['content'] == '资料分析总是做太慢怎么办',
          body['messages'][1]['content'][:60])

    # 有学情数据时要带上学情快照，否则「今天先练什么」只能得到泛泛的答案
    page.evaluate("""() => {
      const A=[];
      for(let i=0;i<30;i++) A.push({t:Date.now(),d:today(),qid:'s'+i,mod:'资料分析',ok:i<15,
        src:'2024·省考',point:'比重',rate:60,dur:100,multi:false,type:'真题',txn:'',why:i<15?'':'来不及'});
      store.attempts=A;
      store.stats={answered:30,correct:15,byMod:{'资料分析':{answered:30,correct:15}},daily:[]};
      save();
    }""")
    page.evaluate("switchTab('ai')")
    page.wait_for_timeout(300)
    check('提问框提示会发送学情统计',
          '学情统计' in page.locator('.ask-status[data-context="ai"]').inner_text(),
          page.locator('.ask-status[data-context="ai"]').inner_text()[:60])
    cap.clear()
    page.fill('#ask-ai', '今天先练什么')
    page.click('[data-send="ai"]')
    page.wait_for_timeout(1200)
    body = json.loads(cap.get('post') or '{}')
    u = body.get('messages', [{}, {}])[1].get('content', '')
    check('有数据时提问带上学情快照', '【模块表现】' in u and '【我的问题】' in u, u[:80])
    check('快照里含她的真实数据', '资料分析' in u and '来不及' in u)
    check('问题本身在最后', u.rstrip().endswith('今天先练什么'), u[-30:])
    check('快照不含题干与答案',
          '题干' not in u and 'options' not in u and 'answer' not in u)
    check('回答渲染出来', '比重变化' in page.locator('.ask-answer[data-answer="ai"]').inner_text())
    check('回答带 AI 生成标注', 'AI 生成' in page.locator('.ask-answer[data-answer="ai"]').inner_text())

    # ---------- 3. 逐题讲解：带上题目与题库解析 ----------
    page.evaluate("""() => {
      const qs=[{id:'ask1',mod:'资料分析',type:'真题',stem:%s,
                 options:['10.1%%','12.3%%','13.4%%','1.1%%'],answer:1,
                 analysis:%s}];
      startQuiz(qs,'问泽测试'); pick(0); nextQ();
    }""" % (json.dumps(STEM, ensure_ascii=False), json.dumps(ANALYSIS, ensure_ascii=False)))
    page.wait_for_timeout(400)
    page.evaluate("reviewQuiz()")
    page.wait_for_timeout(400)
    check('逐题回顾页有问泽框', page.locator('.ask-composer[data-context="question"]').count() == 1)

    cap.clear()
    page.fill('#ask-question', '为什么不能选 A')
    page.click('[data-send="question"]')
    page.wait_for_timeout(1200)
    body = json.loads(cap.get('post') or '{}')
    sysmsg = body['messages'][0]['content']
    user = body['messages'][1]['content']
    check('逐题讲解用逐题 system', '题库原始解析' in sysmsg and '公考行测辅导老师' in sysmsg, sysmsg[:40])
    check('system 写死「不许自己重新判断答案」',
          '不许自己重新判断答案' in sysmsg and '唯一权威答案' in sysmsg)
    check('system 要求超出解析范围就说不知道', '解析里没有提到这一点' in sysmsg)
    check('user 带题干', STEM[:20] in user)
    check('user 带四个选项', 'A. 10.1%' in user and 'B. 12.3%' in user)
    check('user 带正确答案', '正确答案：B' in user, user[:400])
    check('user 带我的答案且标明错误', '我的答案：A（回答错误）' in user)
    check('user 带题库原始解析', '考点：比重变化' in user and '注意区分' in user)
    check('user 带我的问题', '【我的问题】' in user and '为什么不能选 A' in user)
    ans = page.locator('.ask-answer[data-answer="question"]').inner_text()
    check('逐题回答渲染', '比重变化' in ans)
    check('逐题回答标注以题库解析为准', '以题库原始解析为准' in ans, ans[:120])

    # ---------- 3b. 答题页答完题后也能问（这是修掉的一个 bug） ----------
    # 问泽框在两处出现：答题页答完题之后、以及逐题回顾页。
    # askQuestionCtx 曾按 Q.mode==='review' 过滤，而答题页的 mode 是 multi/single，
    # 于是「打开题目问 AI」一直提示取不到题目。
    page.evaluate("""() => {
      const qs=[{id:'ans1',mod:'数量关系',type:'真题',
                 stem:'甲单独完成需要 10 天，乙单独完成需要 15 天，两人合作需要几天？',
                 options:['5 天','6 天','7 天','8 天'],answer:1,
                 analysis:'考点：工程问题。设总量为 30，甲效率 3、乙效率 2，合作效率 5，30/5=6 天。'}];
      startQuiz(qs,'答题中问泽测试');
      pick(0);
    }""")
    page.wait_for_timeout(500)
    check('答题页答完题出现问泽框',
          page.locator('.ask-composer[data-context="question"]').count() == 1)
    cap.clear()
    page.fill('#ask-question', '为什么不是 5 天')
    page.click('[data-send="question"]')
    page.wait_for_timeout(1200)
    body = json.loads(cap.get('post') or '{}')
    user = body.get('messages', [{}, {}])[1].get('content', '')
    status = page.locator('.ask-status[data-context="question"]').inner_text()
    check('答题中提问带上题干', '甲单独完成需要' in user, user[:80])
    check('答题中提问带上题库解析', '工程问题' in user)
    check('答题中提问不再报「取不到题目」', '没有取到当前题目' not in status, status[:60])
    check('答题中提问正常出结果',
          '比重变化' in page.locator('.ask-answer[data-answer="question"]').inner_text())

    # ---------- 3c. 推荐问题按实际作答生成，不能写死 ----------
    # 以前写死成「为什么不能选 B」——她选 A 的时候这句话就是错的。
    def chips_for(pick_idx, qs_js, multi=False):
        page.evaluate("""() => {
          const qs=%s;
          startQuiz(qs,'chips'); pick(%d);%s
        }""" % (qs_js, pick_idx, ' submitMulti();' if multi else ''))
        page.wait_for_timeout(400)
        return page.evaluate(
            "() => [...document.querySelectorAll('.ask-composer[data-context=\"question\"] .ask-chip')]"
            ".map(b => b.textContent)")

    SINGLE = ("[{id:'c1',mod:'常识判断',type:'单选',stem:'单选测试题',"
              "options:['甲','乙','丙','丁'],answer:1,analysis:'解析'}]")
    MULTI = ("[{id:'c2',mod:'常识判断',type:'多选',multi:true,stem:'多选测试题',"
             "options:['甲','乙','丙','丁'],answer:'AB',analysis:'解析'}]")

    c = chips_for(0, SINGLE)          # 选 A，正确是 B
    check('答错选 A 时提示「为什么不能选 A」', c and c[0] == '为什么不能选 A', str(c))
    c = chips_for(2, SINGLE)          # 选 C，正确是 B
    check('答错选 C 时提示「为什么不能选 C」', c and c[0] == '为什么不能选 C', str(c))
    c = chips_for(1, SINGLE)          # 选 B，正确
    check('答对时不再出现「为什么不能选」',
          c and c[0] == '我选的 B 是怎么对的' and not any('为什么不能选' in x for x in c), str(c))
    c = chips_for(0, MULTI, multi=True)   # 多选只选了 A，正确是 AB
    check('多选按实际所选项生成', c and c[0] == '为什么不能选 A', str(c))
    check('后两个推荐问题保留', c and c[1:] == ['换个角度讲', '总结这个考点'], str(c))

    # 3c 把页面带到了答题态，恢复到逐题回顾供后面两节使用
    page.evaluate("""() => {
      const qs=[{id:'c9',mod:'常识判断',type:'单选',stem:'恢复用题',
                 options:['甲','乙','丙','丁'],answer:0,analysis:'解析'}];
      startQuiz(qs,'恢复'); pick(1); nextQ();
    }""")
    page.wait_for_timeout(300)
    page.evaluate("reviewQuiz()")
    page.wait_for_timeout(300)

    # ---------- 4. 错误处理 ----------
    mode['status'] = 401
    mode['body'] = '{"error":"bad key"}'
    page.fill('#ask-question', '再讲一遍')
    page.click('[data-send="question"]')
    page.wait_for_timeout(1000)
    check('出错时状态栏给出可照做的提示',
          '鉴权失败' in page.locator('.ask-status[data-context="question"]').inner_text(),
          page.locator('.ask-status[data-context="question"]').inner_text())
    check('出错后发送按钮恢复可用', page.locator('[data-send="question"]').is_enabled())

    # ---------- 5. 空输入不请求 ----------
    mode['status'] = 200
    cap.clear()
    page.fill('#ask-question', '   ')
    page.click('[data-send="question"]')
    page.wait_for_timeout(400)
    check('空输入不发起请求', cap.get('url') is None)
    check('空输入给出提示',
          '请先输入' in page.locator('.ask-status[data-context="question"]').inner_text())

    check('无 JS 运行错误', not errors, str(errors[:3]))
    browser.close()

print(f'==== v2.11 问泽接通验收：通过 {checks - len(fails)}/{checks}，失败 {fails or "无"} ====')
raise SystemExit(1 if fails else 0)
