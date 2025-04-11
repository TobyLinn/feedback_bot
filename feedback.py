import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import json

# 加载配置文件
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理反馈消息"""
    try:
        # 检查 update 和 message 是否存在
        if not update or not update.message:
            logger.error("收到无效的更新或消息")
            return

        message = update.message
        user = message.from_user
        
        # 检查消息内容
        if not message.text:
            logger.error("收到空消息")
            return
            
        content = message.text.strip()
        
        # 检查消息格式
        if not content.startswith('#反馈'):
            return
        
        # 记录用户信息
        user_info = f"用户ID: {user.id}\n用户名: {user.username}\n"
        logger.info(f"收到反馈\n{user_info}内容: {content}")
        
        # 移除标签获取实际内容
        actual_content = content[3:].strip()
        if not actual_content:
            await message.reply_text("❌ 请在标签后输入具体内容")
            return
        
        # 保存到数据库
        conn = sqlite3.connect(config['db_file'])
        c = conn.cursor()
        c.execute('''
            INSERT INTO feedback (user_id, username, content, feedback_type, status, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', (user.id, user.username, actual_content, 'feedback', 'pending'))
        feedback_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # 发送确认消息给用户
        confirm_message = (
            f"✅ 已收到您的反馈\n"
            f"📝 内容：{actual_content}\n"
            f"🔢 反馈ID：{feedback_id}\n"
            f"⏳ 状态：待处理\n\n"
            "感谢您的反馈！我们会尽快处理。"
        )
        await message.reply_text(confirm_message)
        
        # 发送到反馈管理群组
        group_message = (
            f"📝 新的反馈\n\n"
            f"👤 用户信息：\n{user_info}"
            f"📝 内容：{actual_content}\n"
            f"🔢 反馈ID：{feedback_id}\n\n"
            f"💬 请管理员处理"
        )
        
        # 创建按钮
        keyboard = [
            [
                InlineKeyboardButton("✅ 已解决", callback_data=f"resolve_{feedback_id}"),
                InlineKeyboardButton("❌ 驳回", callback_data=f"reject_{feedback_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 发送到反馈管理群组并置顶
        sent_message = await context.bot.send_message(
            chat_id=config['feedback_group'],
            text=group_message,
            reply_markup=reply_markup
        )
        
        # 置顶消息
        try:
            await context.bot.pin_chat_message(
                chat_id=config['feedback_group'],
                message_id=sent_message.message_id
            )
        except Exception as e:
            logger.error(f"置顶消息失败: {e}")
        
        # 更新数据库中的消息ID
        conn = sqlite3.connect(config['db_file'])
        c = conn.cursor()
        c.execute('UPDATE feedback SET message_id = ? WHERE id = ?', (sent_message.message_id, feedback_id))
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"处理反馈时出错: {e}")
        # 如果 message 对象存在，尝试发送错误消息
        if update and update.message:
            try:
                await update.message.reply_text("❌ 抱歉，处理您的反馈时出现错误，请稍后重试。")
            except Exception as e2:
                logger.error(f"发送错误消息失败: {e2}")
        else:
            logger.error("无法发送错误消息：消息对象不存在")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理按钮回调"""
    query = update.callback_query
    await query.answer()

    # 检查是否是管理员
    if query.from_user.id not in config['admin_ids']:
        await query.message.reply_text("❌ 抱歉，您没有权限处理反馈。")
        return

    # 解析回调数据
    try:
        parts = query.data.split('_')
        action = parts[0]
        
        if action in ['resolve', 'reject']:
            # 处理反馈状态更新
            message_id = int(parts[1])
            
            # 更新数据库
            conn = sqlite3.connect(config['db_file'])
            c = conn.cursor()
            c.execute('UPDATE feedback SET status = ? WHERE message_id = ?',
                      ('resolved' if action == 'resolve' else 'rejected', message_id))
            conn.commit()
            conn.close()

            # 更新消息
            status_text = "✅ 已解决" if action == 'resolve' else "❌ 已驳回"
            await query.edit_message_text(
                text=query.message.text + f"\n\n状态: {status_text}",
                reply_markup=None
            )

            # 取消置顶
            try:
                await context.bot.unpin_chat_message(
                    chat_id=config['feedback_group'],
                    message_id=query.message.message_id
                )
            except Exception as e:
                logger.error(f"取消置顶失败: {e}")

            # 通知用户
            try:
                # 获取反馈信息
                conn = sqlite3.connect(config['db_file'])
                c = conn.cursor()
                c.execute('SELECT user_id, content FROM feedback WHERE message_id = ?', (message_id,))
                feedback = c.fetchone()
                conn.close()

                if feedback:
                    user_id, content = feedback
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"📢 您的反馈已处理\n\n"
                             f"内容: {content}\n"
                             f"状态: {status_text}"
                    )
            except Exception as e:
                logger.error(f"通知用户失败: {e}")
        else:
            logger.error(f"未知的回调操作: {action}")
            await query.edit_message_text("❌ 未知的操作类型")
            
    except Exception as e:
        logger.error(f"处理回调时出错: {e}")
        await query.edit_message_text("❌ 处理请求时出现错误，请稍后重试")

def get_pending_feedback():
    """获取所有未解决的反馈"""
    conn = sqlite3.connect(config['db_file'])
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
        summary += f"用户: {feedback[2]}\n内容: {feedback[3]}\n时间: {feedback[5]}\n\n"

    await context.bot.send_message(
        chat_id=config['display_group'],
        text=summary
    )

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
    """设置反馈相关的处理器"""
    application.add_handler(MessageHandler(filters.Regex(r'^#反馈'), handle_feedback))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("help", help_command))
    logger.info("反馈处理器添加完成") 