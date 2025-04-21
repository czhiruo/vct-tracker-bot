import sqlite3

con = sqlite3.connect("users.db")
cur = con.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teams TEXT,
        notifications TEXT
    )
""")

con.commit()