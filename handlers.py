import logging
import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from config import FEEDBACK_GROUPS, DISPLAY_GROUP, FEEDBACK_TAG
from database import add_feedback, update_feedback_status, get_pending_feedback, get_feedback_by_message_id, get_feedback_stats
from utils import format_feedback_message, format_status_update_message, format_daily_summary, format_stats_message, is_virtual_user

# 配置日志
logger = logging.getLogger(__name__)

# 延迟删除消息的时间（秒）
DELETE_DELAY = 600  # 10分钟

# 反馈分类
CATEGORIES = {
    "bug": "问题",
    "feature": "功能",
    "question": "疑问",
    "suggestion": "建议",
    "general": "一般"
}

# 反馈优先级
PRIORITIES = {
    "high": "高",
    "normal": "中",
    "low": "低"
}

async def delete_message_later(context, chat_id, message_id, delay):
    """延迟删除消息"""
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"消息 {message_id} 已删除")
    except Exception as e:
        logger.error(f"删除消息 {message_id} 失败: {e}")

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理反馈消息"""
    if update.message.chat_id not in FEEDBACK_GROUPS:
        return

    message_text = update.message.text
    if not message_text.startswith(FEEDBACK_TAG):
        return

    content = message_text[len(FEEDBACK_TAG):].strip()
    if not content:
        await update.message.reply_text("请提供反馈内容！")
        return

    # 获取用户信息
    user = update.message.from_user
    
    # 解析反馈分类和优先级
    category = "general"
    priority = "normal"
    
    # 检查分类标记
    for cat_key, cat_name in CATEGORIES.items():
        if f"#{cat_key}" in content.lower():
            category = cat_key
            content = content.replace(f"#{cat_key}", "").strip()
            break
    
    # 检查优先级标记
    if "!!!" in content:
        priority = "high"
        content = content.replace("!!!", "").strip()
    elif "!!" in content:
        priority = "high"
        content = content.replace("!!", "").strip()
    elif "!" in content:
        priority = "normal"
        content = content.replace("!", "").strip()
    
    # 发送反馈到展示群组
    keyboard = [
        [
            InlineKeyboardButton("已解决", callback_data=f"resolve"),
            InlineKeyboardButton("驳回", callback_data=f"reject")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 使用工具函数格式化消息
    formatted_message = format_feedback_message(user, content, category, priority)
    
    feedback_message = await context.bot.send_message(
        chat_id=DISPLAY_GROUP,
        text=formatted_message,
        reply_markup=reply_markup
    )

    # 置顶消息
    await context.bot.pin_chat_message(
        chat_id=DISPLAY_GROUP,
        message_id=feedback_message.message_id
    )

    # 保存到数据库
    add_feedback(
        user.id,
        user.username,
        content,
        feedback_message.message_id,
        category,
        priority
    )

    await update.message.reply_text("感谢您的反馈！")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理按钮回调"""
    query = update.callback_query
    await query.answer()

    action = query.data
    message_id = query.message.message_id
    chat_id = query.message.chat_id

    if action == "resolve":
        status = "resolved"
        status_text = "已解决"
    else:
        status = "rejected"
        status_text = "已驳回"

    # 更新数据库
    update_feedback_status(message_id, status)

    # 更新消息
    await query.edit_message_text(
        text=query.message.text + f"\n\n状态: {status_text}",
        reply_markup=None
    )

    # 取消置顶（无论是已解决还是驳回）
    try:
        await context.bot.unpin_chat_message(
            chat_id=DISPLAY_GROUP,
            message_id=message_id
        )
    except Exception as e:
        logger.error(f"取消置顶失败: {e}")
    
    # 设置延迟删除消息
    asyncio.create_task(delete_message_later(context, chat_id, message_id, DELETE_DELAY))
    
    # 在原始反馈群组中发送通知
    try:
        feedback = get_feedback_by_message_id(message_id)
        if feedback:
            user_id, content = feedback
            # 在所有反馈群组中发送通知
            for group_id in FEEDBACK_GROUPS:
                try:
                    # 使用工具函数格式化消息
                    formatted_message = format_status_update_message(content, status_text)
                    await context.bot.send_message(
                        chat_id=group_id,
                        text=formatted_message
                    )
                except Exception as e:
                    logger.error(f"在群组 {group_id} 发送通知失败: {e}")
    except Exception as e:
        logger.error(f"处理反馈通知失败: {e}")

async def daily_cleanup(context: ContextTypes.DEFAULT_TYPE):
    """每日清理任务"""
    pending_feedbacks = get_pending_feedback()
    if not pending_feedbacks:
        return

    # 使用工具函数格式化消息
    summary = format_daily_summary(pending_feedbacks)

    await context.bot.send_message(
        chat_id=DISPLAY_GROUP,
        text=summary
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理统计命令"""
    # 检查权限
    if update.effective_user.id not in context.bot_data.get("admin_ids", []):
        await update.message.reply_text("您没有权限执行此命令。")
        return
    
    # 获取统计信息
    stats = get_feedback_stats()
    
    # 格式化统计信息
    stats_message = format_stats_message(stats)
    
    await update.message.reply_text(stats_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理帮助命令"""
    help_text = (
        "📝 反馈机器人使用指南\n\n"
        f"1. 使用 {FEEDBACK_TAG} 提交反馈\n"
        "2. 可以使用以下标记分类反馈：\n"
    )
    
    for cat_key, cat_name in CATEGORIES.items():
        help_text += f"   - #{cat_key}: {cat_name}\n"
    
    help_text += (
        "\n3. 可以使用以下标记设置优先级：\n"
        "   - !: 普通优先级\n"
        "   - !!: 高优先级\n"
        "   - !!!: 紧急优先级\n\n"
        "示例：\n"
        f"{FEEDBACK_TAG} #bug !! 这是一个高优先级的bug反馈\n"
        f"{FEEDBACK_TAG} #suggestion 这是一个建议\n"
    )
    
    await update.message.reply_text(help_text) 