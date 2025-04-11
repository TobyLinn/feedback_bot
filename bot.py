import sqlite3
import logging
import schedule
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import json
import requests
from urllib.parse import quote
from requests_toolbelt import MultipartEncoder
from feedback import setup_handlers as setup_feedback_handlers
from movie_request import setup_handlers as setup_movie_request_handlers, init_moviepoilt, toggle_movie_request

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
    'general': '一般反馈',
    'request': '求片'
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
    'general': '📢',
    'request': '🎬'
}

# 优先级图标
PRIORITY_ICONS = {
    '!': '⚪',
    '!!': '🟡',
    '!!!': '🔴'
}

# MoviePoilt API 配置
MOVIEPOILT_API_URL = config.get('moviepoilt_api_url', 'http://46.38.242.30:3000')
MOVIEPOILT_LOGIN_URL = f"{MOVIEPOILT_API_URL}/api/v1/login/access-token"
MOVIEPOILT_SEARCH_URL = f"{MOVIEPOILT_API_URL}/search"
MOVIEPOILT_USERNAME = config.get('moviepoilt_username', 'admin')
MOVIEPOILT_PASSWORD = config.get('moviepoilt_password', 'wonderful123')

# 初始化数据库
def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(config['db_file'])
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  content TEXT,
                  feedback_type TEXT,
                  status TEXT,
                  created_at TIMESTAMP,
                  message_id INTEGER)''')
    conn.commit()
    conn.close()

# 添加反馈到数据库
def add_feedback(user_id, username, content, message_id):
    conn = sqlite3.connect(config['db_file'])
    c = conn.cursor()
    c.execute('''INSERT INTO feedback (user_id, username, content, status, created_at, message_id)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, username, content, 'pending', datetime.now(), message_id))
    conn.commit()
    conn.close()

# 更新反馈状态
def update_feedback_status(message_id, status):
    conn = sqlite3.connect(config['db_file'])
    c = conn.cursor()
    c.execute('UPDATE feedback SET status = ? WHERE message_id = ?', (status, message_id))
    conn.commit()
    conn.close()

# 获取所有未解决的反馈
def get_pending_feedback():
    conn = sqlite3.connect(config['db_file'])
    c = conn.cursor()
    c.execute('SELECT * FROM feedback WHERE status = "pending" ORDER BY created_at DESC')
    feedbacks = c.fetchall()
    conn.close()
    return feedbacks

