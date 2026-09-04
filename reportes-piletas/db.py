# db.py
# Conexion y creacion de la base de datos SQLite.

import sqlite3
import config


def get_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    """Crea las tablas si no existen. Se puede correr las veces que sea,
    no borra datos existentes."""
    conn = get_connection()
    with open('./db/schema.sql', encoding='utf-8') as f:
        conn.executescript(f.read())

    # Migracion defensiva: si la base ya existia de antes de que
    # agregaramos login con contraseña, sumamos la columna sin perder
    # los usuarios ya cargados.
    columnas = [c['name'] for c in conn.execute('PRAGMA table_info(usuarios)').fetchall()]
    if 'password_hash' not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''")

    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    print('Base de datos inicializada en', config.DB_PATH)
