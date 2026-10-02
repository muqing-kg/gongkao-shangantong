/* ============ 同舟共济 · 随手会冒出来的小话 ============
   设计原则（改过一次）：
   第一版藏得太深（连点七下、敲 zhou 之类），正常人根本碰不到，等于没有。
   这一版改成「正常用着用着就会遇到」：
     · 交完卷一定有一句
     · 答题时偶尔有一句
     · 每天第一次打开有一句
     · 切页面偶尔有一句
     · 点一下左上角的小船就有一句
   全部只在本机跑，不发任何请求，也不打断任何操作。
*/
(function () {
  'use strict';

  /* ---------- 话池 ---------- */
  const CHEER = [                       // 答对时
    '对了，记一下。',
    '这道稳了。',
    '手感回来了。',
    '就是这个节奏。',
  ];
  const COMFORT = [                     // 答错时
    '错了不要紧，我们一起看。',
    '这题先记下，回头专门收拾它。',
    '别急，错题才是涨分的地方。',
    '没关系，下一道。',
  ];
  const AFTER = [                       // 交完卷
    '今天也辛苦了。',
    '做完了就好，剩下的交给明天。',
    '这些题，都会变成你的。',
    '我一直在这儿。',
    '慢慢来，路是一步一步走的。',
  ];
  const HELLO = [                       // 每天第一次打开
    '今天也一起。',
    '来了就好，不着急。',
    '先做一题暖暖手？',
    '我在。',
  ];
  const CLICK = [                       // 点小船
    '嗯？',
    '我在听。',
    '怎么啦。',
    '想说什么就说。',
    '累了就歇会儿。',
    '你认真的样子很好看。',
  ];

  const pick = a => a[Math.floor(Math.random() * a.length)];
  const todayKey = () => {
    const d = new Date();
    return `sat_egg_${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  };
  const onceADay = key => {
    try {
      if (localStorage.getItem(key)) return false;
      localStorage.setItem(key, '1');
      return true;
    } catch (_) { return false; }
  };

  /* ---------- 浮层 ---------- */
  let current = null;
  function say(text, opts) {
    opts = opts || {};
    /* 同一时刻只留一句：新的顶掉旧的，而不是把新的丢掉
       （之前是丢弃，导致每日问候还没消失时，答题的那句就永远出不来） */
    if (current) {
      clearTimeout(current.timer);
      current.el.remove();
      current = null;
    }
    const el = document.createElement('div');
    el.className = 'egg-note';
    const b = document.createElement('b');
    b.textContent = text;
    el.appendChild(b);
    if (opts.sub) {
      const s = document.createElement('span');
      s.textContent = opts.sub;
      el.appendChild(s);
    }
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('on'));
    const timer = setTimeout(() => {
      el.classList.remove('on');
      setTimeout(() => el.remove(), 400);
      if (current && current.el === el) current = null;
    }, opts.ms || 3000);
    current = { el, timer };
  }
  window.eggSay = say;

  /* ---------- 1. 每天第一次打开 ---------- */
  window.addEventListener('load', () => {
    if (onceADay(todayKey())) {
      setTimeout(() => say(pick(HELLO)), 1400);
    }
  });

  /* ---------- 2. 交完卷：一定有一句 ---------- */
  const result = document.querySelector('#resultLayer');
  if (result) {
    new MutationObserver(() => {
      if (!result.classList.contains('hidden')) {
        setTimeout(() => say(pick(AFTER), { ms: 4200 }), 700);
      }
    }).observe(result, { attributes: true, attributeFilter: ['class'] });
  }

  /* ---------- 3. 答题时偶尔一句 ---------- */
  /* 用事件委托听选项点击：点完一题，约 1/4 概率冒一句 */
  document.addEventListener('click', e => {
    const opt = e.target.closest('.q-opt, .opt, [data-opt]');
    if (!opt) return;
    if (Math.random() > 0.25) return;
    /* 等界面更新完再判断对错 */
    setTimeout(() => {
      /* 注意：.q-opt.correct 标的是「正确答案」，不是「她答对了」。
         只有出现 .q-opt.wrong 才说明她选错了。 */
      const missed = document.querySelector('.q-opt.wrong');
      say(missed ? pick(COMFORT) : pick(CHEER), { ms: 2400 });
    }, 420);
  }, true);

  /* ---------- 4. 切页面偶尔一句（每 6 次左右一次） ---------- */
  if (typeof window.switchTab === 'function') {
    const orig = window.switchTab;
    window.switchTab = function () {
      const r = orig.apply(this, arguments);
      if (Math.random() < 0.18) setTimeout(() => say(pick(CLICK), { ms: 2400 }), 600);
      return r;
    };
  }

  /* ---------- 5. 点一下小船 ---------- */
  const logo = document.querySelector('.brand-logo');
  if (logo) {
    logo.style.cursor = 'pointer';
    logo.addEventListener('click', () => {
      logo.animate(
        [{ transform: 'rotate(0)' }, { transform: 'rotate(-8deg)' }, { transform: 'rotate(6deg)' }, { transform: 'rotate(0)' }],
        { duration: 420, easing: 'ease-in-out' }
      );
      say(pick(CLICK), { ms: 2600 });
    });
  }

  /* ---------- 6. 控制台留言（给会开 F12 的人） ---------- */
  try {
    console.log('%c同舟共济', 'font:700 26px "Songti SC",serif;color:#C08468');
    console.log('%c一起渡过这段路。', 'font:14px "PingFang SC",sans-serif;color:#8A7461');
    console.log('%c点一下左上角那只小船试试。', 'font:12px "PingFang SC",sans-serif;color:#B9A48C');
  } catch (_) {}
})();
