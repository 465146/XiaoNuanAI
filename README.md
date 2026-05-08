# 🫧 小暖 XiaoNuan — AI CBT 心理陪伴伙伴

**2026 年中国大学生计算机设计大赛参赛作品**

小暖是一个基于大语言模型的 CBT（认知行为疗法）心理陪伴 Web 应用，面向大学生心理健康场景，提供 AI 对话疏导、情绪追踪、PHQ-9 抑郁筛查、情绪日记、微信消息接入等功能。

---

## ✨ 功能

| 模块 | 说明 |
|------|------|
| 💬 AI 对话 | SSE 流式输出，Markdown 渲染，日常聊天直连 DeepSeek（快），技能请求走 OpenClaw Gateway |
| 📊 情绪仪表盘 | 30 天趋势图（ECharts），周度文字报告，情绪指标卡片 |
| 📋 PHQ-9 测评 | 9 题随机乱序，自动分级，Q9 危机预警 + 24h 热线提示 |
| 📝 情绪日记 | 一键 AI 生成，基于当天对话内容 |
| 📱 微信连接 | 每用户独立 bot，扫码绑定，双向消息同步 |
| 🔐 用户系统 | JWT 认证、邮箱验证码注册、自定义 AI 模型配置 |

---

## 🏗 架构

```
Browser (SPA) ──▶ FastAPI (uvicorn :8000)
                      │
              ┌───────┼───────┐
              ▼       ▼       ▼
          DeepSeek  MySQL  OpenClaw Gateway (:18789)
          (日常聊天) (数据)   (技能+记忆)
```

- **日常聊天** → DeepSeek API 直连（流式 SSE，低延迟）
- **技能请求**（音乐点歌等）→ 路由到 OpenClaw Gateway
- **记忆系统** → 后台定时摘要 → 写入 Gateway 工作区 → mengram 插件索引

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- MySQL 8.0
- Node.js 22+（仅 Gateway 需要）

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

**完整启动（Web + Gateway）：**

```bash
bash start.sh
```

> Windows 用户：运行 `start.bat`（会自动启动 Gateway + Web）

---

## 📁 项目结构

```
├── main.py              # FastAPI 主应用
├── cbt_agent.py         # AI 代理（System Prompt、路由、记忆同步）
├── database.py          # MySQL 数据层
├── auth.py              # JWT 认证 + bcrypt
├── preferences.py       # 用户偏好管理
├── verification.py      # 邮箱验证码（SMTP）
├── wechat_login.py      # 微信扫码登录（ilink API）
├── wechat_bot.py        # 微信消息轮询
│
├── templates/           # Jinja2 HTML 模板
│   ├── index.html       # 主 SPA
│   └── login.html       # 登录注册
│
├── static/              # 前端资源
│   └── js/              # auth.js, chat.js, dashboard.js, diary.js, phq9.js
│
├── agent_data/          # AI 知识库（可安全提交）
│   ├── AGENTS.md        # 小暖角色定义
│   └── knowledge/       # CBT、焦虑、睡眠、正念
│
├── gateway/             # OpenClaw Gateway 配置
│   ├── openclaw.json    # 主配置
│   ├── agents/          # Agent 定义
│   └── workspace/       # 工作区（技能、记忆）
│
├── schema.sql           # 数据库 DDL
├── requirements.txt     # Python 依赖
├── railway.toml         # Railway 部署配置
├── start.sh             # Linux 启动脚本
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

`start.sh` 会自动处理：Node.js 安装 → OpenClaw Gateway 启动 → Python uvicorn 启动。

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

### 日记 & 微信

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/diary/list` | 日记列表 |
| GET | `/api/diary/{date}` | 某天日记 |
| POST | `/api/diary/generate` | AI 生成日记 |
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
