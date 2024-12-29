import sqlite3

# Connect to the database
conn = sqlite3.connect('levels.db')
cursor = conn.cursor()

# Count the number of rows in the table
table_name = 'levels'
cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
count = cursor.fetchone()[0]

print(f"Number of entries in {table_name}: {count}")

# Close the connection
conn.close()
