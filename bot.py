"""
Telegram bot: command handlers and the recurring RSS-poll job.
"""
from __future__ import annotations

import html
import logging
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
import monitor
import storage

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escape text for safe inclusion in HTML parse-mode messages."""
    return html.escape(str(text))


def _authorized(update: Update) -> bool:
    return update.effective_user.id == config.ALLOWED_USER_ID


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    await update.message.reply_text(
        "👋 <b>NodeSeek 关键词监控 Bot</b>\n\n"
        "<b>命令列表：</b>\n"
        "/add <code>&lt;关键词&gt;</code> <i>[分类]</i>  — 添加监控关键词\n"
        "/remove <code>&lt;关键词&gt;</code>  — 删除关键词（含所有分类）\n"
        "/list  — 查看所有监控关键词\n"
        "/categories  — 查看可用版块分类\n"
        "/status  — 查看 Bot 运行状态\n\n"
        "💡 <i>不填分类则监控全部版块；可多次 /add 同一关键词搭配不同分类。</i>",
        parse_mode=ParseMode.HTML,
    )


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return

    if not context.args:
        await update.message.reply_text(
            "用法：/add <code>&lt;关键词&gt;</code> <i>[分类]</i>\n\n"
            "示例：\n"
            "  /add DMIT\n"
            "  /add 搬瓦工 trade\n"
            "  /add Hetzner info",
            parse_mode=ParseMode.HTML,
        )
        return

    # Smart parsing: if the last token is a known category slug, treat it as one
    parts = list(context.args)
    category: Optional[str] = None
    if parts[-1].lower() in monitor.CATEGORIES:
        category = parts.pop().lower()
    keyword = " ".join(parts)

    if not keyword:
        await update.message.reply_text("❌ 关键词不能为空。")
        return

    ok = storage.add_keyword(keyword, category)
    if ok:
        cat_str = (
            f"，仅限 <b>{_esc(monitor.CATEGORIES[category])}</b> 版块"
            if category
            else "，监控全部版块"
        )
        await update.message.reply_text(
            f"✅ 已添加关键词 <code>{_esc(keyword)}</code>{cat_str}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"⚠️ 关键词 <code>{_esc(keyword)}</code>"
            + (f" ({_esc(category)})" if category else "")
            + " 已存在，无需重复添加。",
            parse_mode=ParseMode.HTML,
        )


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return

    if not context.args:
        await update.message.reply_text(
            "用法：/remove <code>&lt;关键词&gt;</code>\n"
            "将删除该关键词下所有分类的记录。",
            parse_mode=ParseMode.HTML,
        )
        return

    keyword = " ".join(context.args)
    count = storage.remove_keyword(keyword)
    if count:
        await update.message.reply_text(
            f"✅ 已删除关键词 <code>{_esc(keyword)}</code>（共 {count} 条记录）",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"❌ 未找到关键词 <code>{_esc(keyword)}</code>，请用 /list 确认拼写。",
            parse_mode=ParseMode.HTML,
        )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return

    keywords = storage.list_keywords()
    if not keywords:
        await update.message.reply_text(
            "📋 暂无监控关键词。\n使用 /add 添加第一个。"
        )
        return

    lines = [f"📋 <b>监控关键词（共 {len(keywords)} 条）：</b>\n"]
    for i, kw in enumerate(keywords, 1):
        if kw["category"]:
            cat_label = monitor.CATEGORIES.get(kw["category"], kw["category"])
            scope = f"<i>{_esc(cat_label)}</i>"
        else:
            scope = "<i>全部版块</i>"
        lines.append(f"{i}. <code>{_esc(kw['keyword'])}</code> — {scope}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return

    lines = ["🏷 <b>可用版块分类：</b>\n"]
    for slug, name in monitor.CATEGORIES.items():
        lines.append(f"• <code>{slug}</code> — {name}")
    lines.append("\n示例：/add DMIT trade")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return

    keywords = storage.list_keywords()
    initialized = storage.get_setting("initialized") == "true"
    await update.message.reply_text(
        f"✅ <b>Bot 运行正常</b>\n\n"
        f"📊 监控关键词：{len(keywords)} 个\n"
        f"⏱ 轮询间隔：{config.POLL_INTERVAL} 秒\n"
        f"🌐 RSS 地址：<code>{config.RSS_BASE_URL}</code>\n"
        f"🔄 已初始化：{'是' if initialized else '否（首次轮询后完成）'}",
        parse_mode=ParseMode.HTML,
    )


# ── Notification formatter ────────────────────────────────────────────────────

def _build_notification(post: dict, matched_keywords: list[str]) -> str:
    kw_tags = " ".join(f"<code>{_esc(k)}</code>" for k in matched_keywords)
    cat_name = monitor.CATEGORIES.get(post["category"], post["category"])
    return (
        f"🔔 <b>关键词提醒</b>  {kw_tags}\n\n"
        f"📌 <b>{_esc(post['title'])}</b>\n"
        f"🏷 {_esc(cat_name)}\n"
        f"👤 {_esc(post['author'])}\n"
        f"🔗 {post['link']}"
    )


# ── RSS polling job (runs on bot's event loop via JobQueue) ───────────────────

async def poll_rss(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Called every POLL_INTERVAL seconds by PTB's JobQueue.

    Strategy:
    - On first run: seed all current feed posts as "seen" without notifying
      (prevents flooding the user with backlog on startup).
    - Subsequent runs: for each unseen post, check keyword matches and notify.
    """
    keywords = storage.list_keywords()
    if not keywords:
        return  # Nothing to do

    # Determine which category feeds to request
    need_global = any(kw["category"] is None for kw in keywords)
    specific_cats: set[str] = {
        kw["category"] for kw in keywords if kw["category"] is not None
    }

    # Collect all entries, deduplicated by post_id
    entries: dict[int, dict] = {}
    try:
        if need_global:
            for e in await monitor.fetch_entries():
                entries[e["post_id"]] = e
        else:
            for cat in specific_cats:
                for e in await monitor.fetch_entries(cat):
                    entries[e["post_id"]] = e
    except Exception as exc:
        logger.exception("Unhandled error during RSS fetch: %s", exc)
        return

    if not entries:
        return

    # ── First-run: seed without notifying ────────────────────────────────────
    if storage.get_setting("initialized") != "true":
        logger.info("First poll — seeding %d posts as seen (no notifications)", len(entries))
        storage.mark_many_seen(list(entries.keys()))
        storage.set_setting("initialized", "true")
        return

    # ── Normal run: check new posts ───────────────────────────────────────────
    new_posts = 0
    notified = 0

    # Process in ascending post_id order (oldest new first)
    for post_id, post in sorted(entries.items()):
        if storage.is_seen(post_id):
            continue

        storage.mark_seen(post_id)
        new_posts += 1

        matched = [
            kw["keyword"]
            for kw in keywords
            if (kw["category"] is None or kw["category"] == post["category"])
            and monitor.matches(post["title"], kw["keyword"])
        ]
        if not matched:
            continue

        msg = _build_notification(post, matched)
        try:
            await context.bot.send_message(
                chat_id=config.ALLOWED_USER_ID,
                text=msg,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            notified += 1
        except Exception as exc:
            logger.error("Failed to send notification for post %d: %s", post_id, exc)

    if new_posts:
        logger.info("Poll complete — %d new post(s), %d notification(s) sent", new_posts, notified)

    # Prune old seen_posts rows weekly (cheap op, runs every cycle)
    storage.cleanup_old_seen(keep_days=7)
