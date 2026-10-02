# 同舟共济

> 公务员考试学习与成长平台。题库、错题本、申论批改、能力画像，还有一个能陪她说话的小助手。
>
> 一起渡过这段路。

纯前端 + 一个轻量服务端。学习数据默认存在浏览器本地，登录后可同步到自己的服务器，管理端能看到学习情况。

---

## 功能

**行测**

- **12,908 道真题**，全部来自历年真题（国考 2008–2026、省考 2020–2026、选调 2013–2025），**不含模拟题、原创题**
- 精确去重为 0 重复；3,249 道题聚合了多个来源，可显示年份、考试、地区卷别与原卷题号
- 六模块：政治理论 465 · 常识判断 4,182 · 言语理解 2,607 · 数量关系 983 · 判断推理 2,980 · 资料分析 1,691
- 每日一练（按日期做种子，同一天固定一组）· 随机刷题 · 错题重练 · 模拟考试 · 卷种定制组卷
- 题库懒加载 + IndexedDB 持久缓存，首屏不等题库

**申论**

- 12 卷 59 道真题
- 练笔 + AI 批改（按测评维度给参考反馈，**不给分数**）
- 素材库：名言金句、时政热点、案例素材、写作框架、应用文模板

**学习与成长**

- 学习计划（目标、考试日期、每日题量）
- 能力画像：模块正确率、用时配速、失分结构、错因占比
- 错题本 + 艾宾浩斯复习（1/2/4/7/15 天）
- 打卡与连续天数

**上岸小助手（AI）**

- 逐题讲解、学情诊断、学习计划、通用问答，支持语音输入
- **AI 不判分**：逐题讲解以题库原始解析为唯一权威；申论批改不给分数并要求引用原文
- AI 的 Key 只存在服务端，学习端拿不到

**管理后台**

- 学习进度监控：最后活跃、累计做题、总正确率、累计学习时长
- 学习动态（近 30 天）：每天首次/末次进入时间、学习时长、做题数
- 模块掌握度（从弱到强）
- 系统配置：AI 接口地址 / 模型 / Key
- 给她留一句话，显示在她的首页

---

## 目录结构

```
├── index.html          学习端
├── login.html          登录页（一个密码框，自动判身份）
├── admin.html          管理后台
├── css/
│   ├── style.css       基础样式与设计变量
│   ├── ai.css          AI 输出排版
│   └── patch.css       补齐的缺失样式
├── js/
│   ├── app.js          主程序（视图路由、答题引擎、各功能）
│   ├── ai.js           AI 接入层（OpenAI 兼容接口）
│   ├── icons.js        手绘 SVG 图标（44 个）
│   ├── lazy-bank.js    题库懒加载 + IndexedDB 缓存
│   ├── sync.js         登录守卫 + 学习数据同步
│   ├── easter.js       随手会冒出来的小话
│   ├── questions*.js   题库分片
│   └── shenlun.js      申论素材
├── server/
│   ├── index.js        服务端（登录 / 同步 / AI 代理 / 后台）
│   └── set-password.js 设置密码
├── assets/             图片与插画
├── scripts/            测试与维护工具
└── docs/               各版本实现记录
```

---

## 部署

### 1. 设密码

```bash
node server/set-password.js user  <她的密码>
node server/set-password.js admin <管理密码>
```

密码用 scrypt + 随机盐哈希后存进 `server/data/db.json`，明文不落盘、不进 Git。

### 2. 启动

```bash
node server/index.js
```

默认监听 `127.0.0.1:8848`。环境变量：`PORT`、`DATA_DIR`。

### 3. 访问

- `http://<服务器>:8848/` → 未登录自动跳登录页
- 输入**学习密码** → 进学习端
- 输入**管理密码** → 进管理后台

### 4. 反向代理（可选）

Nginx / OpenResty 示例：

```nginx
server {
    listen 443 ssl http2;
    server_name your.domain;

    # 题库与图片体积大，务必开 gzip
    gzip on;
    gzip_types application/javascript text/css application/json image/svg+xml;
    gzip_min_length 1024;

    location / {
        proxy_pass http://127.0.0.1:8848;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 图片长期不变，强缓存
    location /assets/img/ {
        proxy_pass http://127.0.0.1:8848;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

**部署时必须改 `index.html` 里各资源的 `?v=` 版本号** —— 本项目靠查询参数做缓存失效，改了文件不改版本号，用户会一直拿到旧文件。

---

## 安全

| 项 | 做法 |
|---|---|
| 密码 | scrypt + 随机盐哈希，明文不落盘 |
| 会话 | HttpOnly + SameSite Cookie，JS 读不到 |
| 登录限速 | 同 IP 每分钟 5 次 |
| 越权 | 学习端访问后台页面 → 302；调后台接口 → 403 |
| AI Key | 只存服务端，接口不回显，学习端拿不到 |
| 备份 | 导出的 JSON 不含 AI 配置 |
| 注入 | 所有用户输入与 AI 输出经 `esc()` / `mdToHtml()` 转义，已实测 5 个注入点 |

---

## 测试

```bash
# 学习端（需先起静态服务器：python -m http.server 8140 --bind 127.0.0.1）
$env:SAT_TEST_URL='http://127.0.0.1:8140/index.html'
python scripts/test_v01.py
# …共 20 个

# 服务端（需先设密码并启动）
python scripts/test_server.py
```

覆盖：题库质量、缓存、回归、UI、学习计划、配速、错因、AI 接入、问答、申论、Markdown 渲染、安全阻断项、服务端权限。

---

## 题库维护

```bash
node scripts/import_shenlun.js      # 导入申论真题
python scripts/dedupe_bank.py       # 精确去重
python scripts/localize_images.py   # 图片本地化
python scripts/prune_broken_images.py
```

题库只收真题。新增题目后需同步更新 `js/bank/questions-zhenti-manifest.json` 与 `index.html` 的版本号。

---

## License

MIT
