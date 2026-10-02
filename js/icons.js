/* ============ 同舟共济 · 图标系统 ============ */
/* 手绘 SVG 图标，替代原来散落各处的 emoji。
   为什么不用 emoji：字形随系统变、无法跟随主题换色、深浅背景下表现不可控、
   且与「可爱但不喧宾夺主」的调性对不上。
   这套图标统一 24 视框、1.8 描边、圆头圆角，风格偏圆润。

   用法：${ico('book')}  或  ico('book','lg') */
const ICON_PATHS = {
  /* 导航 */
  home: '<path d="M4 10.6 12 4.2l8 6.4V19a1.6 1.6 0 0 1-1.6 1.6H5.6A1.6 1.6 0 0 1 4 19z"/><path d="M9.6 20.6v-5.8h4.8v5.8"/>',
  book: '<path d="M12 6.6C10 4.9 7.3 4.1 4 4.1v12.8c3.3 0 6 .8 8 2.5 2-1.7 4.7-2.5 8-2.5V4.1c-3.3 0-6 .8-8 2.5Z"/><path d="M12 6.6v12.8"/>',
  pen: '<path d="M4.2 19.8l.9-4.2L15.4 5.3a2.2 2.2 0 0 1 3.1 3.1L8.4 18.9l-4.2.9Z"/><path d="M14.2 6.5l3.3 3.3"/>',
  chart: '<path d="M4 20.2h16"/><rect x="5.6" y="11.4" width="3.6" height="6" rx="1.3"/><rect x="10.2" y="7" width="3.6" height="10.4" rx="1.3"/><rect x="14.8" y="13.6" width="3.6" height="3.8" rx="1.3"/>',
  spark: '<path d="M12 4c.7 3.6 1.7 4.6 5.3 5.3-3.6.7-4.6 1.7-5.3 5.3-.7-3.6-1.7-4.6-5.3-5.3C10.3 8.6 11.3 7.6 12 4Z"/><path d="M18 15.2c.3 1.5.7 1.9 2.2 2.2-1.5.3-1.9.7-2.2 2.2-.3-1.5-.7-1.9-2.2-2.2 1.5-.3 1.9-.7 2.2-2.2Z"/>',

  /* 六个模块 */
  gov: '<path d="M3.4 9.6 12 4.2l8.6 5.4z"/><path d="M5.8 20V11M10 20V11M14 20V11M18.2 20V11"/><path d="M4 20.2h16"/>',
  bulb: '<path d="M12 3.2a6.2 6.2 0 0 0-3.6 11.3c.5.4.8 1 .8 1.6v.5h5.6v-.5c0-.6.3-1.2.8-1.6A6.2 6.2 0 0 0 12 3.2Z"/><path d="M9.6 19.4h4.8M10.4 21.4h3.2"/>',
  speech: '<path d="M20.2 11.6a7.4 7.4 0 0 1-7.4 7.4H8.2l-4 3v-4.4a7.4 7.4 0 0 1 6.4-11.9h2.2a7.4 7.4 0 0 1 7.4 7.4Z"/><path d="M9 11.6h6"/>',
  number: '<rect x="5" y="3.4" width="14" height="17.2" rx="3.4"/><path d="M8.6 7.8h6.8"/><circle cx="9.2" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="14.8" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="9.2" cy="16.4" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="16.4" r="1" fill="currentColor" stroke="none"/><circle cx="14.8" cy="16.4" r="1" fill="currentColor" stroke="none"/>',
  puzzle: '<path d="M9.8 4.6a2.2 2.2 0 1 1 4.4 0v1.2h3.4a1.2 1.2 0 0 1 1.2 1.2v3.2h1.2a2.2 2.2 0 1 1 0 4.4h-1.2V18a1.2 1.2 0 0 1-1.2 1.2H14v1.2a2.2 2.2 0 1 1-4.4 0v-1.2H6.2A1.2 1.2 0 0 1 5 18v-3.2H3.8a2.2 2.2 0 1 1 0-4.4H5V7a1.2 1.2 0 0 1 1.2-1.2h3.6Z"/>',
  pie: '<circle cx="12" cy="12" r="8.4"/><path d="M12 3.6V12l7.3 4.2"/>',

  /* 功能卡 */
  target: '<circle cx="12" cy="12" r="8.4"/><circle cx="12" cy="12" r="4.4"/><circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none"/>',
  clock: '<circle cx="12" cy="12" r="8.4"/><path d="M12 7v5.4l3.4 2"/>',
  compass: '<circle cx="12" cy="12" r="8.4"/><path d="m15.2 8.8-1.9 4.5-4.5 1.9 1.9-4.5z"/>',
  trendUp: '<path d="M4 16.6 9 11.6l3.4 3.4L20 7.4"/><path d="M15.6 7.4H20v4.4"/>',
  trendDown: '<path d="M4 7.4 9 12.4l3.4-3.4L20 16.6"/><path d="M15.6 16.6H20v-4.4"/>',
  search: '<circle cx="11" cy="11" r="6.6"/><path d="m15.8 15.8 4.4 4.4"/>',
  doc: '<path d="M6.2 3.4h7.2L19 9v11.6a1.4 1.4 0 0 1-1.4 1.4H6.2a1.4 1.4 0 0 1-1.4-1.4V4.8a1.4 1.4 0 0 1 1.4-1.4Z"/><path d="M13.2 3.4V9H19"/><path d="M8.4 13.4h7.2M8.4 16.6h4.8"/>',
  list: '<path d="M8.6 6.6h11M8.6 12h11M8.6 17.4h11"/><circle cx="4.6" cy="6.6" r="1.2" fill="currentColor" stroke="none"/><circle cx="4.6" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="4.6" cy="17.4" r="1.2" fill="currentColor" stroke="none"/>',
  trophy: '<path d="M7.8 4.4h8.4v5a4.2 4.2 0 0 1-8.4 0z"/><path d="M7.8 6H5.2v1.6a3 3 0 0 0 2.6 2.9M16.2 6h2.6v1.6a3 3 0 0 1-2.6 2.9"/><path d="M12 13.6v3.2M8.8 20.4h6.4l-.6-3.6H9.4z"/>',
  robot: '<rect x="4.4" y="8.2" width="15.2" height="11.4" rx="4.2"/><circle cx="9.6" cy="13.4" r="1.3" fill="currentColor" stroke="none"/><circle cx="14.4" cy="13.4" r="1.3" fill="currentColor" stroke="none"/><path d="M12 8.2V5.4"/><circle cx="12" cy="4.2" r="1.4"/>',

  /* 快捷操作 */
  calendar: '<rect x="4" y="5.6" width="16" height="14.8" rx="3.4"/><path d="M4 10.6h16M8.6 3.4v4.2M15.4 3.4v4.2"/><circle cx="12" cy="15" r="1.1" fill="currentColor" stroke="none"/>',
  dice: '<rect x="4.4" y="4.4" width="15.2" height="15.2" rx="4.4"/><circle cx="9.2" cy="9.2" r="1.25" fill="currentColor" stroke="none"/><circle cx="14.8" cy="14.8" r="1.25" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.25" fill="currentColor" stroke="none"/>',
  inbox: '<path d="M4 13.4 6.4 6.2A2.2 2.2 0 0 1 8.5 4.8h7A2.2 2.2 0 0 1 17.6 6.2L20 13.4v4.2a2.2 2.2 0 0 1-2.2 2.2H6.2A2.2 2.2 0 0 1 4 17.6Z"/><path d="M4 13.4h4.2l.9 2h5.8l.9-2H20"/>',
  print: '<path d="M7.2 8.6V4.4h9.6v4.2"/><rect x="4.2" y="8.6" width="15.6" height="7" rx="2.2"/><path d="M7.2 15.6h9.6v4.2H7.2z"/>',
  download: '<path d="M12 4v10.4"/><path d="m8 10.8 4 4 4-4"/><path d="M5 19.6h14"/>',
  trash: '<path d="M5 7h14"/><path d="M9.6 7V5.6a1.2 1.2 0 0 1 1.2-1.2h2.4a1.2 1.2 0 0 1 1.2 1.2V7"/><path d="M6.6 7v12a1.6 1.6 0 0 0 1.6 1.6h7.6A1.6 1.6 0 0 0 17.4 19V7"/>',
  key: '<circle cx="8.2" cy="14.6" r="3.6"/><path d="m10.8 12 7.8-7.8M16.2 6.6l2.4 2.4M13.8 9l2.4 2.4"/>',
  mic: '<rect x="9.2" y="3.4" width="5.6" height="10.2" rx="2.8"/><path d="M5.8 11.6a6.2 6.2 0 0 0 12.4 0"/><path d="M12 17.8v2.8"/>',

  /* 状态 */
  check: '<path d="m5 12.6 4.6 4.6L19 7"/>',
  cross: '<path d="m6.6 6.6 10.8 10.8M17.4 6.6 6.6 17.4"/>',
  flag: '<path d="M6.2 20.6V4.2"/><path d="M6.2 5.2h10.6l-1.9 3.6 1.9 3.6H6.2"/>',
  alert: '<path d="M12 4.4 21 19.6H3z"/><path d="M12 10v3.8"/><circle cx="12" cy="16.8" r="1" fill="currentColor" stroke="none"/>',
  arrowLeft: '<path d="M19 12H5"/><path d="m11 6-6 6 6 6"/>',
  arrowRight: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',

  /* 补：替换剩余 emoji 所需 */
  bolt: '<path d="M13.4 3 5.6 13.2h5.2L10.6 21l7.8-10.2h-5.2z"/>',
  play: '<path d="M7.4 5.2 18.6 12 7.4 18.8z"/>',
  star: '<path d="m12 4 2.5 5.1 5.6.8-4 3.9 1 5.6-5.1-2.7-5.1 2.7 1-5.6-4-3.9 5.6-.8z"/>',
  tag: '<path d="M4.2 11.4 11.4 4.2h7.2a1.2 1.2 0 0 1 1.2 1.2v7.2L12.6 19.8a1.6 1.6 0 0 1-2.3 0L4.2 13.7a1.6 1.6 0 0 1 0-2.3Z"/><circle cx="16" cy="8" r="1.3" fill="currentColor" stroke="none"/>',
  shield: '<path d="M12 3.4 5 6.2v5.4c0 4.2 2.9 7.6 7 9 4.1-1.4 7-4.8 7-9V6.2z"/><path d="m9.2 12 2 2 3.6-3.8"/>',
  archive: '<rect x="3.6" y="4.6" width="16.8" height="4.2" rx="1.6"/><path d="M5.4 8.8v9.2a1.6 1.6 0 0 0 1.6 1.6h10a1.6 1.6 0 0 0 1.6-1.6V8.8"/><path d="M10 12.6h4"/>',
  outbox: '<path d="M4 13.4 6.4 6.2A2.2 2.2 0 0 1 8.5 4.8h7A2.2 2.2 0 0 1 17.6 6.2L20 13.4v4.2a2.2 2.2 0 0 1-2.2 2.2H6.2A2.2 2.2 0 0 1 4 17.6Z"/><path d="M4 13.4h4.2l.9 2h5.8l.9-2H20"/><path d="M12 10.6V6.4m0 0L10.2 8.2M12 6.4l1.8 1.8"/>',
  coffee: '<path d="M4.6 7h12v6.6a4.4 4.4 0 0 1-4.4 4.4H9a4.4 4.4 0 0 1-4.4-4.4z"/><path d="M16.6 8.6h1.6a2.4 2.4 0 0 1 0 4.8h-1.6"/><path d="M4 20.6h13"/>',
  home2: '<path d="M4 10.6 12 4.2l8 6.4V19a1.6 1.6 0 0 1-1.6 1.6H5.6A1.6 1.6 0 0 1 4 19z"/>'
};

function ico(name, cls) {
  return '<svg class="ico' + (cls ? ' ' + cls : '') + '" aria-hidden="true"><use href="#i-' + name + '"></use></svg>';
}

/* 把 sprite 同步注入 DOM（本脚本在 body 末尾、app.js 之前加载） */
(function () {
  const wrap = document.createElement('div');
  wrap.innerHTML = '<svg id="ico-sprite" aria-hidden="true" focusable="false" ' +
    'style="position:absolute;width:0;height:0;overflow:hidden">' +
    Object.keys(ICON_PATHS).map(function (k) {
      return '<symbol id="i-' + k + '" viewBox="0 0 24 24">' + ICON_PATHS[k] + '</symbol>';
    }).join('') + '</svg>';
  document.body.insertBefore(wrap.firstChild, document.body.firstChild);
})();
