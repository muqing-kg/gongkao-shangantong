# -*- coding: utf-8 -*-
"""致泽学堂 v2.7 配速诊断验收。

针对「行测做不完 + 正确率上不去」：把已记录的每题用时（attempts[].dur）
变成「时间花在哪、该放弃什么」的四象限结论。

守三件事：
1. 样本不足时不下结论（不给假精确）；
2. 四象限按她自己数据的中位数划分，不引入任何外部「标准用时」；
3. 时间黑洞与基本盘的判定、超时题统计、页面渲染都正确。
"""
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


# 构造数据：4 个模块各 8 题
#   资料分析 100s / 4对8 = 50%     数量关系 110s / 3对8 = 38%  -> 慢且弱 = 时间黑洞
#   常识判断  25s / 7对8 = 88%     言语理解  45s / 6对8 = 75%  -> 快且强 = 优势区
# 用时中位数 = (45+100)/2 = 72.5 -> 73
# 正确率中位数 = (50+75)/2 = 62.5 -> 63
SEED = """
  const mk=(mod,dur,nOk,n)=>{ const out=[]; for(let i=0;i<n;i++)
    out.push({t:Date.now(),d:today(),qid:mod+i,mod,ok:i<nOk,src:'2024·省考',point:'考点'+i,
              rate:60,dur,multi:false,type:'真题',txn:''}); return out; };
  store.attempts=[...mk('资料分析',100,4,8),...mk('常识判断',25,7,8),
                  ...mk('言语理解',45,6,8),...mk('数量关系',110,3,8)];
  save();
"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(URL, wait_until='domcontentloaded', timeout=120000)
    # 题库加载完成时若停在首页会自动 renderDash()，会覆盖直接渲染的视图；先等题库就绪以消除该竞态
    page.wait_for_function(
        "() => window.LAZY_BANK_STATUS && window.LAZY_BANK_STATUS.loaded", timeout=120000)

    # ---------- 1. 样本不足时不下结论 ----------
    few = page.evaluate('''() => {
      store.attempts = [{t:Date.now(),d:today(),qid:'a',mod:'常识判断',ok:true,src:'',point:'',
                         rate:60,dur:30,multi:false,type:'',txn:''}];
      save();
      return {diag: paceDiag(), card: paceCardHtml()};
    }''')
    check('样本不足时 paceDiag 返回 null', few['diag'] is None, str(few['diag']))
    check('样本不足时不渲染配速卡', few['card'] == '', str(few['card'])[:80])

    # ---------- 2. 四象限判定 ----------
    diag = page.evaluate("() => {" + SEED + """
      const p = paceDiag();
      return {n:p.n, overall:p.overall, over:p.over, medDur:p.medDur, medAcc:p.medAcc,
              rows:p.rows.map(r=>({mod:r.mod,avg:r.avg,acc:r.acc,zone:r.zone})),
              hole:p.hole&&p.hole.mod, base:p.base&&p.base.mod};
    }""")
    check('样本量正确', diag['n'] == 32, str(diag['n']))
    check('平均每题用时正确', diag['overall'] == 70, str(diag['overall']))
    check('超时题（≥90秒）统计正确', diag['over'] == 16, str(diag['over']))
    check('用时中位数按自身数据取', diag['medDur'] == 73, str(diag['medDur']))
    check('正确率中位数按自身数据取', diag['medAcc'] == 63, str(diag['medAcc']))

    zones = {r['mod']: r['zone'] for r in diag['rows']}
    check('资料分析 = 又慢又错', zones.get('资料分析') == 'slowweak', str(zones))
    check('数量关系 = 又慢又错', zones.get('数量关系') == 'slowweak', str(zones))
    check('常识判断 = 快且准', zones.get('常识判断') == 'faststrong', str(zones))
    check('言语理解 = 快且准', zones.get('言语理解') == 'faststrong', str(zones))
    check('时间黑洞取最慢的那个', diag['hole'] == '数量关系', str(diag['hole']))
    check('基本盘取正确率最高的', diag['base'] == '常识判断', str(diag['base']))

    rows = {r['mod']: r for r in diag['rows']}
    check('模块平均用时计算正确',
          rows['资料分析']['avg'] == 100 and rows['常识判断']['avg'] == 25, str(rows))
    check('模块正确率计算正确',
          rows['资料分析']['acc'] == 50 and rows['常识判断']['acc'] == 88, str(rows))

    # ---------- 3. 页面渲染 ----------
    page.evaluate("renderAnalysis()")
    page.wait_for_timeout(300)
    txt = page.locator('#view').inner_text()
    check('能力分析页出现配速诊断卡', '配速诊断' in txt)
    check('显示平均每题用时', '平均每题 70 秒' in txt, txt[:200])
    check('显示超时题占比', '16 题（50%）单题超过 90 秒' in txt)
    check('点名时间黑洞', '数量关系' in txt and '时间黑洞' in txt)
    check('给出取舍建议', '放到最后' in txt and '果断蒙一个' in txt)
    check('点名基本盘', '常识判断' in txt and '基本盘' in txt)
    check('教她用自己的卷面算预算', '总时长 ÷ 总题量' in txt)
    # 不引入外部基准：卡片里不应出现任何硬编码的「每秒/每题」参考值
    check('未引入外部标准用时',
          '标准用时' not in txt and '建议每题' not in txt and '参考用时' not in txt)

    # ---------- 4. 边界：单模块时不出结论 ----------
    one = page.evaluate('''() => {
      store.attempts = Array.from({length:30},(_,i)=>({t:Date.now(),d:today(),qid:'x'+i,
        mod:'常识判断',ok:true,src:'',point:'',rate:60,dur:30,multi:false,type:'',txn:''}));
      save();
      return paceDiag();
    }''')
    check('只有一个模块时不下结论', one is None, str(one))

    check('无 JS 运行错误', not errors, str(errors[:3]))
    browser.close()

print(f'==== v2.7 配速诊断验收：通过 {checks - len(fails)}/{checks}，失败 {fails or "无"} ====')
raise SystemExit(1 if fails else 0)
