import sqlite3
import logging
import schedule
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommandScopeDefault, BotCommandScopeChat, BotCommandScopeAllPrivateChats
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import json
from database import (
    init_db, add_feedback, update_feedback_status, get_pending_feedback,
    get_feedback_by_message_id, get_feedback_stats, clear_database,
    add_group, get_admin_group, get_user_groups, is_admin_group,
    remove_group, is_user_group
)

# 加载配置文件
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 反馈类型字典
FEEDBACK_TYPES = {
    'bug': '问题反馈',
    'feature': '功能建议',
    'question': '疑问咨询',
    'suggestion': '一般建议',
    'general': '一般反馈'
}

# 优先级字典
PRIORITY_LEVELS = {
    '!': '普通',
    '!!': '高',
    '!!!': '紧急'
}

# 反馈类型图标
FEEDBACK_ICONS = {
    'bug': '🐛',
    'feature': '💡',
    'question': '❓',
    'suggestion': '📝',
    'general': '📢'
}

# 优先级图标
PRIORITY_ICONS = {
    '!': '⚪',
    '!!': '🟡',
    '!!!': '🔴'
}

# 初始化数据库
init_db()

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理反馈消息"""
    try:
        user = update.effective_user
        message = update.effective_message
        chat_id = update.effective_chat.id
        
        # 检查是否在用户群组中
        if not is_user_group(chat_id):
            return

        # 检查消息是否以 #反馈 开头
        content = message.text
        if not content or not content.startswith('#反馈'):
            return

        # 解析反馈内容
        content = content[3:].strip()  # 移除 #反馈 前缀
        if not content:
            await message.reply_text("请提供反馈内容。")
            return

        # 确定反馈类型
        feedback_type = 'general'
        for key, value in FEEDBACK_TYPES.items():
            if content.startswith(f"#{value}"):
                feedback_type = key
                content = content[len(value)+1:].strip()
                break

        # 确定优先级
        priority = '!'
        if '!!!' in content:
            priority = '!!!'
            content = content.replace('!!!', '').strip()
        elif '!!' in content:
            priority = '!!'
            content = content.replace('!!', '').strip()

        # 添加反馈到数据库
        feedback_id = add_feedback(
            user_id=user.id,
            username=user.username or user.first_name,
            content=content,
            message_id=message.message_id,
            feedback_type=feedback_type,
            group_id=chat_id,
            priority=priority
        )

        if feedback_id:
            # 构建确认消息
            confirm_message = (
                f"{FEEDBACK_ICONS[feedback_type]} 感谢您的反馈！\n\n"
                f"📝 内容：{content}\n"
                f"📌 类型：{FEEDBACK_TYPES[feedback_type]}\n"
                f"🔢 优先级：{PRIORITY_ICONS[priority]} {PRIORITY_LEVELS[priority]}\n"
                f"⏳ 状态：待处理\n\n"
                "我们会尽快处理您的反馈。"
            )
            await message.reply_text(confirm_message)

            # 获取管理群组
            admin_group = get_admin_group()
            if not admin_group:
                logger.error("未找到管理群组")
                await message.reply_text("抱歉，系统配置错误，请联系管理员。")
                return

            admin_group_id = admin_group[0]  # 获取群组ID
            if not admin_group_id:
                logger.error("管理群组ID为空")
                await message.reply_text("抱歉，系统配置错误，请联系管理员。")
                return

            try:
                # 构建管理群组消息
                admin_message = (
                    f"📢 新反馈\n\n"
                    f"👤 用户信息：\n"
                    f"- ID: {user.id}\n"
                    f"- 用户名: [{user.username or user.first_name}](tg://user?id={user.id})\n\n"
                    f"📝 反馈内容：\n{content}\n\n"
                    f"📌 类型：{FEEDBACK_TYPES[feedback_type]}\n"
                    f"🔢 优先级：{PRIORITY_ICONS[priority]} {PRIORITY_LEVELS[priority]}"
                )
                
                # 创建处理按钮
                keyboard = [
                    [
                        InlineKeyboardButton("✅ 已解决", callback_data=f"resolve_{message.message_id}"),
                        InlineKeyboardButton("❌ 已拒绝", callback_data=f"reject_{message.message_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # 发送到管理群组
                logger.info(f"尝试发送消息到管理群组: {admin_group_id}")
                admin_msg = await context.bot.send_message(
                    chat_id=admin_group_id,
                    text=admin_message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                logger.info("成功发送消息到管理群组")
                
                # 置顶消息
                try:
                    await context.bot.pin_chat_message(
                        chat_id=admin_group_id,
                        message_id=admin_msg.message_id
                    )
                    logger.info("成功置顶消息")
                except Exception as e:
                    logger.error(f"置顶消息失败: {e}")
                    # 继续执行，不中断流程

            except Exception as e:
                logger.error(f"发送消息到管理群组失败: {str(e)}")
                await message.reply_text("抱歉，发送反馈到管理群组时出现错误，请联系管理员。")
                return

        else:
            await message.reply_text("抱歉，提交反馈时出现错误。请稍后再试。")

    except Exception as e:
        logger.error(f"处理反馈时出错: {str(e)}")
        await message.reply_text("处理反馈时出现错误，请稍后再试。")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理回调查询"""
    try:
        query = update.callback_query
        await query.answer()

        data = query.data
        if not data:
            return

        # 解析回调数据
        action, *params = data.split('_')
        if not action or not params:
            return

        if action == 'resolve':
            # 处理反馈
            message_id = int(params[0])
            success = update_feedback_status(message_id, 'resolved')
            if success:
                # 获取反馈详情
                feedback = get_feedback_by_message_id(message_id)
                if feedback:
                    # 从反馈记录中获取所需字段
                    user_id = feedback[1]  # user_id
                    content = feedback[3]  # content
                    group_id = feedback[6]  # group_id
                    
                    logger.info(f"准备发送反馈处理通知: group_id={group_id}, user_id={user_id}")
                    
                    # 构建通知消息
                    notification = (
                        "📢 反馈处理通知\n\n"
                        f"您的反馈已被处理：\n"
                        f"📝 内容：{content}\n"
                        f"✅ 状态：已解决\n"
                        f"⏰ 处理时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        "感谢您的反馈！"
                    )
                    # 在原始群组发送通知
                    try:
                        logger.info(f"尝试发送消息到群组: {group_id}")
                        await context.bot.send_message(
                            chat_id=group_id,
                            text=notification
                        )
                        logger.info("成功发送反馈处理通知")
                    except Exception as e:
                        logger.error(f"发送反馈处理通知失败: {str(e)}")
                        # 继续执行，不中断流程
                
                # 更新消息并取消置顶
                await query.edit_message_text(
                    text=f"{query.message.text}\n\n✅ 已标记为已解决\n👤 处理人：{query.from_user.username or query.from_user.first_name}",
                    reply_markup=None
                )
                try:
                    await context.bot.unpin_chat_message(
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id
                    )
                    logger.info("成功取消置顶消息")
                except Exception as e:
                    logger.error(f"取消置顶消息失败: {e}")
            else:
                await query.edit_message_text(
                    text=f"{query.message.text}\n\n❌ 更新状态失败",
                    reply_markup=None
                )
        elif action == 'reject':
            # 处理反馈
            message_id = int(params[0])
            success = update_feedback_status(message_id, 'rejected')
            if success:
                # 获取反馈详情
                feedback = get_feedback_by_message_id(message_id)
                if feedback:
                    # 从反馈记录中获取所需字段
                    user_id = feedback[1]  # user_id
                    content = feedback[3]  # content
                    group_id = feedback[6]  # group_id
                    
                    logger.info(f"准备发送反馈处理通知: group_id={group_id}, user_id={user_id}")
                    
                    # 构建通知消息
                    notification = (
                        "📢 反馈处理通知\n\n"
                        f"您的反馈已被处理：\n"
                        f"📝 内容：{content}\n"
                        f"❌ 状态：已驳回\n"
                        f"⏰ 处理时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        "如有疑问，请重新提交反馈或联系管理员。"
                    )
                    # 在原始群组发送通知
                    try:
                        logger.info(f"尝试发送消息到群组: {group_id}")
                        await context.bot.send_message(
                            chat_id=group_id,
                            text=notification
                        )
                        logger.info("成功发送反馈处理通知")
                    except Exception as e:
                        logger.error(f"发送反馈处理通知失败: {str(e)}")
                        # 继续执行，不中断流程
                
                # 更新消息并取消置顶
                await query.edit_message_text(
                    text=f"{query.message.text}\n\n❌ 已标记为已驳回\n👤 处理人：{query.from_user.username or query.from_user.first_name}",
                    reply_markup=None
                )
                try:
                    await context.bot.unpin_chat_message(
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id
                    )
                    logger.info("成功取消置顶消息")
                except Exception as e:
                    logger.error(f"取消置顶消息失败: {e}")
            else:
                await query.edit_message_text(
                    text=f"{query.message.text}\n\n❌ 更新状态失败",
                    reply_markup=None
                )
    except Exception as e:
        logger.error(f"处理回调查询时出错: {str(e)}")
        await query.edit_message_text(
            text=f"{query.message.text}\n\n❌ 处理失败",
            reply_markup=None
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
    
    conn.close()

    # 创建统计消息
    stats_message = (
        f"📊 反馈统计\n\n"
        f"总反馈数: {total}\n"
        f"已解决: {resolved}\n"
        f"待处理: {pending}"
    )

    await update.message.reply_text(stats_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /help 命令"""
    # 检查是否是管理员
    is_admin = update.effective_user.id in config['admin_ids']
    
    # 基础帮助信息
    help_text = (
        "🤖 反馈机器人使用说明\n\n"
        "📝 发送反馈：\n"
        "- 使用 #反馈 开头发送一般反馈\n\n"
        "🎯 反馈类型：\n"
        "- 问题反馈 🐛\n"
        "- 功能建议 💡\n"
        "- 疑问咨询 ❓\n"
        "- 一般建议 📝\n"
        "- 一般反馈 📢\n\n"
    )
    
    # 如果是管理员，添加管理员命令
    if is_admin:
        help_text += (
            "📊 管理员命令：\n"
            "/stats - 查看反馈统计\n"
            "/pending - 查看待处理的反馈\n"
            "/clear_db - 清除所有反馈记录\n"
            "/set_admin_group - 设置当前群组为管理群组\n"
            "/set_user_group - 设置当前群组为用户群组\n"
            "/remove_user_group - 移除当前用户群组\n"
            "/list_groups - 列出所有群组\n"
            "/help - 显示此帮助信息"
        )
    else:
        help_text += "📊 命令：\n/help - 显示此帮助信息"
    
    await update.message.reply_text(help_text)

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看待处理的反馈"""
    try:
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # 检查是否为管理员群组
        if not is_admin_group(chat_id):
            await update.message.reply_text("此命令只能在管理员群组中使用。")
            return

        # 获取待处理的反馈
        pending_feedback = get_pending_feedback()

        if not pending_feedback:
            await update.message.reply_text("目前没有待处理的反馈。")
            return

        # 构建消息
        message = "待处理的反馈：\n\n"
        
        if pending_feedback:
            message += "📝 待处理反馈：\n"
            for feedback in pending_feedback:
                message += f"- {feedback[3]} (来自: {feedback[2]})\n"
            message += "\n"

        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"查看待处理内容时出错: {str(e)}")
        await update.message.reply_text("获取待处理内容时出现错误，请稍后再试。")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    # 检查是否是管理员
    is_admin = update.effective_user.id in config['admin_ids']
    
    # 基础欢迎信息
    welcome_message = (
        "🤖 欢迎使用反馈机器人！\n\n"
        "📝 发送反馈：\n"
        "- 使用 #反馈 开头发送一般反馈\n\n"
        "🎯 反馈类型：\n"
        "- 问题反馈 🐛\n"
        "- 功能建议 💡\n"
        "- 疑问咨询 ❓\n"
        "- 一般建议 📝\n"
        "- 一般反馈 📢\n\n"
    )
    
    # 如果是管理员，添加管理员命令
    if is_admin:
        welcome_message += (
            "📊 管理员命令：\n"
            "/stats - 查看反馈统计\n"
            "/pending - 查看待处理的反馈\n"
            "/clear_db - 清除所有反馈记录\n"
            "/set_admin_group - 设置当前群组为管理群组\n"
            "/set_user_group - 设置当前群组为用户群组\n"
            "/remove_user_group - 移除当前用户群组\n"
            "/list_groups - 列出所有群组\n"
            "/help - 显示此帮助信息"
        )
    else:
        welcome_message += "📊 命令：\n/help - 显示此帮助信息"
    
    await update.message.reply_text(welcome_message)

async def clear_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """清除数据库中的所有反馈记录"""
    # 检查用户是否是管理员
    if update.effective_user.id not in config.get('admin_ids', []):
        await update.message.reply_text("抱歉，只有管理员可以执行此操作。")
        return
    
    if clear_database():
        await update.message.reply_text("数据库已成功清除。")
    else:
        await update.message.reply_text("清除数据库时发生错误。")

async def set_admin_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置管理群组"""
    if not update.message:
        return
    
    group_id = update.message.chat_id
    group_name = update.message.chat.title
    
    if add_group(group_id, group_name, is_admin_group=True):
        await update.message.reply_text("✅ 已设置此群组为管理群组")
    else:
        await update.message.reply_text("❌ 设置管理群组失败")

async def set_user_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置用户群组"""
    if not update.message:
        return
    
    group_id = update.message.chat_id
    group_name = update.message.chat.title
    
    if add_group(group_id, group_name, is_admin_group=False):
        await update.message.reply_text("✅ 已设置此群组为用户群组")
    else:
        await update.message.reply_text("❌ 设置用户群组失败")

async def remove_user_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """移除用户群组"""
    if update.effective_user.id not in config['admin_ids']:
        await update.message.reply_text("只有管理员可以移除用户群组")
        return
    
    if not update.effective_chat.type == 'group' and not update.effective_chat.type == 'supergroup':
        await update.message.reply_text("请在群组中使用此命令")
        return
    
    group_id = update.effective_chat.id
    remove_group(group_id)
    await update.message.reply_text("已移除当前群组")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出所有群组"""
    try:
        # 检查是否是管理员
        if update.effective_user.id not in config['admin_ids']:
            await update.message.reply_text("❌ 抱歉，您没有权限执行此操作。")
            return
            
        # 获取管理群组
        admin_group = get_admin_group()
        message = "📋 群组列表：\n\n"
        
        if admin_group:
            message += f"管理群组：\n- ID: {admin_group[0]}\n\n"
        else:
            message += "管理群组：未设置\n\n"
            
        # 获取用户群组
        user_groups = get_user_groups()
        if user_groups:
            message += "用户群组：\n"
            for group in user_groups:
                message += f"- {group[1]} (ID: {group[0]})\n"
        else:
            message += "用户群组：无\n"
            
        await update.message.reply_text(message)
        
    except Exception as e:
        logger.error(f"列出群组时出错: {str(e)}")
        await update.message.reply_text("❌ 列出群组时出错，请稍后重试。")

def main():
    """主函数"""
    # 创建应用
    application = Application.builder().token(config['bot_token']).build()

    # 设置管理员命令列表
    admin_commands = [
        ("start", "开始使用机器人"),
        ("help", "显示帮助信息"),
        ("stats", "查看反馈统计"),
        ("pending", "查看待处理的反馈"),
        ("clear_db", "清除所有反馈记录"),
        ("set_admin_group", "设置当前群组为管理群组"),
        ("set_user_group", "设置当前群组为用户群组"),
        ("remove_user_group", "移除当前用户群组"),
        ("list_groups", "列出所有群组")
    ]
    
    # 设置普通用户命令列表
    user_commands = [
        ("start", "开始使用机器人"),
        ("help", "显示帮助信息")
    ]
    
    # 设置默认命令（所有用户）
    application.bot.set_my_commands(commands=user_commands, scope=BotCommandScopeDefault())
    
    # 设置管理员命令（私聊）
    application.bot.set_my_commands(commands=admin_commands, scope=BotCommandScopeAllPrivateChats())
    
    # 设置群组命令
    # 获取管理群组
    admin_group = get_admin_group()
    if admin_group:
        admin_group_id = admin_group[0]
        # 为管理群组设置管理员命令
        application.bot.set_my_commands(commands=admin_commands, scope=BotCommandScopeChat(chat_id=admin_group_id))
    
    # 获取用户群组
    user_groups = get_user_groups()
    if user_groups:
        for group in user_groups:
            group_id = group[0]
            # 为用户群组设置普通命令
            application.bot.set_my_commands(commands=user_commands, scope=BotCommandScopeChat(chat_id=group_id))

    # 添加命令处理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("pending", pending))
    application.add_handler(CommandHandler("clear_db", clear_db))
    application.add_handler(CommandHandler("set_admin_group", set_admin_group))
    application.add_handler(CommandHandler("set_user_group", set_user_group))
    application.add_handler(CommandHandler("remove_user_group", remove_user_group))
    application.add_handler(CommandHandler("list_groups", list_groups))

    # 添加反馈处理器
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback))

    # 添加回调查询处理器
    application.add_handler(CallbackQueryHandler(handle_callback))

    # 启动应用
    application.run_polling()

if __name__ == '__main__':
    main() 