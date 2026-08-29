import sqlite3, os
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '군종.db')
conn = sqlite3.connect(db_path)
for r in conn.execute('SELECT DISTINCT team FROM users WHERE team IS NOT NULL AND team != ""'):
    print(r[0].encode('cp949', errors='ignore').decode('cp949'))
conn.close()
