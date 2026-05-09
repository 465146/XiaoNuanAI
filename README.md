# 🫧 小暖 XiaoNuan — AI CBT 心理陪伴伙伴

**2026 年中国大学生计算机设计大赛参赛作品**

小暖是一个基于大语言模型的 CBT（认知行为疗法）心理陪伴 Web 应用，面向大学生心理健康场景，提供 AI 对话疏导、情绪追踪、PHQ-9 抑郁筛查、情绪日记、微信消息接入等功能。

---

## ✨ 功能

| 模块 | 说明 |
|------|------|
| 💬 AI 对话 | SSE 流式输出，Markdown 渲染，直连 DeepSeek API |
| 🎵 音乐点播 | 搜索网易云音乐，APlayer 嵌入式播放器，真正可听 |
| 📊 情绪仪表盘 | 30 天趋势图（ECharts），周度文字报告，情绪指标卡片 |
| 📋 PHQ-9 测评 | 9 题随机乱序，自动分级，Q9 危机预警 + 24h 热线提示 |
| 📝 情绪日记 | 一键 AI 生成，基于当天对话内容 |
| 📱 微信连接 | 每用户独立 bot，扫码绑定，双向消息同步 |
| 🔐 用户系统 | JWT 认证、邮箱验证码注册、自定义 AI 模型配置 |

---

## 🏗 架构

```
Browser (SPA)
   │  ▲
   │  ├── SSE 流式聊天（DeepSeek 直连）
   │  ├── APlayer 播放器 ← /api/music/player ← Meting API / netease-api
   │  └── ECharts 仪表盘 / PHQ-9 / 日记
   ▼  │
FastAPI (uvicorn)
   │
   ├── DeepSeek API（AI 对话 + 音乐搜索关键词注入）
   ├── NeteaseCloudMusicAPI Enhanced (:3000)（歌曲搜索 + URL 解析）
   ├── Public Meting API（备选音源，VIP 歌曲可播）
   ├── OpenClaw Gateway (:18789)（Agent 技能 + 记忆）
   └── MySQL（用户 / 聊天 / 情绪数据）
```

- **日常聊天** → DeepSeek API 直连（SSE 流式输出，低延迟）
- **音乐点歌** → 后端搜歌 → System Prompt 注入链接 → 前端 APlayer 播放
- **记忆系统** → 对话摘要写入文件 → Gateway 工作区索引

### 音乐播放流程

```
用户说"放《成都》"
  → cbt_agent._detect_music_query() 提取关键词"成都"
  → _search_music() 调用端口 3000 的网易云 API 搜索
  → 结果注入 System Prompt："[成都 — 赵雷](https://music.163.com/#/song?id=xxx)"
  → AI 回复包含 Markdown 歌曲链接
  → chat.js embedMusicPlayers() 检测 songId
  → /api/music/player 获取歌名+歌手+封面+播放 URL
  → APlayer 迷你播放器渲染在聊天气泡内 🎵
```

音源两层保障：**① 公共 Meting API** (`api.injahow.cn`) 优先，② **本地 netease-api** 备用。

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vanilla JS SPA + Jinja2 + ECharts + APlayer + Marked.js |
| 后端 | FastAPI + uvicorn + SSE Streaming |
| AI | DeepSeek API（直连）+ OpenClaw Gateway（技能路由） |
| 数据库 | MySQL 8.0（用户、聊天、情绪数据） |
| 音乐 | NeteaseCloudMusicAPI Enhanced + 公共 Meting API + APlayer |
| 认证 | JWT + bcrypt + 邮箱验证码 |
| 部署 | Railway (nixpacks) + start.sh 多进程管理 |

## 🚀 快速开始

### 环境要求

- Python 3.10+
- MySQL 8.0
- Node.js 22+（音乐 API + Gateway）

### 1. 克隆项目

```bash
git clone <repo-url>
cd OpenclawProject
```

### 2. 初始化数据库

```bash
mysql -u root -p < schema.sql
```

创建 `cbt_xiaonuan` 数据库和全部 8 张表。

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY 和数据库连接信息
```

必需环境变量：

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（[获取](https://platform.deepseek.com)） |
| `DATABASE_URL` | MySQL 连接（格式：`mysql://user:pass@host:3306/cbt_xiaonuan`） |

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 5. 启动

**本地开发（仅 Web，无 Gateway）：**

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

访问 http://localhost:8000

**完整启动（Web + 音乐 + Gateway）：**

```bash
bash start.sh
```

`start.sh` 会依次启动：
1. 音乐 API（端口 3000）
2. OpenClaw Gateway（端口 18789）
3. FastAPI 主服务（端口 8000）

> Windows 用户：运行 `start.bat`

---

## 📁 项目结构

