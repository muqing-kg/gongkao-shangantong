# -*- coding: utf-8 -*-
"""同舟共济正式 UI v2.4：阶段 1 品牌壳、导航分组与环境偏好。"""
import os
from playwright.sync_api import sync_playwright

URL = os.environ.get("SAT_TEST_URL", "http://127.0.0.1:8140/index.html?v=zhize-production-red")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
fails = []


def check(name, ok, detail=""):
    print(f'[{"PASS" if ok else "FAIL"}] {name} {detail}')
    if not ok:
        fails.append(name)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(URL, wait_until="domcontentloaded", timeout=120000)

    check("页面标题使用同舟共济", "同舟共济" in page.title(), page.title())
    check(
        "品牌区使用致泽名称与主标语",
        page.locator(".brand-name").inner_text().splitlines() == ["同舟共济", "一起渡过这段路"],
        page.locator(".brand-name").inner_text(),
    )
    check("品牌图标使用生成的小舟插画", page.locator('.brand-logo img[src*="logo-boat"]').count() == 1)

    expected = ["首页", "行测", "申论", "成长", "上岸小助手"]
    labels = page.locator(".tabbar .tab").all_inner_texts()
    check("桌面一级导航顺序正确", labels == expected, str(labels))
    check("桌面一级导航五项均可见", page.locator(".tabbar .tab:visible").count() == 5)

    grouped = page.evaluate(
        """() => {
          if(window.LAZY_BANK_STATUS) window.LAZY_BANK_STATUS.loaded=true;
          switchTab('exam');
          const active=document.querySelector('.tab[aria-current="page"]');
          return {active:active?.dataset.view,current:currentView()};
        }"""
    )
    check("旧行测子路由仍点亮行测一级入口", grouped == {"active": "practice", "current": "exam"}, str(grouped))

    page.set_viewport_size({"width": 390, "height": 844})
    page.evaluate("switchTab('dashboard')")
    mobile = page.evaluate(
        """() => ({
          position:getComputedStyle(document.querySelector('.tabbar')).position,
          visible:[...document.querySelectorAll('.tabbar .tab')]
            .filter(x=>getComputedStyle(x).display!=='none').map(x=>x.textContent.trim()),
          askVisible:getComputedStyle(document.querySelector('.top-ask')).display!=='none',
          overflow:document.documentElement.scrollWidth<=document.documentElement.clientWidth,
        })"""
    )
    check("移动端使用固定底栏", mobile["position"] == "fixed", str(mobile))
    check("移动端底栏保留五项且顶部提供问泽", mobile["visible"] == ["首页", "行测", "申论", "成长"] and mobile["askVisible"], str(mobile))
    check("390px 全局壳无横向溢出", mobile["overflow"], str(mobile))
    check("阶段1无JavaScript运行错误", not errors, str(errors[:5]))
    browser.close()

print(f"==== 致泽正式UI阶段1：通过 {12-len(fails)}/12，失败 {fails or '无'} ====")
raise SystemExit(1 if fails else 0)
