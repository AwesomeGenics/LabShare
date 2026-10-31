import sqlite3

conn = sqlite3.connect('temp.db', check_same_thread=False)
conn.row_factory = sqlite3.Row
csr = conn.cursor()

def db_init_temp():
    query = '''CREATE TABLE IF NOT EXISTS temp(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL
    )'''
    csr.execute(query)


def add_temporary(email, name):
    query = '''INSERT INTO temp (email, name) VALUES (?,?)'''
    csr.execute(query, (email, name,))
    conn.commit()


def check_existance(email):
    query = '''SELECT (id) FROM temp WHERE email = ?'''
    return csr.execute(query, (email,)).fetchone()