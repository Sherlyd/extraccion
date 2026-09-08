# db.py
# Capa de conexion a Postgres. La URL sale de la variable de entorno
# DATABASE_URL (asi la entrega AWS RDS/App Runner) o de un archivo
# .env local para desarrollo (ver .env.example). ConexionPG envuelve
# la conexion real de psycopg2 para que conn.execute(sql, params) siga
# funcionando igual que con sqlite3.Connection.

import os
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

load_dotenv()  # lee .env si existe; si no, no hace nada (no rompe)

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://postgres:postgres123@localhost:5432/reportes_piletas',  # solo desarrollo local
)


class ConexionPG:
    def __init__(self, pg_conn):
        self._conn = pg_conn

    def execute(self, sql, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or [])
        return cur

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_connection():
    pg_conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return ConexionPG(pg_conn)


def init_db():
    """Crea las tablas si no existen. Se puede correr las veces que
    sea, no borra datos existentes."""
    conn = get_connection()
    ruta_schema = os.path.join(os.path.dirname(__file__), 'db', 'schema_postgres.sql')
    with open(ruta_schema, encoding='utf-8') as f:
        conn.execute(f.read())
    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    print('Base de datos inicializada (Postgres):', DATABASE_URL.split('@')[-1])