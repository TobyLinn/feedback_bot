import logging
import json
import os

# 配置文件路径
VIRTUAL_USERS_FILE = 'virtual_users.json'

# 加载皮套用户配置
def load_virtual_users():
    """加载皮套用户配置"""
    if not os.path.exists(VIRTUAL_USERS_FILE):
        return {"virtual_users": [], "keywords": ["皮套", "vtuber", "虚拟"]}
    
    try:
        with open(VIRTUAL_USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"加载皮套用户配置失败: {e}")
        return {"virtual_users": [], "keywords": ["皮套", "vtuber", "虚拟"]}

# 检查是否是皮套用户
def is_virtual_user(user):
    """检查是否是皮套用户"""
    config = load_virtual_users()
    
    # 检查用户ID
    for virtual_user in config.get("virtual_users", []):
        if "user_id" in virtual_user and user.id == virtual_user["user_id"]:
            return True, virtual_user.get("display_name", user.username)
    
    # 检查用户名
    if user.username:
        for virtual_user in config.get("virtual_users", []):
            if "username" in virtual_user and user.username == virtual_user["username"]:
                return True, virtual_user.get("display_name", user.username)
        
        # 检查关键词
        for keyword in config.get("keywords", []):
            if keyword in user.username:
                return True, user.username
    
    return False, None

# 配置日志
def setup_logging():
    """配置日志"""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    return logging.getLogger(__name__)

# 格式化反馈消息
def format_feedback_message(user, content, category="general", priority="normal"):
    """格式化反馈消息"""
    # 检查是否是皮套用户
    is_virtual, virtual_name = is_virtual_user(user)
    
    # 优先级图标
    priority_icon = {
        "high": "🔴",
        "normal": "🟡",
        "low": "🟢"
    }.get(priority, "🟡")
    
    # 分类图标
    category_icon = {
        "bug": "🐛",
        "feature": "✨",
        "question": "❓",
        "suggestion": "💡",
        "general": "📝"
    }.get(category, "📝")
    
    if is_virtual:
        return f"📝 新反馈 {priority_icon} {category_icon}\n\n" \
               f"来自皮套: {virtual_name}\n" \
               f"分类: {category}\n" \
               f"优先级: {priority}\n\n" \
               f"反馈内容:\n{content}"
    else:
        return f"📝 新反馈 {priority_icon} {category_icon}\n\n" \
               f"来自用户: {user.full_name}\n" \
               f"用户ID: {user.id}\n" \
               f"用户名: @{user.username}\n" \
               f"分类: {category}\n" \
               f"优先级: {priority}\n\n" \
               f"反馈内容:\n{content}"

# 格式化状态更新消息
def format_status_update_message(content, status):
    """格式化状态更新消息"""
    status_icon = {
        "已解决": "✅",
        "已驳回": "❌"
    }.get(status, "")
    
    return f"📢 反馈状态更新\n\n" \
           f"您的反馈: {content}\n" \
           f"状态: {status_icon} {status}"

# 格式化每日汇总消息
def format_daily_summary(feedbacks):
    """格式化每日汇总消息"""
    summary = "📊 未解决反馈汇总\n\n"
    for feedback in feedbacks:
        summary += f"用户: {feedback[2]}\n内容: {feedback[3]}\n时间: {feedback[7]}\n\n"
    return summary

# 格式化统计信息
def format_stats_message(stats):
    """格式化统计信息"""
    return f"📊 反馈统计\n\n" \
           f"总反馈数: {stats['total']}\n" \
           f"待处理: {stats['pending']}\n" \
           f"已解决: {stats['resolved']}\n" \
           f"已驳回: {stats['rejected']}\n" \
           f"今日反馈: {stats['today']}" 