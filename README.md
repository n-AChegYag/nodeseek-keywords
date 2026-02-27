# NodeSeek Keywords Bot

一个私人 Telegram Bot，实时监控 [NodeSeek](https://www.nodeseek.com/) RSS 订阅，发现包含指定关键词的新帖后立即推送通知。

## 功能特性

- **关键词监控** — 支持子串匹配和正则表达式两种模式，大小写不敏感
- **版块过滤** — 可针对特定版块（交易、技术、情报……）独立配置，也可全版块监控
- **关键词开关** — 支持暂停/恢复单个关键词，无需删除重建
- **推送历史** — 记录所有命中的帖子，可随时通过 `/history` 回溯
- **防洪推送** — 每轮最多推送 N 条单独消息，超出部分自动汇总为一条，避免消息轰炸
- **通知可靠** — 发送失败自动重试（最多 3 次指数退避），失败记录可在历史中查看
- **RSS 健康告警** — 连续拉取失败达阈值后自动发送告警通知
- **去重推送** — 每篇帖子只通知一次，重启后状态不丢失
- **首次静默** — Bot 启动时先标记历史帖，避免积压推送
- **Docker 部署** — 一条命令启动，数据通过 volume 持久化
- **单用户鉴权** — 仅响应 `ALLOWED_USER_ID` 指定的用户

## 支持的版块

| Slug | 版块 |
|---|---|
| `daily` | 日常 |
| `tech` | 技术 |
| `info` | 情报 |
| `review` | 测评 |
| `trade` | 交易 |
| `carpool` | 拼车 |
| `dev` | Dev |
| `photo-share` | 贴图 |
| `expose` | 曝光 |
| `sandbox` | 沙盒 |

## 快速开始

### 前置准备

1. 向 [@BotFather](https://t.me/BotFather) 申请一个 Bot，获取 `TELEGRAM_BOT_TOKEN`
2. 向 [@userinfobot](https://t.me/userinfobot) 获取你的 `ALLOWED_USER_ID`

### 方式一：Docker（推荐）

```bash
# 克隆仓库
git clone https://github.com/n-AChegYag/nodeseek-keywords.git
cd nodeseek-keywords

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 TELEGRAM_BOT_TOKEN 和 ALLOWED_USER_ID

# 启动
docker compose up -d
```

数据库文件保存在 `./data/keywords.db`，容器重建后数据不丢失。

### 方式二：直接运行

**要求：Python 3.11+**

```bash
git clone https://github.com/n-AChegYag/nodeseek-keywords.git
cd nodeseek-keywords

pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入必要配置

python main.py
```

## 配置

在 `.env` 文件中设置以下变量：

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | — | BotFather 提供的 Bot Token |
| `ALLOWED_USER_ID` | ✅ | — | 允许使用 Bot 的 Telegram 用户 ID |
| `POLL_INTERVAL` | ❌ | `60` | RSS 轮询间隔（秒） |
| `MAX_NOTIFICATIONS_PER_POLL` | ❌ | `10` | 每轮最多单独推送的消息数，超出部分自动汇总 |
| `RSS_FAIL_ALERT_THRESHOLD` | ❌ | `3` | RSS 连续拉取失败多少次后发送告警 |
| `DATABASE_PATH` | ❌ | `data/keywords.db` | SQLite 数据库文件路径 |

## Bot 命令

| 命令 | 说明 |
|---|---|
| `/start` `/help` | 查看帮助与命令列表 |
| `/add <关键词> [--regex] [版块]` | 添加监控关键词 |
| `/remove <关键词>` | 删除关键词（含所有版块配置） |
| `/pause <关键词>` | 暂停关键词监控（不删除） |
| `/resume <关键词>` | 恢复已暂停的关键词 |
| `/list` | 查看所有监控关键词及其状态 |
| `/history [数量]` | 查看最近推送记录（默认 10 条，最多 20） |
| `/categories` | 查看所有可用版块及其 Slug |
| `/status` | 查看 Bot 运行状态 |

## 匹配模式

### 普通模式（默认）

大小写不敏感的子串匹配：

```
/add DMIT              # 全版块监控含 "DMIT" 的帖子
/add 搬瓦工 trade      # 只在交易版监控含 "搬瓦工" 的帖子
/add Hetzner info      # 只在情报版监控含 "Hetzner" 的帖子
```

### 正则模式（`--regex`）

使用 Python `re` 语法，默认忽略大小写：

```
/add DMIT.*(CN2|GIA) --regex
    → 含 CN2 或 GIA 的 DMIT 帖（全版块）

/add 套餐.*\d+[Gg] --regex trade
    → 交易版中带容量数字的套餐帖，如"套餐 1Gbps"

/add (补货|回归|上新) --regex info
    → 情报版的补货、回归或上新帖

/add ^\[.*(促销|限时).* --regex
    → 标题开头带 [促销] 或 [限时] 标签的帖子
```

> 添加时会立即校验正则语法，无效表达式会报错提示。

## `/list` 状态标记

```
1. DMIT           — 全部版块          ← 普通模式，监控中
2. 套餐.*\d+[Gg] 🔍 — 交易           ← 🔍 正则模式，监控中
3. 搬瓦工 ⏸       — 交易             ← ⏸ 已暂停
```

## 通知示例

**单条通知：**
```
🔔 关键词提醒  DMIT

📌 DMIT 新款 CN2 GIA 套餐上线
🏷 交易
👤 someuser
🔗 https://www.nodeseek.com/post-12345-1
```

**防洪汇总（超出单条上限时）：**
```
⚠️ 本轮匹配 15 条，已单独推送 10 条。以下 5 条已自动汇总：

• DMIT — DMIT 年付特惠活动开启
• 搬瓦工 — 搬瓦工 2024 黑五套餐
• ...
```

## 项目结构

```
.
├── main.py          # 入口：串联各模块，启动 Bot 和定时任务
├── bot.py           # Telegram 命令处理器 & RSS 轮询 Job
├── monitor.py       # RSS 抓取 & 关键词匹配逻辑
├── storage.py       # SQLite 数据访问层
├── config.py        # 环境变量读取
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## License

MIT
