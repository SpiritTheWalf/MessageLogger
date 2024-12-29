import sqlite3


def check():
    try:
        # Connect to the database
        conn = sqlite3.connect('levels.db')
        cursor = conn.cursor()

        # Check the number of rows in the 'levels' table
        table_name = 'levels'
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(count)
        return count
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        # Ensure the connection is closed
        if conn:
            conn.close()

if __name__ == "__main__":
    check()
