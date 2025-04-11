import os
import sqlite3
from config import DB_FILE

def init_db():
    """初始化数据库"""
    # 如果数据库文件存在，先删除
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 创建反馈表
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  content TEXT,
                  feedback_type TEXT,
                  status TEXT,
                  created_at TIMESTAMP,
                  message_id INTEGER)''')
    
    # 创建订阅表
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  tmdb_url TEXT,
                  title TEXT,
                  created_at TIMESTAMP,
                  status TEXT DEFAULT 'pending')''')
    
    conn.commit()
    conn.close()
    print("数据库初始化完成！")

if __name__ == '__main__':
    init_db() 