async def get_moviepoilt_token():
    """获取 MoviePoilt API Token"""
    try:
        logger.info(f"尝试登录 MoviePoilt: {MOVIEPOILT_LOGIN_URL}")
        logger.info(f"用户名: {MOVIEPOILT_USERNAME}")
        
        # 构建 multipart/form-data 数据
        multipart_data = MultipartEncoder(
            fields={
                'username': MOVIEPOILT_USERNAME,
                'password': MOVIEPOILT_PASSWORD,
                'otp_password': ''
            }
        )
        
        headers = {
            'Content-Type': multipart_data.content_type,
            'Accept': 'application/json'
        }
        
        response = requests.post(
            MOVIEPOILT_LOGIN_URL,
            headers=headers,
            data=multipart_data,
            timeout=10
        )
        
        logger.info(f"登录响应状态码: {response.status_code}")
        logger.info(f"登录响应内容: {response.text}")
        
        if response.status_code == 200:
            token = response.json().get('access_token')
            if token:
                logger.info("成功获取 Token")
                return token
            else:
                logger.error("响应中没有找到 Token")
                return None
        else:
            logger.error(f"登录失败，状态码: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        logger.error("请求超时")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("连接错误，请检查 API URL 是否正确")
        return None
    except Exception as e:
        logger.error(f"获取 MoviePoilt Token 失败: {str(e)}")
        return None

async def search_movie(title: str, token: str) -> list:
    """搜索电影"""
    try:
        # URL encode the title
        encoded_title = quote(title)
        search_url = f"{MOVIEPOILT_API_URL}/api/v1/media/search?page=1&title={encoded_title}&type=media"
        
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Authorization': f'Bearer {token}',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
        }
        
        logger.info(f"搜索URL: {search_url}")
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"搜索响应: {data}")
            
            # 解析搜索结果
            results = []
            for item in data:
                result = {
                    'title': item.get('title', '未知标题'),
                    'year': item.get('year', '未知年份'),
                    'type': item.get('type', '未知类型'),
                    'description': item.get('overview', '暂无简介'),
                    'rating': item.get('vote_average', '暂无评分'),
                    'source': item.get('source', '未知来源'),
                    'poster': item.get('poster_path', ''),
                    'detail_link': item.get('detail_link', ''),
                    'original_title': item.get('original_title', ''),
                    'release_date': item.get('release_date', ''),
                    'vote_count': item.get('vote_count', 0),
                    'popularity': item.get('popularity', 0),
                    'tmdb_id': item.get('tmdb_id'),
                    'douban_id': item.get('douban_id'),
                    'bangumi_id': item.get('bangumi_id')
                }
                results.append(result)
            return results
        else:
            logger.error(f"搜索失败，状态码: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"搜索出错: {str(e)}")
        return []

async def subscribe_tmdb(url, user_id, title):
    """订阅 TMDB 资源"""
    try:
        # 保存到数据库
        conn = sqlite3.connect(config['db_file'])
        c = conn.cursor()
        c.execute('''INSERT INTO subscriptions 
                     (user_id, tmdb_url, title, created_at, status)
                     VALUES (?, ?, ?, ?, ?)''',
                  (user_id, url, title, datetime.now(), 'pending'))
        conn.commit()
        conn.close()
        
        logger.info(f"用户 {user_id} 订阅了 TMDB URL: {url}")
        return True
    except Exception as e:
        logger.error(f"订阅失败: {e}")
        return False

async def subscribe_movie(token: str, movie_data: dict) -> bool:
    """订阅电影"""
    try:
        subscribe_url = f"{MOVIEPOILT_API_URL}/api/v1/subscribe/"
        
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
        }
        
        payload = {
            "name": movie_data['title'],
            "type": "电影",
            "year": movie_data['year'],
            "tmdbid": movie_data.get('tmdb_id'),
            "doubanid": movie_data.get('douban_id'),
            "bangumiid": movie_data.get('bangumi_id'),
            "season": 0,
            "best_version": 1
        }
        
        logger.info(f"订阅请求: {payload}")
        response = requests.post(subscribe_url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info("订阅成功")
            return True
        else:
            logger.error(f"订阅失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"订阅出错: {str(e)}")
        return False

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

async def init_moviepoilt(context: ContextTypes.DEFAULT_TYPE):
    """初始化 MoviePoilt Token"""
    try:
        token = await get_moviepoilt_token()
        if token:
            context.bot_data['moviepoilt_token'] = token
            logger.info("MoviePoilt Token 初始化成功")
        else:
            logger.error("MoviePoilt Token 初始化失败")
    except Exception as e:
        logger.error(f"MoviePoilt Token 初始化出错: {e}")

async def refresh_moviepoilt_token(context: ContextTypes.DEFAULT_TYPE):
    """刷新 MoviePoilt Token"""
    try:
        token = await get_moviepoilt_token()
        if token:
            context.bot_data['moviepoilt_token'] = token
            logger.info("MoviePoilt Token 刷新成功")
        else:
            logger.error("MoviePoilt Token 刷新失败")
    except Exception as e:
        logger.error(f"MoviePoilt Token 刷新出错: {e}")

async def handle_movie_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理求片请求"""
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
        if not content.startswith('#求片'):
            return
        
        # 记录用户信息
        user_info = f"用户ID: {user.id}\n用户名: {user.username}\n"
        logger.info(f"收到求片请求\n{user_info}内容: {content}")
        
        # 移除标签获取实际内容
        actual_content = content[3:].strip()
        if not actual_content:
            await message.reply_text("❌ 请在标签后输入电影名称")
            return
        
        # 保存到数据库
        conn = sqlite3.connect(config['db_file'])
        c = conn.cursor()
        c.execute('''
            INSERT INTO feedback (user_id, username, content, feedback_type, status, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', (user.id, user.username, actual_content, 'request', 'pending'))
        feedback_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # 搜索资源
        token = context.bot_data.get('moviepoilt_token')
        if not token:
            # 如果 token 不存在，尝试刷新
            await refresh_moviepoilt_token(context)
            token = context.bot_data.get('moviepoilt_token')
            
        if token:
            search_results = await search_movie(actual_content, token)
            if search_results:
                # 构建搜索结果消息
                results_message = f"🎬 为您找到以下资源：\n\n"
                buttons = []
                
                for idx, result in enumerate(search_results[:3], 1):  # 只显示前3个结果
                    results_message += f"{idx}. 《{result['title']}》\n"
                    if result['original_title']:
                        results_message += f"📌 原名：{result['original_title']}\n"
                    if result['year']:
                        results_message += f"📅 年份：{result['year']}\n"
                    if result['release_date']:
                        results_message += f"📆 上映日期：{result['release_date']}\n"
                    if result['rating']:
                        results_message += f"⭐️ 评分：{result['rating']} ({result['vote_count']}人评分)\n"
                    results_message += f"📊 来源：{result['source']}\n\n"
                    
                    # 添加订阅按钮
                    movie_id = result.get('tmdb_id') or result.get('douban_id') or result.get('bangumi_id')
                    if movie_id:
                        buttons.append(
                            InlineKeyboardButton(
                                f"📌 {idx}",
                                callback_data=f"sub_{movie_id}_{result['title']}_{result['year']}"
                            )
                        )
                
                # 添加一行说明文字
                results_message += "📌 点击序号订阅该资源"
                
                # 将所有按钮放在同一行
                keyboard = [buttons] if buttons else None
                reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
                
                # 发送到管理群组
                group_message = (
                    f"🎬 新的求片请求\n\n"
                    f"👤 用户信息：\n{user_info}"
                    f"📝 内容：{actual_content}\n"
                    f"🔢 请求ID：{feedback_id}\n\n"
                    f"搜索结果：\n{results_message}"
                )
                await context.bot.send_message(
                    chat_id=config['feedback_group'],
                    text=group_message,
                    reply_markup=reply_markup
                )
            else:
                # 发送到管理群组
                group_message = (
                    f"🎬 新的求片请求\n\n"
                    f"👤 用户信息：\n{user_info}"
                    f"📝 内容：{actual_content}\n"
                    f"🔢 请求ID：{feedback_id}\n\n"
                    "🔍 抱歉，没有找到相关资源。"
                )
                await context.bot.send_message(
                    chat_id=config['feedback_group'],
                    text=group_message
                )
        else:
            logger.error("无法获取 MoviePoilt Token")
            # 发送到管理群组
            group_message = (
                f"🎬 新的求片请求\n\n"
                f"👤 用户信息：\n{user_info}"
                f"📝 内容：{actual_content}\n"
                f"🔢 请求ID：{feedback_id}\n\n"
                "🔍 抱歉，搜索服务暂时不可用。"
            )
            await context.bot.send_message(
                chat_id=config['feedback_group'],
                text=group_message
            )
        
        # 发送确认消息给用户
        confirm_message = (
            f"✅ 已收到您的求片请求\n"
            f"📝 内容：{actual_content}\n"
            f"🔢 请求ID：{feedback_id}\n"
            f"⏳ 状态：待处理\n\n"
            "感谢您的请求！我们会尽快处理。"
        )
        await message.reply_text(confirm_message)
        
    except Exception as e:
        logger.error(f"处理求片请求时出错: {e}")
        # 如果 message 对象存在，尝试发送错误消息
        if update and update.message:
            try:
                await update.message.reply_text("❌ 抱歉，处理您的求片请求时出现错误，请稍后重试。")
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
        
        if action == 'sub':
            # 处理订阅请求
            movie_id = parts[1]
            title = parts[2]
            year = parts[3]
            
            # 获取 Token
            token = context.bot_data.get('moviepoilt_token')
            if not token:
                # 如果 token 不存在，尝试刷新
                await refresh_moviepoilt_token(context)
                token = context.bot_data.get('moviepoilt_token')
                
            if not token:
                await query.edit_message_text("❌ 订阅失败：无法获取认证信息")
                return
            
            # 构建电影数据
            movie_data = {
                'title': title,
                'year': year,
                'tmdb_id': movie_id if movie_id.isdigit() else None,
                'douban_id': movie_id if not movie_id.isdigit() else None,
                'bangumi_id': None
            }
            
            # 执行订阅
            if await subscribe_movie(token, movie_data):
                await query.edit_message_text(
                    f"✅ 已成功订阅《{title}》\n"
                    f"📅 年份：{year}\n\n"
                    "有新资源时会通知您！"
                )
            else:
                await query.edit_message_text("❌ 订阅失败，请稍后重试")
            return
            
        elif action in ['resolve', 'reject']:
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

async def daily_cleanup(context: ContextTypes.DEFAULT_TYPE):
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
    """处理 /help 命令"""
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
        "/pending - 查看待处理的反馈\n"
        "/toggle_movie yes/no - 开启/关闭求片功能\n"
        "/help - 显示此帮助信息"
    )
    await update.message.reply_text(help_text)

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /pending 命令"""
    # 检查是否是管理员
    if update.effective_user.id not in config['admin_ids']:
        await update.message.reply_text("❌ 抱歉，您没有权限查看待处理反馈。")
        return

    # 获取待处理反馈
    conn = sqlite3.connect(config['db_file'])
    c = conn.cursor()
    c.execute('''
        SELECT id, user_id, username, content, feedback_type, created_at
        FROM feedback
        WHERE status = 'pending'
        ORDER BY created_at DESC
    ''')
    pending_feedbacks = c.fetchall()
    conn.close()

    if not pending_feedbacks:
        await update.message.reply_text("✅ 目前没有待处理的反馈。")
        return

    # 构建消息
    message = "⏳ 待处理反馈列表：\n\n"
    for feedback in pending_feedbacks:
        feedback_id, user_id, username, content, feedback_type, created_at = feedback
        message += (
            f"🔢 ID: {feedback_id}\n"
            f"👤 用户: {username} ({user_id})\n"
            f"📝 内容: {content}\n"
            f"📌 类型: {feedback_type}\n"
            f"⏰ 时间: {created_at}\n\n"
        )

    await update.message.reply_text(message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    welcome_message = (
        "🤖 欢迎使用反馈机器人！\n\n"
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
        "/pending - 查看待处理的反馈\n"
        "/toggle_movie yes/no - 开启/关闭求片功能\n"
        "/help - 显示此帮助信息"
    )
    await update.message.reply_text(welcome_message)

async def clear_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """清除数据库中的所有反馈记录"""
    # 检查用户是否是管理员
    if update.effective_user.id not in config.get('admin_ids', []):
        await update.message.reply_text("抱歉，只有管理员可以执行此操作。")
        return
    
    from database import clear_database
    if clear_database():
        await update.message.reply_text("数据库已成功清除。")
    else:
        await update.message.reply_text("清除数据库时发生错误。")

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    return logging.getLogger(__name__)

def main():
    """主函数"""
    # 创建应用
    application = Application.builder().token(config['bot_token']).build()
    
    # 注册命令处理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("pending", pending))
    application.add_handler(CommandHandler("clear_db", clear_db))  # 添加清除数据库命令
    
    # 添加反馈和求片处理器
    setup_feedback_handlers(application)
    setup_movie_request_handlers(application)
    
    # 初始化 MoviePoilt Token
    application.add_handler(CommandHandler("init", init_moviepoilt))
    
    # 启动机器人
    application.run_polling()

if __name__ == '__main__':
    main() 