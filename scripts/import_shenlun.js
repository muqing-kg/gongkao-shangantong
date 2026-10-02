// ============================================================
// 致泽学堂 · 国考申论真题导入器
//
// 数据来源：GitHub 公开仓库 wunian-10086/kaogong-shuati 的申论部分
//   （原始数据是从国考申论 PDF 扫描件 OCR 出来的，见该仓库 data/catalog.js）
//   仅用于个人学习，版权归原始题库方所有。
//
// 用法：
//   1) 下载该仓库的 data/banks-1.js ~ banks-5.js 到任意目录
//   2) node scripts/import_shenlun.js <该目录> [输出路径]
//
// 只导入 12 份国考真题（2022-2025 副省/地市/行政执法）。
// 刻意丢掉该仓库的「申论100题」：它的 stem 只是标题标签（如"2025 浙江（C类）第一题"），
// reference 里混着答案要点、材料片段与解析步骤，结构不可用。
// ============================================================
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const SRC = process.argv[2];
const OUT = process.argv[3] || path.join(__dirname, '..', 'js', 'bank', 'shenlun-papers.js');

if (!SRC) {
  console.error('用法: node scripts/import_shenlun.js <banks 所在目录> [输出路径]');
  process.exit(1);
}

// OCR 文本里有大量句中换行（"案例各\n自体现出"），合并掉；
// 句末标点后的换行保留，那是真正的分段。
function joinWraps(s) {
  return String(s || '').replace(/\r/g, '').replace(/([^。！？；：\n])\n(?=[^\n])/g, '$1');
}
const clean = s => joinWraps(s).trim();

const papers = [];
for (const f of ['banks-1.js', 'banks-2.js', 'banks-3.js', 'banks-4.js', 'banks-5.js']) {
  const p = path.join(SRC, f);
  if (!fs.existsSync(p)) continue;
  const ctx = vm.createContext({ window: {} });
  vm.runInContext(fs.readFileSync(p, 'utf8'), ctx);
  for (const b of ctx.window.__BANKS__ || []) {
    if (!b || b.subject !== '申论') continue;
    if (String(b.id).startsWith('shenlun100')) continue;   // 结构不可用，丢弃

    const questions = (b.questions || []).map(q => {
      const o = {
        no: q.no, module: clean(q.module), stem: clean(q.stem),
        score: q.score || 0, word_limit: q.word_limit || 0,
      };
      if (q.reference) o.reference = clean(q.reference);
      if (Array.isArray(q.points) && q.points.length) o.points = q.points.map(clean).filter(Boolean);
      const exp = clean(q.explanation);
      if (exp && exp !== o.reference) o.explanation = exp;
      return o;
    }).filter(q => q.stem && q.stem.length >= 20);          // 题干太短的丢掉

    if (!questions.length) continue;
    papers.push({
      id: b.id, title: clean(b.title), year: b.year || '', variant: clean(b.variant),
      duration_min: b.duration_min || 0, total_score: b.total_score || 0,
      materials: (b.materials || []).map(m => ({ name: clean(m.name), text: clean(m.text) })).filter(m => m.text),
      questions,
    });
  }
}

if (!papers.length) {
  console.error('没有解析到任何申论卷，请检查 <目录> 里是否有 banks-*.js');
  process.exit(1);
}

const js = '/* 致泽学堂 · 国考申论真题库（2022-2025 副省/地市/行政执法）\n'
  + ' * 数据来源：GitHub 公开仓库 wunian-10086/kaogong-shuati（原始为国考申论 PDF 的 OCR 结果）。\n'
  + ' * 仅用于个人学习，版权归原始题库方所有。由 scripts/import_shenlun.js 生成，请勿手改。\n'
  + ' */\nwindow.SHENLUN_PAPERS=' + JSON.stringify(papers) + ';\n';
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, js, 'utf8');

const totalQ = papers.reduce((s, p) => s + p.questions.length, 0);
const matChars = papers.reduce((s, p) => s + p.materials.reduce((a, m) => a + m.text.length, 0), 0);
const withRef = papers.reduce((s, p) => s + p.questions.filter(q => q.reference).length, 0);
console.log(`输出 ${OUT}`);
console.log(`  卷数 ${papers.length} · 题数 ${totalQ} · 有参考答案 ${withRef}`);
console.log(`  材料 ${papers.reduce((s, p) => s + p.materials.length, 0)} 段 / ${(matChars / 10000).toFixed(1)} 万字`);
console.log(`  文件 ${(Buffer.byteLength(js) / 1024).toFixed(0)} KB`);
