import json
import os

# 配置文件路径
CONFIG_FILE = 'config.json'

# 加载配置
def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"配置文件 {CONFIG_FILE} 不存在！")
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config

# 加载配置
config = load_config()

# Bot Token
BOT_TOKEN = config['bot_token']

# 反馈接收群组ID列表
FEEDBACK_GROUPS = config['feedback_groups']

# 反馈展示群组ID
DISPLAY_GROUP = config['display_group']

# 反馈标签
FEEDBACK_TAG = config['feedback_tag']

# 数据库文件
DB_FILE = config['db_file']

# 管理员ID列表
ADMIN_IDS = config['admin_ids']

# MoviePoilt API 配置
MOVIEPOILT_API_URL = config.get('moviepoilt_api_url', 'http://46.38.242.30:3000')
MOVIEPOILT_LOGIN_URL = f"{MOVIEPOILT_API_URL}/auth/login"
MOVIEPOILT_SEARCH_URL = f"{MOVIEPOILT_API_URL}/search"
MOVIEPOILT_USERNAME = config.get('moviepoilt_username', 'admin')
MOVIEPOILT_PASSWORD = config.get('moviepoilt_password', 'wonderful123') 