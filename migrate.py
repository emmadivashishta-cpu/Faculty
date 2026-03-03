import os
import re

def migrate_schema():
    with open('database/schema.sql', 'r') as f:
        content = f.read()
    
    # INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL PRIMARY KEY
    content = content.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
    # REAL -> FLOAT
    content = content.replace('REAL', 'FLOAT')
    
    with open('database/schema.sql', 'w') as f:
        f.write(content)

def migrate_app():
    with open('app.py', 'r') as f:
        content = f.read()

    # Imports
    content = content.replace('import sqlite3\n', 'import psycopg2\nfrom psycopg2.extras import RealDictCursor\n')

    # get_db function
    old_get_db = '''def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn'''

    new_get_db = '''class DBConnection:
    def __init__(self, conn):
        self.conn = conn
    def cursor(self):
        return self.conn.cursor()
    def execute(self, query, args=None):
        cur = self.conn.cursor()
        if args:
            cur.execute(query, args)
        else:
            cur.execute(query)
        return cur
    def commit(self):
        self.conn.commit()
    def close(self):
        self.conn.close()

def get_db():
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:password@localhost/faculty_impact')
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    return DBConnection(conn)'''
    content = content.replace(old_get_db, new_get_db)

    # replace all '?' with '%s' inside python strings. Actually just globally, it's safer than regex here
    content = content.replace(', ?', ', %s')
    content = content.replace('=?\n', '=%s\n')
    content = content.replace('= ?', '= %s')
    content = content.replace('=? ', '=%s ')
    content = content.replace('(?)', '(%s)')
    content = content.replace('?, ?', '%s, %s')
    content = content.replace(' (?,', ' (%s,')

    # lastrowid replacement 1
    content = content.replace(
        "cursor.execute(\"INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'faculty')\", \n                         (name, email, password))\n            user_id = cursor.lastrowid",
        "cursor.execute(\"INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'faculty') RETURNING id\", \n                         (name, email, password))\n            user_id = cursor.fetchone()['id']"
    )

    # lastrowid replacement 2
    content = content.replace(
        "cursor.execute(\"INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'faculty')\", \n                                     (name, email, password))\n                        faculty_id = cursor.lastrowid",
        "cursor.execute(\"INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'faculty') RETURNING id\", \n                                     (name, email, password))\n                        faculty_id = cursor.fetchone()['id']"
    )

    # Exceptions
    content = content.replace('sqlite3.IntegrityError', 'psycopg2.IntegrityError')

    # Remove ? inside UPDATEs that we might have missed
    content = re.sub(r'(\w+)=\?', r'\1=%s', content)
    content = content.replace('VALUES (%s, %s, %s)', 'VALUES (%s, %s, %s)') # just in case
    
    # A few specific replacements for missing question marks
    content = content.replace('SET total_score=%s, quality_score=%s, impact_score=%s, last_updated=CURRENT_TIMESTAMP', 'SET total_score=%s, quality_score=%s, impact_score=%s, last_updated=CURRENT_TIMESTAMP')
    content = content.replace('VALUES (%s, %s, %s, %s)', 'VALUES (%s, %s, %s, %s)')
    content = content.replace('SET setting_value=%s', 'SET setting_value=%s')
    content = content.replace('WHERE u.id = %s', 'WHERE u.id = %s')

    # Fix all ?
    content = content.replace('?', '%s')
    
    with open('app.py', 'w') as f:
        f.write(content)

def migrate_init():
    with open('init_db.py', 'r') as f:
        content = f.read()

    content = content.replace('import sqlite3\n', 'import psycopg2\nfrom psycopg2.extras import RealDictCursor\n')
    
    # Connect logic
    old_init = '''if os.path.exists(DATABASE):
        os.remove(DATABASE)
    
    conn = sqlite3.connect(DATABASE)'''
    
    new_init = '''db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:password@localhost/faculty_impact')
    
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)'''
    content = content.replace(old_init, new_init)

    # schema script
    content = content.replace('conn.executescript(f.read())', 'with conn.cursor() as cur: cur.execute(f.read())')
    
    # lastrowid
    content = content.replace(
        "cursor.execute(\n            \"INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)\",\n            (f['name'], f['email'], generate_password_hash('faculty123'), 'faculty')\n        )\n        user_id = cursor.lastrowid",
        "cursor.execute(\n            \"INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id\",\n            (f['name'], f['email'], generate_password_hash('faculty123'), 'faculty')\n        )\n        user_id = cursor.fetchone()['id']"
    )

    # question marks
    content = content.replace('?', '%s')

    with open('init_db.py', 'w') as f:
        f.write(content)

if __name__ == '__main__':
    migrate_schema()
    migrate_app()
    migrate_init()
    print("Migration scripts executed.")
