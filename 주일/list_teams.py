import sqlite3
conn = sqlite3.connect('군종.db')
for r in conn.execute('SELECT DISTINCT team FROM users WHERE team IS NOT NULL AND team != ""'):
    print(r[0])
conn.close()