```
├── main.py              # FastAPI 主应用（含 /api/music/* 端点）
├── cbt_agent.py         # AI 代理（System Prompt、音乐检测、记忆同步）
├── database.py          # MySQL 数据层
├── auth.py              # JWT 认证 + bcrypt
├── preferences.py       # 用户偏好管理
├── verification.py      # 邮箱验证码（SMTP）
├── wechat_login.py      # 微信扫码登录（ilink API）
├── wechat_bot.py        # 微信消息轮询
│
├── templates/           # Jinja2 HTML 模板
│   ├── index.html       # 主 SPA（含 APlayer CDN）
│   └── login.html       # 登录注册
│
├── static/              # 前端资源
│   ├── css/style.css    # 含 APlayer 暖色主题样式
│   └── js/              # auth.js, chat.js, dashboard.js, diary.js, phq9.js
│
├── agent_data/          # AI 知识库
│   ├── AGENTS.md        # 小暖角色定义（含音乐分享说明）
│   └── knowledge/       # CBT、焦虑、睡眠、正念
│
├── gateway/             # OpenClaw Gateway 配置
│   ├── openclaw.json    # 主配置
│   ├── agents/          # Agent 定义
│   └── workspace/       # 工作区（技能、记忆）
│
├── netease-api/         # NeteaseCloudMusicAPI Enhanced v4.32
│   ├── app.js           # 入口，port 3000
│   └── ...              # 391 个网易云 API 端点
│
├── schema.sql           # 数据库 DDL
├── requirements.txt     # Python 依赖
├── railway.toml         # Railway 部署配置
├── start.sh             # Linux 启动脚本（含音乐 API + Gateway）
├── start.bat            # Windows 启动脚本
└── PROJECT_SUMMARY.md   # 详细项目总结
```

---

## 🚢 部署到 Railway

项目已配置好 `railway.toml`，支持一键部署：

1. Fork 本项目到 GitHub
2. 在 [Railway](https://railway.app) 中 New Project → Deploy from GitHub repo
3. 添加 MySQL 数据库服务
4. 设置环境变量 `DEEPSEEK_API_KEY`
5. 在 MySQL 中执行 `schema.sql`

`start.sh` 自动处理：Node.js 安装 → 音乐 API 启动 (:3000) → OpenClaw Gateway (:18789) → uvicorn。

> 音乐播放依赖 [NeteaseCloudMusicAPI Enhanced](https://github.com/enhancemade/NetEasy-Cloud-Music-API-Enhanced)，
> 部署时会自动 `npm install` 并启动在 3000 端口。若不可用，
> 会自动回退到公共 Meting API (`api.injahow.cn`)。

---

## 📡 API 文档

启动后访问 http://localhost:8000/docs 查看 Swagger UI。

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录（返回 JWT） |
| POST | `/api/auth/send-code` | 发送邮箱验证码 |
| GET | `/api/auth/me` | 当前用户信息 |

### 聊天

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/send` | 发送消息（SSE 流式响应） |
| GET | `/api/chat/history` | 获取对话历史 |
| POST | `/api/chat/clear` | 清空对话 |

### 情绪 & 测评

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/mood/scores` | 情绪分数历史 |
| GET | `/api/mood/report` | 周度报告 |
| POST | `/api/phq9/start` | 开始 PHQ-9 |
| POST | `/api/phq9/answer` | 提交答案 |
| GET | `/api/phq9/history` | 测评历史 |

### 日记 & 音乐 & 微信

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/diary/list` | 日记列表 |
| GET | `/api/diary/{date}` | 某天日记 |
| POST | `/api/diary/generate` | AI 生成日记 |
| GET | `/api/music/search?q=` | 搜索网易云歌曲 |
| GET | `/api/music/player?songId=` | APlayer 数据（歌名+封面+播放URL） |
| GET | `/api/music/stream?songId=` | MP3 直链 302 重定向 |
| GET | `/api/music/health` | 音乐 API 健康检查 |
| POST | `/api/wechat/start-login` | 微信扫码 |
| GET | `/api/wechat/login-status/{id}` | 扫码状态 |

---

## 📦 数据库表

| 表 | 用途 |
|---|---|
| `users` | 用户账户 |
| `messages` | 聊天记录 |
| `daily_scores` | 每日情绪分数 |
| `phq9_records` | PHQ-9 测评记录 |
| `diary_entries` | 情绪日记 |
| `wechat_bots` | 微信 bot 绑定 |
| `verify_codes` | 邮箱验证码 |
| `config` | 全局配置 |

---

## 🏆 比赛信息

- **赛事**：2026 年（第 19 届）中国大学生计算机设计大赛
- **赛道**：软件应用与开发 / 人工智能应用
- **作品名**：小暖 — 基于大语言模型的 CBT 心理陪伴伙伴

---

## 📄 许可

MIT License
