import sqlite3
import logging
import requests
from urllib.parse import quote
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, CommandHandler, filters, ContextTypes
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

# MoviePoilt API 配置
MOVIEPOILT_API_URL = config.get('moviepoilt_api_url', 'http://46.38.242.30:3000')
MOVIEPOILT_LOGIN_URL = f"{MOVIEPOILT_API_URL}/api/v1/login/access-token"
MOVIEPOILT_SEARCH_URL = f"{MOVIEPOILT_API_URL}/search"
MOVIEPOILT_USERNAME = config.get('moviepoilt_username', 'admin')
MOVIEPOILT_PASSWORD = config.get('moviepoilt_password', 'wonderful123')

# 全局变量，用于控制求片功能状态
movie_request_enabled = True

# 初始化功能状态表
def init_feature_status():
    """初始化功能状态表"""
    conn = sqlite3.connect(config['db_file'])
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS feature_status (
            feature_name TEXT PRIMARY KEY,
            enabled INTEGER DEFAULT 1
        )
    ''')
    # 确保 movie_request 状态存在
    c.execute('''
        INSERT OR IGNORE INTO feature_status (feature_name, enabled)
        VALUES ('movie_request', 1)
    ''')
    conn.commit()
    conn.close()

# 获取功能状态
def get_feature_status(feature_name):
    """获取功能状态"""
    conn = sqlite3.connect(config['db_file'])
    c = conn.cursor()
    c.execute('SELECT enabled FROM feature_status WHERE feature_name = ?', (feature_name,))
    result = c.fetchone()
    conn.close()
    return bool(result[0]) if result else True

# 设置功能状态
def set_feature_status(feature_name, enabled):
    """设置功能状态"""
    conn = sqlite3.connect(config['db_file'])
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO feature_status (feature_name, enabled)
        VALUES (?, ?)
    ''', (feature_name, 1 if enabled else 0))
    conn.commit()
    conn.close()

# 初始化功能状态表
init_feature_status()

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

async def toggle_movie_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切换求片功能的开启/关闭状态"""
    # 检查是否是管理员
    if update.effective_user.id not in config['admin_ids']:
        logger.warning(f"非管理员尝试切换求片功能状态: {update.effective_user.id}")
        await update.message.reply_text("❌ 抱歉，您没有权限执行此操作。")
        return
    
    # 获取命令参数
    args = context.args
    if not args:
        # 如果没有参数，显示当前状态
        current_status = get_feature_status('movie_request')
        status = "开启" if current_status else "关闭"
        logger.info(f"管理员查询求片功能状态: {status}")
        await update.message.reply_text(f"当前求片功能状态：{status}\n\n使用方式：\n/toggle_movie yes - 开启求片功能\n/toggle_movie no - 关闭求片功能")
        return
    
    # 处理参数
    arg = args[0].lower()
    if arg == 'yes':
        set_feature_status('movie_request', True)
        status = "开启"
        logger.info(f"管理员开启求片功能: {update.effective_user.id}")
    elif arg == 'no':
        set_feature_status('movie_request', False)
        status = "关闭"
        logger.info(f"管理员关闭求片功能: {update.effective_user.id}")
    else:
        logger.warning(f"管理员使用无效参数: {arg}")
        await update.message.reply_text("❌ 无效的参数。请使用：\n/toggle_movie yes - 开启求片功能\n/toggle_movie no - 关闭求片功能")
        return
    
    # 验证状态是否已更改
    new_status = get_feature_status('movie_request')
    if (arg == 'yes' and not new_status) or (arg == 'no' and new_status):
        logger.error(f"求片功能状态更改失败: 期望 {arg}, 实际 {new_status}")
        await update.message.reply_text("❌ 状态更改失败，请重试")
        return
    
    await update.message.reply_text(f"✅ 求片功能已{status}")
    
    # 发送到管理群组
    admin_message = (
        f"🔔 管理员操作通知\n\n"
        f"👤 操作人：{update.effective_user.username} ({update.effective_user.id})\n"
        f"📝 操作：求片功能已{status}\n"
        f"⏰ 时间：{update.message.date}"
    )
    await context.bot.send_message(
        chat_id=config['feedback_group'],
        text=admin_message
    )

async def handle_movie_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理求片请求"""
    # 检查功能是否开启
    if not get_feature_status('movie_request'):
        await update.message.reply_text("❌ 抱歉，求片功能当前已关闭。")
        return
    
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

async def handle_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理订阅按钮点击"""
    try:
        query = update.callback_query
        await query.answer()
        
        # 检查是否是管理员
        if query.from_user.id not in config['admin_ids']:
            await query.edit_message_text("❌ 抱歉，您没有权限进行订阅操作。")
            return
        
        # 解析回调数据
        try:
            _, movie_id, title, year = query.data.split('_')
        except ValueError:
            logger.error(f"解析回调数据失败: {query.data}")
            await query.edit_message_text("❌ 订阅失败：数据格式错误")
            return
        
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
            
    except Exception as e:
        logger.error(f"处理订阅时出错: {e}")
        await query.edit_message_text("❌ 处理订阅时出现错误，请稍后重试")

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

def setup_handlers(application: Application):
    """设置求片相关的处理器"""
    application.add_handler(MessageHandler(filters.Regex(r'^#求片'), handle_movie_request))
    application.add_handler(CallbackQueryHandler(handle_subscribe, pattern="^sub_"))
    application.add_handler(CommandHandler("toggle_movie", toggle_movie_request))
    logger.info("求片处理器添加完成") 