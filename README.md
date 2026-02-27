# NodeSeek Keywords Bot

一个私人 Telegram Bot，实时监控 [NodeSeek](https://www.nodeseek.com/) RSS 订阅，发现包含指定关键词的新帖后立即推送通知。

## 功能特性

- **关键词监控** — 支持添加任意数量关键词，大小写不敏感匹配
- **版块过滤** — 可针对特定版块（交易、技术、情报……）独立配置，也可全版块监控
- **去重推送** — 每篇帖子只通知一次，重启后状态不丢失
- **首次静默** — Bot 启动时先静默标记历史帖，避免积压推送
- **Docker 部署** — 一条命令启动，数据通过 volume 持久化
- **单用户鉴权** — 仅响应 `ALLOWED_USER_ID` 指定的用户，无需担心隐私

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
| `DATABASE_PATH` | ❌ | `data/keywords.db` | SQLite 数据库文件路径 |

## Bot 命令

| 命令 | 说明 |
|---|---|
| `/start` `/help` | 查看帮助与命令列表 |
| `/add <关键词> [版块]` | 添加监控关键词，可选指定版块 |
| `/remove <关键词>` | 删除关键词（含所有版块配置） |
| `/list` | 查看当前所有监控关键词 |
| `/categories` | 查看所有可用版块及其 Slug |
| `/status` | 查看 Bot 运行状态 |

### 使用示例

```
# 监控全版块中包含 "DMIT" 的帖子
/add DMIT

# 只监控交易版块中包含 "搬瓦工" 的帖子
/add 搬瓦工 trade

# 同一关键词可搭配不同版块多次添加
/add Hetzner info
/add Hetzner trade
```

## 通知示例

```
🔔 关键词提醒  DMIT

📌 DMIT 新款 CN2 GIA 套餐上线
🏷 交易
👤 someuser
🔗 https://www.nodeseek.com/post-12345-1
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
