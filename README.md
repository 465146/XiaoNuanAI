# 🫧 小暖 XiaoNuan — AI CBT 心理陪伴伙伴

**2026 年中国大学生计算机设计大赛参赛作品**

小暖是一个基于大语言模型的 CBT（认知行为疗法）心理陪伴 Web 应用。面向大学生心理健康场景，提供 AI 对话疏导、情绪追踪、PHQ-9 抑郁筛查、情绪日记、微信消息接入等功能。

## 技术栈

| 层面 | 技术 |
|------|------|
| 后端框架 | Python FastAPI |
| 数据库 | MySQL 8.0 |
| AI 模型 | DeepSeek API（支持用户自定义 Key） |
| 前端 | 原生 HTML/CSS/JS + ECharts + marked.js |
| 微信接入 | WeChat ilink API（每用户独立 bot） |
| Agent 网关 | OpenClaw Gateway（skills 扩展） |
| 包管理 | uv (pyproject.toml) |

## 功能模块

### 💬 AI 对话
- SSE 流式输出，Markdown 渲染
- 智能路由：日常聊天直连 DeepSeek（快），技能请求走 OpenClaw Gateway
- 每轮对话自动评估情绪分数
- 历史记录持久化，刷新不丢失

### 📊 情绪仪表盘
- 30 天情绪趋势折线图
- PHQ-9 测试历史柱状图
- 周度文字报告（平均值 / 趋势 / 风险评估）
- 今日情绪、本周平均、最新 PHQ-9 三指标卡片

### 📋 PHQ-9 抑郁筛查
- 9 道国际标准题目，随机乱序
- 严重程度自动分级（无/轻度/中度/中重度/重度）
- 结果反馈到情绪追踪系统
- Q9（自伤念头）>0 自动提供 24h 危机热线

### 📝 情绪日记
- 一键 AI 生成当日日记（基于对话内容）
- Markdown / 纯文本下载
- 按日期归档，独立存储

### 📱 微信连接
- **每用户独立微信 bot**：扫码后创建专属 ilink bot
- Python 后台长轮询收消息 → AI 处理 → 自动回复
- 多用户完全隔离，互不干扰

### ⚙️ 用户系统
- JWT 认证 + bcrypt 密码哈希
- 邮箱验证码注册
- 自定义 AI 模型 Key / 地址 / 模型名
- 个人档案（目标、触发点、应对方式）

## 快速启动

### 环境要求
- Python 3.13+
- MySQL 8.0
- Node.js（OpenClaw Gateway）
- Windows 10/11

### 数据库初始化

```sql
CREATE DATABASE cbt_xiaonuan DEFAULT CHARACTER SET utf8mb4;

-- 执行 database.py 中的表结构会自动创建
-- 首次启动时 wechat_bots 表需要手动创建（见下方）
```

### 一键启动

```bat
E:\OpenclawProject\start.bat
```

脚本自动完成：
1. 清理端口 8000 / 18789 残留进程
2. 启动 OpenClaw Gateway（后台，端口 18789）
3. 启动 FastAPI 应用（前台，端口 8000）

访问：http://localhost:8000

### 手动启动

```bash
# 终端 1：启动 Gateway
set DEEPSEEK_API_KEY=sk-your-key-here
node %APPDATA%\npm\node_modules\openclaw\dist\index.js gateway --port 18789

# 终端 2：启动 FastAPI
cd E:\OpenclawProject
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

## 项目结构

```
E:\OpenclawProject\
├── main.py              # FastAPI 主应用
├── auth.py              # JWT + bcrypt 认证
├── database.py          # MySQL CRUD
├── cbt_agent.py         # AI Agent + 智能路由
├── wechat_login.py      # 微信二维码登录（ilink API）
├── wechat_bot.py        # 每用户独立微信 bot 轮询
├── preferences.py       # 用户偏好管理
├── verification.py      # 邮箱验证码
├── pyproject.toml       # Python 依赖
├── start.bat            # 一键启动脚本
├── start.sh             # Linux 启动脚本
├── railway.toml         # Railway 部署配置
├── templates/
│   ├── index.html       # 主 SPA（6 个页面）
│   └── login.html       # 登录注册页
├── static/
│   ├── css/style.css    # 暖橙色全局样式
│   └── js/              # auth.js, chat.js, dashboard.js, diary.js, phq9.js
├── agent_data/
│   ├── AGENTS.md        # CBT Agent 系统提示词
│   └── knowledge/       # 专业知识库（CBT/焦虑/睡眠/正念）
└── user_data/           # 用户偏好文件（已 gitignore）
```

## 关于 C:\Users\daier\.openclaw\

**⚠️ 整个 `.openclaw` 目录不应提交到 GitHub。**

原因：
| 文件/目录 | 包含内容 | 风险 |
|-----------|----------|------|
| `.env` | DeepSeek API Key | 🔴 明文密钥 |
| `openclaw-weixin/accounts/*.json` | 微信 bot token | 🔴 可接管你的微信 bot |
| `openclaw.json` | Gateway 配置（含 token 引用） | 🟡 含架构信息 |
| `logs/` | 运行日志 | 🟡 可能含对话内容 |
| `memory/` | Agent 对话记忆 | 🟡 用户对话数据 |
| `completions/` | API 调用记录 | 🟡 含敏感内容 |

**如果确实需要分享配置**，可以单独提取以下安全内容：
- `workspace/cbt/AGENTS.md` — Agent 系统提示词
- `agents/cbt/agent/` — Agent 配置结构
- `skills/` — Skills 配置（排除 token 字段）
- `openclaw.json` — 改名为 `openclaw.example.json`，删除 token/env 引用

本项目已将上述文件的核心内容复制到 `agent_data/` 目录中，该目录可安全提交。

## API 路由概要

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| POST | `/api/auth/send-code` | 发送邮箱验证码 |
| GET | `/api/auth/me` | 当前用户信息 |
| POST | `/api/chat/send` | SSE 流式聊天 |
| GET | `/api/chat/history` | 对话历史 |
| POST | `/api/chat/clear` | 清空对话 |
| GET | `/api/mood/scores` | 情绪分数历史 |
| GET | `/api/mood/report` | 周度情绪报告 |
| POST | `/api/phq9/start` | 开始 PHQ-9 测试 |
| POST | `/api/phq9/answer` | 提交测试答案 |
| GET | `/api/phq9/history` | 测试历史 |
| GET/POST | `/api/diary/*` | 日记 CRUD + AI 生成 |
| POST | `/api/wechat/start-login` | 开始微信扫码 |
| GET | `/api/wechat/login-status/{sid}` | 扫码状态查询 |
| GET | `/api/wechat/login-qrcode/{sid}` | 二维码图片 |
| GET | `/api/wechat/info` | 用户微信连接状态 |
| GET/PUT | `/api/user/preferences` | 用户偏好 |
| GET | `/api/health` | 健康检查 |

API 文档：启动后访问 http://localhost:8000/docs

## 比赛信息

- **赛事**：2026 年中国大学生计算机设计大赛
- **赛道**：软件应用与开发 / 人工智能应用
- **作品名称**：小暖 — AI CBT 心理陪伴伙伴
