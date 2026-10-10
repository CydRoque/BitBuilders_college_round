import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect(dbname='postgres', user='postgres', password='0310', host='localhost', port=5432)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname='fairwork_db'")
if not cur.fetchone():
    cur.execute("CREATE DATABASE fairwork_db")
    print("Database fairwork_db created successfully!")
else:
    print("Database fairwork_db already exists!")
cur.close()
conn.close()
