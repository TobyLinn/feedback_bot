import sqlite3
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 数据库文件
DB_FILE = 'feedback.db'

# 反馈状态
FEEDBACK_STATUS = {
    'pending': '待处理',
    'resolved': '已解决',
    'rejected': '已驳回'
}

def init_db():
    """初始化数据库"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # 创建反馈表
        c.execute('''CREATE TABLE IF NOT EXISTS feedback
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      username TEXT,
                      content TEXT,
                      message_id INTEGER,
                      feedback_type TEXT,
                      group_id INTEGER,
                      priority TEXT,
                      status TEXT DEFAULT 'pending',
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # 创建群组表
        c.execute('''CREATE TABLE IF NOT EXISTS groups
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      group_id INTEGER UNIQUE,
                      group_name TEXT,
                      is_admin_group INTEGER DEFAULT 0,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # 创建触发器，自动更新 updated_at
        c.execute('''CREATE TRIGGER IF NOT EXISTS update_feedback_timestamp
                     AFTER UPDATE ON feedback
                     BEGIN
                         UPDATE feedback SET updated_at = CURRENT_TIMESTAMP
                         WHERE id = NEW.id;
                     END;''')
        
        conn.commit()
        conn.close()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        raise

def add_feedback(user_id, username, content, message_id, feedback_type, group_id, priority='!'):
    """添加反馈"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''INSERT INTO feedback 
                     (user_id, username, content, message_id, feedback_type, group_id, priority)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, username, content, message_id, feedback_type, group_id, priority))
        feedback_id = c.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"添加反馈成功: {feedback_id}")
        return feedback_id
    except Exception as e:
        logger.error(f"添加反馈失败: {str(e)}")
        return None

def update_feedback_status(message_id, status):
    """更新反馈状态"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''UPDATE feedback 
                     SET status = ?
                     WHERE message_id = ?''',
                  (status, message_id))
        conn.commit()
        conn.close()
        logger.info(f"更新反馈状态成功: {message_id} -> {status}")
        return True
    except Exception as e:
        logger.error(f"更新反馈状态失败: {str(e)}")
        return False

def get_pending_feedback():
    """获取待处理的反馈"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT * FROM feedback 
                     WHERE status = 'pending'
                     ORDER BY created_at DESC''')
        feedbacks = c.fetchall()
        conn.close()
        return feedbacks
    except Exception as e:
        logger.error(f"获取待处理反馈失败: {str(e)}")
        return []

def get_feedback_by_message_id(message_id):
    """根据消息ID获取反馈"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT * FROM feedback 
                     WHERE message_id = ?''',
                  (message_id,))
        feedback = c.fetchone()
        conn.close()
        return feedback
    except Exception as e:
        logger.error(f"获取反馈失败: {str(e)}")
        return None

def get_feedback_stats():
    """获取反馈统计"""
    try:
        conn = sqlite3.connect(DB_FILE)
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
        return {
            'total': total,
            'resolved': resolved,
            'pending': pending
        }
    except Exception as e:
        logger.error(f"获取反馈统计失败: {str(e)}")
        return None

def clear_database():
    """清除数据库"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM feedback')
        c.execute('DELETE FROM groups')
        conn.commit()
        conn.close()
        logger.info("数据库已清除")
        return True
    except Exception as e:
        logger.error(f"清除数据库失败: {str(e)}")
        return False

def add_group(group_id, group_name, is_admin_group=False):
    """添加群组"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # 检查是否已存在
        c.execute('SELECT * FROM groups WHERE group_id = ?', (group_id,))
        existing = c.fetchone()
        
        if existing:
            # 更新现有记录
            c.execute('''UPDATE groups 
                         SET group_name = ?, is_admin_group = ?
                         WHERE group_id = ?''',
                      (group_name, 1 if is_admin_group else 0, group_id))
        else:
            # 添加新记录
            c.execute('''INSERT INTO groups 
                         (group_id, group_name, is_admin_group)
                         VALUES (?, ?, ?)''',
                      (group_id, group_name, 1 if is_admin_group else 0))
        
        conn.commit()
        conn.close()
        logger.info(f"添加群组成功: {group_id}")
        return True
    except Exception as e:
        logger.error(f"添加群组失败: {str(e)}")
        return False

def get_admin_group():
    """获取管理群组"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT group_id, group_name FROM groups 
                     WHERE is_admin_group = 1
                     LIMIT 1''')
        admin_group = c.fetchone()
        conn.close()
        
        if admin_group:
            logger.info(f"找到管理群组: {admin_group[0]} - {admin_group[1]}")
        else:
            logger.warning("未找到管理群组")
            
        return admin_group
    except Exception as e:
        logger.error(f"获取管理群组失败: {str(e)}")
        return None

def get_user_groups():
    """获取用户群组"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT group_id, group_name FROM groups 
                     WHERE is_admin_group = 0''')
        groups = c.fetchall()
        conn.close()
        return groups
    except Exception as e:
        logger.error(f"获取用户群组失败: {str(e)}")
        return []

def is_admin_group(group_id):
    """检查是否是管理群组"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT is_admin_group FROM groups 
                     WHERE group_id = ?''',
                  (group_id,))
        result = c.fetchone()
        conn.close()
        return result and result[0] == 1
    except Exception as e:
        logger.error(f"检查管理群组失败: {str(e)}")
        return False

def is_user_group(group_id):
    """检查是否是用户群组"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT is_admin_group FROM groups 
                     WHERE group_id = ?''',
                  (group_id,))
        result = c.fetchone()
        conn.close()
        return result and result[0] == 0
    except Exception as e:
        logger.error(f"检查用户群组失败: {str(e)}")
        return False

def remove_group(group_id):
    """移除群组"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
        conn.commit()
        conn.close()
        logger.info(f"移除群组成功: {group_id}")
        return True
    except Exception as e:
        logger.error(f"移除群组失败: {str(e)}")
        return False 