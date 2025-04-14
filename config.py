import json
import os

# 获取配置文件路径
config_path = os.path.join(os.path.dirname(__file__), 'config.json')

# 加载配置文件
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

# 数据库文件路径
DB_FILE = config.get('db_file', 'feedback.db')

# 日志配置
LOG_FILE = config.get('log_file', 'bot.log')
LOG_LEVEL = config.get('log_level', 'INFO')

# 机器人配置
BOT_TOKEN = config.get('bot_token', '')
ADMIN_IDS = config.get('admin_ids', [])

# 反馈配置
FEEDBACK_TYPES = {
    'bug': '问题反馈',
    'feature': '功能建议',
    'question': '疑问咨询',
    'suggestion': '一般建议',
    'general': '一般反馈'
}

# 优先级配置
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

# 群组配置
ADMIN_GROUP_ID = config['admin_group_id']
FEEDBACK_GROUPS = config['feedback_groups']
DISPLAY_GROUP = config['display_group']
FEEDBACK_TAG = config['feedback_tag'] 