import sqlite3
import logging
import os
from datetime import datetime

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 数据库文件
DB_FILE = 'feedback.db'

def init_db():
    """初始化数据库"""
    try:
        # 如果数据库文件已存在，先删除
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
            logger.info(f"已删除旧的数据库文件: {DB_FILE}")

        # 创建新的数据库连接
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # 创建反馈表
        c.execute('''CREATE TABLE feedback
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
        c.execute('''CREATE TABLE groups
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      group_id INTEGER UNIQUE,
                      group_name TEXT,
                      is_admin_group INTEGER DEFAULT 0,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        # 创建触发器，自动更新 updated_at
        c.execute('''CREATE TRIGGER update_feedback_timestamp
                     AFTER UPDATE ON feedback
                     BEGIN
                         UPDATE feedback SET updated_at = CURRENT_TIMESTAMP
                         WHERE id = NEW.id;
                     END;''')

        conn.commit()
        conn.close()
        logger.info(f"数据库初始化成功: {DB_FILE}")
        return True

    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        return False

if __name__ == '__main__':
    init_db() 