import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Get database connection parameters from environment
# NO DEFAULT VALUES - must be set in .env file
DB_HOST = os.getenv("POSTGRES_HOST")
DB_PORT = os.getenv("POSTGRES_PORT")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")

if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
    raise ValueError("PostgreSQL configuration missing! Check .env file.")

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    cursor_factory=RealDictCursor
)
cursor = conn.cursor()

cursor.execute('SELECT * FROM users WHERE user_id = 1')
row = cursor.fetchone()

print('User ID 1 adatai (PostgreSQL):')
print('-' * 50)
if row:
    for col, val in row.items():
        print(f'{col:15}: {val}')
else:
    print('User not found')

conn.close()
