import sqlite3
from pathlib import Path

def setup_db():
    db_path = Path(__file__).parent / "data.db"
    print(f"Initializing database at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add some sample data if the table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        print("Inserting sample data...")
        users = [
            ("alice", "alice@example.com"),
            ("bob", "bob@example.com"),
            ("charlie", "charlie@example.com")
        ]
        cursor.executemany("INSERT INTO users (username, email) VALUES (?, ?)", users)
        conn.commit()
        print("Added 3 users.")
    else:
        print("Database already contains data, skipping insertion.")
        
    conn.close()
    print("Setup complete.")

if __name__ == "__main__":
    setup_db()
