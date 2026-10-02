/* ============ 同舟共济 · 藏在各处的小彩蛋 ============
   都是「不打扰」的设计：不点、不碰、不深夜打开，就完全看不见；
   一旦发现，会心一笑就够了。全部只在本机跑，不发任何请求。
*/
(function () {
  'use strict';

  /* ---------- 0. 控制台留言（打开 F12 才看得到） ---------- */
  try {
    console.log('%c同舟共济', 'font:700 26px "Songti SC",serif;color:#C08468');
    console.log('%c一起渡过这段路。', 'font:14px "PingFang SC",sans-serif;color:#8A7461');
    console.log('%c如果你看到了这行字——说明你和她一样，都爱刨根问底。',
      'font:13px "PingFang SC",sans-serif;color:#8A7461');
    console.log('%c源代码里还藏了几处，慢慢找。', 'font:12px "PingFang SC",sans-serif;color:#B9A48C');
  } catch (_) {}

  /* ---------- 1. 连点船头 7 次：她的小船会晃，并浮出一句话 ---------- */
  (function boat() {
    const logo = document.querySelector('.brand-logo');
    if (!logo) return;
    let n = 0, timer = null;
    logo.style.cursor = 'pointer';
    logo.addEventListener('click', () => {
      n++;
      clearTimeout(timer);
      timer = setTimeout(() => { n = 0; }, 1200);
      logo.animate(
        [{ transform: 'rotate(0)' }, { transform: 'rotate(-9deg)' }, { transform: 'rotate(7deg)' }, { transform: 'rotate(0)' }],
        { duration: 420, easing: 'ease-in-out' }
      );
      if (n === 7) {
        n = 0;
        note('船晃了七下。', '她也在船上，别只顾着划。');
      }
    });
  })();

  /* ---------- 2. 深夜（23:00–05:00）打开：首页换一句问候 ---------- */
  (function lateNight() {
    const h = new Date().getHours();
    if (h < 5 || h >= 23) {
      const patch = () => {
        const el = document.querySelector('.hero .sub');
        if (el && !el.dataset.night) {
          el.dataset.night = '1';
          el.textContent = '这个点了，做两题就睡吧。';
        }
      };
      patch();
      document.addEventListener('sat:bank-loaded', () => setTimeout(patch, 200));
    }
  })();

  /* ---------- 3. 键盘输入「舟」的拼音：浮出一句 ---------- */
  (function konami() {
    const seq = ['z', 'h', 'o', 'u'];
    let i = 0;
    document.addEventListener('keydown', e => {
      if (e.target && /INPUT|TEXTAREA/.test(e.target.tagName)) return;
      i = (e.key.toLowerCase() === seq[i]) ? i + 1 : (e.key.toLowerCase() === seq[0] ? 1 : 0);
      if (i === seq.length) {
        i = 0;
        note('同舟。', '共济。');
      }
    });
  })();

  /* ---------- 4. 连续打卡徽章长按 2 秒：说出真实天数 ---------- */
  (function streakHold() {
    const badge = document.querySelector('#streakBadge');
    if (!badge) return;
    let t = null;
    const start = () => { t = setTimeout(() => {
      const d = (window.getStreak && window.getStreak()) || 0;
      note('已经 ' + d + ' 天了。', d >= 7 ? '比你想的坚持得久。' : '开头最难，先走满七天。');
    }, 2000); };
    const stop = () => clearTimeout(t);
    badge.addEventListener('pointerdown', start);
    badge.addEventListener('pointerup', stop);
    badge.addEventListener('pointerleave', stop);
    badge.addEventListener('pointercancel', stop);
  })();

  /* ---------- 5. 在首页按住 Shift 点空白：掉一行小字 ---------- */
  (function shiftClick() {
    document.addEventListener('click', e => {
      if (!e.shiftKey) return;
      if (e.target.closest('button, a, input, textarea, select')) return;
      const x = e.clientX, y = e.clientY;
      const el = document.createElement('span');
      el.textContent = ['一起', '慢慢来', '别急', '我在', '同舟'][Math.floor(Math.random() * 5)];
      el.style.cssText = `position:fixed;left:${x}px;top:${y}px;z-index:900;pointer-events:none;
        font-size:13px;color:#C08468;font-family:"STKaiti","KaiTi",serif;letter-spacing:1px;
        transform:translate(-50%,-50%);opacity:0;transition:opacity .5s,transform 1.4s ease-out`;
      document.body.appendChild(el);
      requestAnimationFrame(() => {
        el.style.opacity = '1';
        el.style.transform = `translate(-50%,-${90 + Math.random() * 40}px)`;
      });
      setTimeout(() => { el.style.opacity = '0'; }, 900);
      setTimeout(() => el.remove(), 1800);
    });
  })();

  /* ---------- 浮层：统一的彩蛋提示样式 ---------- */
  function note(title, sub) {
    const el = document.createElement('div');
    el.className = 'egg-note';
    el.innerHTML = '<b></b><span></span>';
    el.querySelector('b').textContent = title;
    el.querySelector('span').textContent = sub;
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('on'));
    setTimeout(() => {
      el.classList.remove('on');
      setTimeout(() => el.remove(), 400);
    }, 3400);
  }
})();
