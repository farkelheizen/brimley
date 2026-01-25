import sqlite3
import os

DB_PATH = "demo.db"

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        purchase_count INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE settings (
        setting_name TEXT PRIMARY KEY,
        setting_value TEXT
    )
    """)
    
    users = [
        (1, "alice", 5),    # Score 50
        (2, "bob", 10),     # Score 100
        (3, "charlie", 2),  # Score 20
        (4, "dave", 20)     # Score 200
    ]

    # seed a default setting
    cursor.execute("INSERT INTO settings (setting_name, setting_value) VALUES (?,?)",
                   ("site_mode", "demo"))
    
    cursor.executemany("INSERT INTO users VALUES (?,?,?)", users)
    conn.commit()
    conn.close()
    print(f"Created {DB_PATH} with {len(users)} users.")

if __name__ == "__main__":
    init_db()
