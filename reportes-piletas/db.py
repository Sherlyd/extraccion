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
    columnas_usuarios = [c['name'] for c in conn.execute('PRAGMA table_info(usuarios)').fetchall()]
    if 'password_hash' not in columnas_usuarios:
        conn.execute("ALTER TABLE usuarios ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''")
    if 'centro_distribucion' not in columnas_usuarios:
        conn.execute("ALTER TABLE usuarios ADD COLUMN centro_distribucion TEXT")
    if 'zona' not in columnas_usuarios:
        conn.execute("ALTER TABLE usuarios ADD COLUMN zona TEXT")

    columnas_fact = [c['name'] for c in conn.execute('PRAGMA table_info(facturacion)').fetchall()]
    if 'centro_distribucion' not in columnas_fact:
        conn.execute("ALTER TABLE facturacion ADD COLUMN centro_distribucion TEXT")
    if 'zona' not in columnas_fact:
        conn.execute("ALTER TABLE facturacion ADD COLUMN zona TEXT")
    if 'familia4' not in columnas_fact:
        conn.execute("ALTER TABLE facturacion ADD COLUMN familia4 TEXT")
    if 'familia2' not in columnas_fact:
        conn.execute("ALTER TABLE facturacion ADD COLUMN familia2 TEXT")
    if 'familia3' not in columnas_fact:
        conn.execute("ALTER TABLE facturacion ADD COLUMN familia3 TEXT")

    columnas_ped = [c['name'] for c in conn.execute('PRAGMA table_info(pedidos)').fetchall()]
    if 'centro_distribucion' not in columnas_ped:
        conn.execute("ALTER TABLE pedidos ADD COLUMN centro_distribucion TEXT")
    if 'zona' not in columnas_ped:
        conn.execute("ALTER TABLE pedidos ADD COLUMN zona TEXT")

    columnas_cart = [c['name'] for c in conn.execute('PRAGMA table_info(cartera_pendiente)').fetchall()]
    if 'centro_distribucion' not in columnas_cart:
        conn.execute("ALTER TABLE cartera_pendiente ADD COLUMN centro_distribucion TEXT")
    if 'zona' not in columnas_cart:
        conn.execute("ALTER TABLE cartera_pendiente ADD COLUMN zona TEXT")

    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    print('Base de datos inicializada en', config.DB_PATH)
