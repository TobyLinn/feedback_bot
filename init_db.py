import sqlite3
import json
import os

# Load configuration
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

def init_db():
    """Initialize the database with required tables"""
    # Get database file path from config
    db_file = config['db_file']
    
    # If db_file is just a filename, use current directory
    if not os.path.dirname(db_file):
        db_file = os.path.join(os.getcwd(), db_file)
    
    # Connect to database
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    
    # Create feedback table
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  content TEXT,
                  feedback_type TEXT,
                  status TEXT,
                  created_at TIMESTAMP,
                  message_id INTEGER)''')
    
    # Create subscriptions table
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  tmdb_url TEXT,
                  title TEXT,
                  created_at TIMESTAMP,
                  status TEXT DEFAULT 'pending')''')
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print(f"Database initialized successfully at {db_file}")

if __name__ == "__main__":
    init_db() 