# -*- coding: utf-8 -*-
"""致泽学堂正式 UI v2.4：上岸小助手首页、逐题入口与一级页面。"""
import os
from playwright.sync_api import sync_playwright

URL = os.environ.get("SAT_TEST_URL", "http://127.0.0.1:8141/index.html?v=zhize-features-red")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
fails = []


def check(name, ok, detail=""):
    print(f'[{"PASS" if ok else "FAIL"}] {name} {detail}')
    if not ok:
        fails.append(name)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.add_init_script(
        """
        window.SpeechRecognition=class {
          start(){
            this.onstart?.();
            this.onresult?.({results:[[{transcript:'请解释资料分析的思路'}]]});
            this.onend?.();
          }
          stop(){ this.onend?.(); }
        };
        """
    )
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(URL, wait_until="domcontentloaded", timeout=120000)

    page.evaluate("switchTab('dashboard')")
    check("首页直接显示上岸小助手对话框", page.locator('.ask-composer[data-context="home"]').count() == 1)
    check("首页上岸小助手明确尚未接入且不冒充回答", "尚未接入" in page.locator('.ask-composer[data-context="home"]').inner_text())
    check("首页上岸小助手文字输入具有可访问名称", page.locator('#ask-home[aria-label="向上岸小助手提问"]').count() == 1)
    check("首页上岸小助手提供语音和发送按钮", page.locator('[data-mic="home"]').count() == 1 and page.locator('[data-send="home"]').count() == 1)

    page.locator('.ask-composer[data-context="home"] .ask-chip').first.click()
    check("推荐问题可写入输入框", bool(page.locator('#ask-home').input_value().strip()), page.locator('#ask-home').input_value())
    page.locator('[data-send="home"]').click()
    check("服务未接入时问题不被清空并明确提示去配置", bool(page.locator('#ask-home').input_value().strip()) and "还没配置" in page.locator('.ask-status[data-context="home"]').inner_text(), page.locator('.ask-status[data-context="home"]').inner_text())
    page.locator('#ask-home').fill('题库加载期间保留这段草稿')
    page.evaluate("window.dispatchEvent(new CustomEvent('sat:bank-loaded',{detail:{cacheHit:true}}))")
    check("完整题库异步就绪不清空首页上岸小助手草稿", page.locator('#ask-home').input_value() == '题库加载期间保留这段草稿', page.locator('#ask-home').input_value())

    page.locator('[data-mic="home"]').click()
    check("语音识别结果进入输入框供确认", "请解释资料分析的思路" in page.locator('#ask-home').input_value(), page.locator('#ask-home').input_value())
    check("语音结束后恢复非录音状态", page.locator('[data-mic="home"]').get_attribute('aria-pressed') == 'false')

    page.evaluate("if(window.LAZY_BANK_STATUS) window.LAZY_BANK_STATUS.loaded=true; switchTab('practice')")
    check("行测一级页使用行测标题", page.locator('.page-heading').first.inner_text().startswith('行测'))
    check("行测一级页集中每日练习模考和错题入口", all(page.get_by_role('button', name=name).count() for name in ['每日研习', '模拟策试', '错题温习']))

    page.evaluate("switchTab('shenlun')")
    check("申论一级页使用申论标题", page.locator('.page-heading').first.inner_text().startswith('申论'))

    page.evaluate("switchTab('growth')")
    check("成长一级页使用成长标题", page.locator('.page-heading').first.inner_text().startswith('成长'))
    check("修业成长提供能力图谱与错题温习", all(page.get_by_role('button', name=name).count() for name in ['能力图谱', '错题温习']))

    page.evaluate("switchTab('ai')")
    check("上岸小助手一级页提供独立文字语音对话框", page.locator('.ask-composer[data-context="ai"]').count() == 1 and page.locator('[data-mic="ai"]').count() == 1)

    page.evaluate("switchTab('more')")
    check("首页提供数据管理", page.locator('#view h3:has-text("数据管理")').count() == 1)

    question = page.evaluate(
        """() => {
          const q={id:'zhize-question-reg',mod:'常识判断',type:'单选',stem:'致泽逐题测试',options:['甲','乙','丙','丁'],answer:0,analysis:'这是题库提供的原始解析。'};
          startQuiz([q],'逐题上岸小助手测试'); pick(0);
          const analysis=document.querySelector('.q-analy.original-analysis');
          const ask=document.querySelector('.question-ask');
          return {original:analysis?.innerText||'',ask:!!ask,after:!!(analysis&&ask&&(analysis.compareDocumentPosition(ask)&Node.DOCUMENT_POSITION_FOLLOWING)),context:ask?.querySelector('.question-context')?.innerText||''};
        }"""
    )
    check("作答后明确标识题库原始解析", '题库原始解析' in question['original'], str(question))
    check("上岸小助手逐题对话框位于原始解析之后", question['ask'] and question['after'], str(question))
    check("逐题上岸小助手显示当前题目与我的答案上下文", '当前题目' in question['context'] and '我的答案 A' in question['context'], str(question))
    page.evaluate("finishQuiz(); reviewQuiz()")
    check("逐题回顾同样保留上岸小助手入口", page.locator('.question-ask .ask-composer[data-context="question"]').count() == 1)

    check("阶段2至4无JavaScript运行错误", not errors, str(errors[:5]))
    browser.close()

print(f"==== 致泽正式UI阶段2至4：通过 {24-len(fails)}/24，失败 {fails or '无'} ====")
raise SystemExit(1 if fails else 0)
