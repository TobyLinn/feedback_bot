import sqlite3
from datetime import datetime
from config import DB_FILE

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  content TEXT,
                  category TEXT,
                  priority TEXT,
                  status TEXT,
                  created_at TIMESTAMP,
                  message_id INTEGER)''')
    conn.commit()
    conn.close()

def add_feedback(user_id, username, content, message_id, category="general", priority="normal"):
    """添加反馈到数据库"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO feedback (user_id, username, content, category, priority, status, created_at, message_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, username, content, category, priority, 'pending', datetime.now(), message_id))
    conn.commit()
    conn.close()

def update_feedback_status(message_id, status):
    """更新反馈状态"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE feedback SET status = ? WHERE message_id = ?', (status, message_id))
    conn.commit()
    conn.close()

def get_pending_feedback():
    """获取所有未解决的反馈"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT * FROM feedback WHERE status = "pending" ORDER BY created_at DESC')
    feedbacks = c.fetchall()
    conn.close()
    return feedbacks

def get_feedback_by_message_id(message_id):
    """根据消息ID获取反馈信息"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT user_id, content FROM feedback WHERE message_id = ?', (message_id,))
    feedback = c.fetchone()
    conn.close()
    return feedback

def get_feedback_stats():
    """获取反馈统计信息"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 获取总反馈数
    c.execute('SELECT COUNT(*) FROM feedback')
    total = c.fetchone()[0]
    
    # 获取各状态反馈数
    c.execute('SELECT status, COUNT(*) FROM feedback GROUP BY status')
    status_counts = dict(c.fetchall())
    
    # 获取今日反馈数
    c.execute('SELECT COUNT(*) FROM feedback WHERE date(created_at) = date("now")')
    today = c.fetchone()[0]
    
    conn.close()
    
    return {
        'total': total,
        'pending': status_counts.get('pending', 0),
        'resolved': status_counts.get('resolved', 0),
        'rejected': status_counts.get('rejected', 0),
        'today': today
    }

def clear_database():
    """清除数据库中的所有反馈记录"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM feedback')
    conn.commit()
    conn.close()
    return True 