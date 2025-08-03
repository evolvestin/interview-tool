import sqlite3

DATABASE = 'questions.db'


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            order_index INTEGER
        )
    '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            answer TEXT NOT NULL,
            order_index INTEGER,
            theme_id INTEGER,
            FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE SET NULL
        )
    '''
    )

    conn.commit()
    conn.close()
