import sqlite3

conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()

# Show current state
c.execute('SELECT id, employee_id FROM users_userprofile')
print("BEFORE:", c.fetchall())

# Fix NULL/empty employee_ids with unique values
c.execute("UPDATE users_userprofile SET employee_id = 'EMP-' || CAST(id AS TEXT) WHERE employee_id IS NULL OR employee_id = ''")
conn.commit()
print("Updated", c.rowcount, "rows")

# Show after
c.execute('SELECT id, employee_id FROM users_userprofile')
print("AFTER:", c.fetchall())

conn.close()
print("Done! Now run: python manage.py migrate")
