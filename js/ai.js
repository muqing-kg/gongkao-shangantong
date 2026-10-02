/* 致泽学堂 · AI 接入层（OpenAI 兼容）
 *
 * 设计要点：
 * 1. 配置存独立 localStorage（zhize_ai_cfg_v1），**不随学习数据备份导出**——
 *    否则导出备份就把 API Key 一起送出去了。
 * 2. 已实测 api.deepseek.com 支持浏览器 CORS（回显 Origin、允许 authorization 头），
 *    因此纯前端可直连，不需要后端。若目标端点不支持 CORS，把「接口地址」填成
 *    自己的代理地址即可，本层不区分二者。
 * 3. 只做传输与错误翻译，不含任何业务 prompt。
 */
(() => {
  const CFG_KEY = 'zhize_ai_cfg_v1';
  const DEF = { url: 'https://api.deepseek.com/v1/chat/completions', model: 'deepseek-flash', key: '' };

  function loadCfg(){
    try{
      const raw = JSON.parse(localStorage.getItem(CFG_KEY) || '{}');
      return (raw && typeof raw === 'object') ? { ...DEF, ...raw } : { ...DEF };
    }catch(_){ return { ...DEF }; }
  }
  function saveCfg(next){
    const cur = loadCfg();
    const clean = s => String(s ?? '').trim();
    const merged = {
      url: clean(next.url ?? cur.url).replace(/\/+$/, ''),
      model: clean(next.model ?? cur.model),
      key: clean(next.key ?? cur.key),
    };
    try{ localStorage.setItem(CFG_KEY, JSON.stringify(merged)); }catch(_){ /* 存储不可用时仅本次生效 */ }
    return merged;
  }
  /* 「已配置」必须含 Key：默认值已预填地址与模型，只看这两项会误判成已就绪。
     （若目标是不需要 Key 的本地代理，填任意占位串即可。） */
  function ready(){ const c = loadCfg(); return !!(c.url && c.model && c.key); }

  /* 把 HTTP 状态翻译成用户能照做的动作，而不是甩一个 401 出去 */
  function describeHttpError(status, body){
    const brief = String(body || '').replace(/\s+/g, ' ').slice(0, 160);
    if(status === 401 || status === 403) return 'AI 鉴权失败：请检查 API Key 是否填对、是否已过期';
    if(status === 404) return 'AI 接口地址不对（404）：请检查地址是否以 /v1/chat/completions 结尾';
    if(status === 429) return 'AI 提示请求过于频繁或额度不足（429），稍后再试';
    if(status >= 500) return `AI 服务端错误（${status}），稍后重试`;
    return `AI 请求失败（${status}）${brief ? '：' + brief : ''}`;
  }

  async function chat(messages, opts = {}){
    const c = loadCfg();
    if(!c.url || !c.model) throw new Error('尚未配置 AI 接口，请到「我的书斋 → AI 接入」填写');
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs || 90000);
    try{
      const res = await fetch(c.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(c.key ? { Authorization: 'Bearer ' + c.key } : {}),
        },
        body: JSON.stringify({
          model: c.model,
          messages,
          temperature: opts.temperature ?? 0.3,
          max_tokens: opts.maxTokens ?? 1200,
          stream: false,
        }),
        signal: ctrl.signal,
      });
      if(!res.ok){
        const text = await res.text().catch(() => '');
        throw new Error(describeHttpError(res.status, text));
      }
      const data = await res.json();
      const out = data?.choices?.[0]?.message?.content;
      if(typeof out !== 'string' || !out.trim()) throw new Error('AI 返回内容为空，请重试');
      return out.trim();
    }catch(err){
      if(err?.name === 'AbortError') throw new Error('AI 请求超时，请重试');
      if(err instanceof TypeError) throw new Error('连不上 AI 接口：可能是网络不通，或该接口不允许浏览器直连（CORS）');
      throw err;
    }finally{
      clearTimeout(timer);
    }
  }

  /* 从对话地址推出模型列表地址：
     .../v1/chat/completions → .../v1/models
     不以 /chat/completions 结尾时，直接在末尾接 /models */
  function modelsUrl(chatUrl){
    const u = String(chatUrl || '').trim().replace(/\/+$/, '');
    return /\/chat\/completions$/.test(u) ? u.replace(/\/chat\/completions$/, '/models') : u + '/models';
  }

  async function listModels(){
    const c = loadCfg();
    if(!c.url) throw new Error('请先填写接口地址');
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 30000);
    try{
      const res = await fetch(modelsUrl(c.url), {
        method: 'GET',
        headers: { ...(c.key ? { Authorization: 'Bearer ' + c.key } : {}) },
        signal: ctrl.signal,
      });
      if(!res.ok){
        const text = await res.text().catch(() => '');
        throw new Error(describeHttpError(res.status, text));
      }
      const data = await res.json();
      const ids = Array.isArray(data?.data)
        ? data.data.map(m => m && m.id).filter(x => typeof x === 'string' && x)
        : [];
      return [...new Set(ids)].sort();
    }catch(err){
      if(err?.name === 'AbortError') throw new Error('获取模型列表超时，请重试');
      if(err instanceof TypeError) throw new Error('连不上 AI 接口：可能是网络不通，或该接口不允许浏览器直连（CORS）');
      throw err;
    }finally{
      clearTimeout(timer);
    }
  }

  /* 配置搬运：主人配好一次，导出成一段文本发给对方粘贴导入，
     省掉在手机上敲 URL 和一长串 Key。前缀用于识别内容是否对得上。 */
  const CFG_PREFIX = 'ZSAI1:';
  function b64encode(s){
    const bytes = new TextEncoder().encode(s);
    let bin = '';
    for(const b of bytes) bin += String.fromCharCode(b);
    return btoa(bin);
  }
  function b64decode(s){
    const bin = atob(s);
    const bytes = new Uint8Array(bin.length);
    for(let i=0;i<bin.length;i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder().decode(bytes);
  }
  function exportCfg(){
    const c = loadCfg();
    return CFG_PREFIX + b64encode(JSON.stringify({ url:c.url, model:c.model, key:c.key }));
  }
  function importCfg(text){
    const raw = String(text || '').trim().replace(/\s+/g, '');
    if(!raw) throw new Error('请先粘贴配置内容');
    const body = raw.startsWith(CFG_PREFIX) ? raw.slice(CFG_PREFIX.length) : raw;
    let obj;
    try{ obj = JSON.parse(b64decode(body)); }
    catch(_){ throw new Error('配置内容无法识别，请确认整段复制完整'); }
    if(!obj || typeof obj !== 'object' || !obj.url) throw new Error('配置里没有接口地址');
    return saveCfg(obj);
  }

  window.AI = { loadCfg, saveCfg, ready, chat, listModels, modelsUrl, describeHttpError,
                exportCfg, importCfg, CFG_KEY, DEF, CFG_PREFIX };
})();
