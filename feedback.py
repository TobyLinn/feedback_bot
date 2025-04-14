import sqlite3
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import json
from database import add_feedback, get_admin_group, is_admin_group, is_user_group, update_feedback_status, get_feedback_by_message_id, get_user_group
from movie_request import subscribe_movie
from datetime import datetime
from config import DB_FILE

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理反馈消息"""
    try:
        # 检查是否在用户群组中
        if not is_user_group(update.message.chat_id):
            await update.message.reply_text("❌ 此群组不是用户群组，无法发送反馈")
            return
        
        # 获取用户信息
        user = update.effective_user
        if not user:
            await update.message.reply_text("❌ 无法获取用户信息")
            return
        
        # 获取消息内容
        content = update.message.text
        if not content:
            await update.message.reply_text("❌ 反馈内容不能为空")
            return
        
        # 获取管理群组
        admin_group = get_admin_group()
        if not admin_group:
            await update.message.reply_text("❌ 未设置管理群组，请联系管理员")
            return
        
        admin_group_id = admin_group[0]
        
        # 处理求片请求
        if content.startswith('#求片'):
            # 提取TMDB链接
            tmdb_pattern = r'https?://(?:www\.)?themoviedb\.org/(?:movie|tv)/(\d+)'
            match = re.search(tmdb_pattern, content)
            
            if not match:
                await update.message.reply_text("❌ 请提供有效的TMDB链接（例如：https://www.themoviedb.org/movie/12345）")
                return
            
            tmdb_id = match.group(1)
            media_type = 'movie' if '/movie/' in content else 'tv'
            
            # 构建求片消息
            request_message = (
                f"🎬 收到求片请求\n\n"
                f"👤 用户信息：\n"
                f"- ID: {user.id}\n"
                f"- 用户名: {user.username}\n\n"
                f"📝 请求内容：\n{content}\n\n"
                f"🔗 TMDB ID: {tmdb_id}\n"
                f"📺 类型: {'电影' if media_type == 'movie' else '剧集'}"
            )
            
            # 创建处理按钮
            keyboard = [
                [
                    InlineKeyboardButton("✅ 同意", callback_data=f"approve_{tmdb_id}_{media_type}_{user.id}"),
                    InlineKeyboardButton("❌ 拒绝", callback_data=f"reject_{tmdb_id}_{media_type}_{user.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # 发送到管理群组
            admin_message = await context.bot.send_message(
                chat_id=admin_group_id,
                text=request_message,
                reply_markup=reply_markup
            )
            
            # 置顶消息
            try:
                await context.bot.pin_chat_message(
                    chat_id=admin_group_id,
                    message_id=admin_message.message_id
                )
            except Exception as e:
                logger.error(f"置顶消息失败: {e}")
            
            # 保存到数据库
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('''INSERT INTO subscriptions 
                        (user_id, tmdb_id, media_type, original_message, created_at, status)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (user.id, tmdb_id, media_type, content, datetime.now(), 'pending'))
            conn.commit()
            conn.close()
            
            # 回复用户
            await update.message.reply_text("✅ 您的求片请求已提交，请等待管理员处理")
            return
        
        # 处理普通反馈
        # 保存到数据库
        add_feedback(
            user_id=user.id,
            username=user.username or user.first_name,
            content=content,
            message_id=update.message.message_id,
            group_id=update.message.chat_id
        )
        
        # 发送到管理群组
        admin_message = await context.bot.send_message(
            chat_id=admin_group_id,
            text=f"📢 新反馈\n\n"
                 f"用户: {user.username or user.first_name} (ID: {user.id})\n"
                 f"群组: {update.message.chat.title} (ID: {update.message.chat_id})\n"
                 f"内容: {content}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ 已解决", callback_data=f"resolve_{update.message.message_id}"),
                    InlineKeyboardButton("❌ 已拒绝", callback_data=f"reject_{update.message.message_id}")
                ]
            ])
        )
        
        # 置顶消息
        try:
            await context.bot.pin_chat_message(
                chat_id=admin_group_id,
                message_id=admin_message.message_id
            )
        except Exception as e:
            logger.error(f"置顶消息失败: {e}")
        
        # 回复用户
        await update.message.reply_text("✅ 反馈已发送，请等待管理员处理")
    except Exception as e:
        logger.error(f"处理反馈时出错: {e}")
        await update.message.reply_text("❌ 处理反馈时出错，请稍后重试")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理回调查询"""
    query = update.callback_query
    await query.answer()
    
    # 检查是否在管理群组中
    if not is_admin_group(query.message.chat_id):
        await query.message.reply_text("❌ 此群组不是管理群组，无法处理反馈")
        return
    
    data = query.data
    if data.startswith("approve_") or data.startswith("reject_"):
        # 处理求片请求
        action, tmdb_id, media_type, user_id = data.split("_")
        status = "approved" if action == "approve" else "rejected"
        
        # 更新数据库状态
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''UPDATE subscriptions 
                    SET status = ? 
                    WHERE user_id = ? AND tmdb_id = ? AND status = 'pending' ''',
                 (status, user_id, tmdb_id))
        conn.commit()
        conn.close()
        
        # 在用户群组中发送通知
        try:
            # 获取用户群组ID
            user_group = get_user_group()
            if user_group:
                user_group_id = user_group[0]
                status_text = "✅ 已同意" if action == "approve" else "❌ 已拒绝"
                await context.bot.send_message(
                    chat_id=user_group_id,
                    text=f"📢 求片处理通知\n\n"
                         f"用户ID: {user_id}\n"
                         f"TMDB ID: {tmdb_id}\n"
                         f"类型: {'电影' if media_type == 'movie' else '剧集'}\n"
                         f"状态: {status_text}\n\n"
                         f"处理人: {query.from_user.username} (ID: {query.from_user.id})"
                )
        except Exception as e:
            logger.error(f"发送群组通知失败: {e}")
        
        # 更新管理群消息
        status_text = "✅ 已同意" if action == "approve" else "❌ 已拒绝"
        admin_info = f"\n\n👮 处理人：{query.from_user.username} (ID: {query.from_user.id})"
        await query.message.edit_text(
            text=query.message.text + f"\n\n{status_text}{admin_info}",
            reply_markup=None
        )
        
        # 取消置顶
        try:
            await context.bot.unpin_chat_message(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
        except Exception as e:
            logger.error(f"取消置顶失败: {e}")
        
    elif data.startswith("resolve_") or data.startswith("reject_"):
        # 处理普通反馈
        action, message_id = data.split("_")
        status = "resolved" if action == "resolve" else "rejected"
        status_text = "✅ 已解决" if action == "resolve" else "❌ 已拒绝"
        
        # 获取反馈信息
        feedback = get_feedback_by_message_id(int(message_id))
        if not feedback:
            await query.message.reply_text("❌ 找不到对应的反馈信息")
            return
        
        user_id, content, group_id = feedback
        
        # 更新反馈状态
        update_feedback_status(int(message_id), status)
        
        # 更新消息
        admin_info = f"\n\n👮 处理人：{query.from_user.username} (ID: {query.from_user.id})"
        await query.message.edit_text(
            text=query.message.text + f"\n\n{status_text}{admin_info}",
            reply_markup=None
        )
        
        # 取消置顶
        try:
            await context.bot.unpin_chat_message(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
        except Exception as e:
            logger.error(f"取消置顶失败: {e}")
        
        # 在用户群组中发送通知
        try:
            # 获取用户群组ID
            user_group = get_user_group()
            if user_group:
                user_group_id = user_group[0]
                await context.bot.send_message(
                    chat_id=user_group_id,
                    text=f"📢 反馈处理通知\n\n"
                         f"用户ID: {user_id}\n"
                         f"内容: {content}\n"
                         f"状态: {status_text}\n\n"
                         f"处理人: {query.from_user.username} (ID: {query.from_user.id})"
                )
        except Exception as e:
            logger.error(f"发送群组通知失败: {e}")

def get_pending_feedback():
    """获取所有未解决的反馈"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT * FROM feedback WHERE status = "pending" ORDER BY created_at DESC')
    feedbacks = c.fetchall()
    conn.close()
    return feedbacks

async def daily_cleanup(context: ContextTypes.DEFAULT_TYPE):
    """每日清理任务"""
    pending_feedbacks = get_pending_feedback()
    if not pending_feedbacks:
        return

    summary = "📊 未解决反馈汇总\n\n"
    for feedback in pending_feedbacks:
        # 获取反馈信息
        user_id = feedback[1]  # user_id
        username = feedback[2]  # username
        content = feedback[3]  # content
        created_at = feedback[8]  # created_at
        
        summary += f"用户: {username} (ID: {user_id})\n内容: {content}\n时间: {created_at}\n\n"

    # 获取用户群组ID
    user_group = get_user_group()
    if user_group:
        user_group_id = user_group[0]
        try:
            await context.bot.send_message(
                chat_id=user_group_id,
                text=summary
            )
        except Exception as e:
            logger.error(f"发送每日汇总失败: {e}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理统计命令"""
    # 检查是否是管理员
    if update.effective_user.id not in config['admin_ids']:
        await update.message.reply_text("❌ 抱歉，您没有权限使用此命令。")
        return

    # 获取统计数据
    conn = sqlite3.connect(config['db_file'])
    c = conn.cursor()
    
    # 获取总反馈数
    c.execute('SELECT COUNT(*) FROM feedback')
    total = c.fetchone()[0]
    
    # 获取已解决反馈数
    c.execute('SELECT COUNT(*) FROM feedback WHERE status = "resolved"')
    resolved = c.fetchone()[0]
    
    # 获取待处理反馈数
    c.execute('SELECT COUNT(*) FROM feedback WHERE status = "pending"')
    pending = c.fetchone()[0]
    
    # 获取求片数量
    c.execute('SELECT COUNT(*) FROM feedback WHERE feedback_type = "request"')
    requests = c.fetchone()[0]
    
    conn.close()

    # 创建统计消息
    stats_message = (
        f"📊 反馈统计\n\n"
        f"总反馈数: {total}\n"
        f"已解决: {resolved}\n"
        f"待处理: {pending}\n"
        f"求片数量: {requests}"
    )

    await update.message.reply_text(stats_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理帮助命令"""
    help_text = (
        "🤖 反馈机器人使用说明\n\n"
        "📝 发送反馈：\n"
        "- 使用 #反馈 开头发送一般反馈\n"
        "- 使用 #求片 开头请求影视资源\n\n"
        "🎯 反馈类型：\n"
        "- 问题反馈 🐛\n"
        "- 功能建议 💡\n"
        "- 疑问咨询 ❓\n"
        "- 一般建议 📝\n"
        "- 一般反馈 📢\n"
        "- 求片请求 🎬\n\n"
        "📊 管理员命令：\n"
        "/stats - 查看反馈统计\n"
        "/help - 显示此帮助信息"
    )
    await update.message.reply_text(help_text)

def setup_handlers(application: Application):
    """设置反馈处理器"""
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("help", help_command))
    logger.info("反馈处理器添加完成") 