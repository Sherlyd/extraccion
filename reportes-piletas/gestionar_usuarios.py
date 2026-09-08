# gestionar_usuarios.py
# Crear y administrar usuarios (Postgres). La contraseña nunca se
# guarda en texto plano.
#
# Uso:
#   python gestionar_usuarios.py crear "Nombre" email contraseña rol [centro] [zona] [sucursal] [rubro] [ejecutivo_cuenta]
#   python gestionar_usuarios.py listar
#   python gestionar_usuarios.py cambiar-clave email nueva_contraseña
#   python gestionar_usuarios.py desactivar email

import sys
from werkzeug.security import generate_password_hash
from db import get_connection, init_db


def crear(nombre, email, password, rol, centro=None, zona=None, sucursal=None, rubro=None, ejecutivo=None):
    init_db()
    conn = get_connection()
    try:
        conn.execute('''
            INSERT INTO usuarios (nombre, email, password_hash, rol, centro_distribucion, zona,
                                   sucursal, rubro, ejecutivo_cuenta)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (nombre, email, generate_password_hash(password), rol, centro, zona, sucursal, rubro, ejecutivo))
        conn.commit()
        print(f'Usuario creado: {nombre} <{email}> — rol: {rol}')
    except Exception as e:
        conn.rollback()
        print(f'Error al crear usuario: {e}')
    finally:
        conn.close()


def listar():
    conn = get_connection()
    usuarios = conn.execute('SELECT * FROM usuarios ORDER BY rol, nombre').fetchall()
    print(f'\n{len(usuarios)} usuarios:\n')
    for u in usuarios:
        estado = 'activo' if u['activo'] else 'INACTIVO'
        print(f"- {u['nombre']} <{u['email']}> — {u['rol']} — centro={u['centro_distribucion']} "
              f"zona={u['zona']} sucursal={u['sucursal']} rubro={u['rubro']} ({estado})")
    conn.close()


def cambiar_clave(email, password):
    conn = get_connection()
    cur = conn.execute('UPDATE usuarios SET password_hash = %s WHERE email = %s',
                        (generate_password_hash(password), email))
    afectadas = cur.rowcount
    conn.commit()
    print('Contraseña actualizada.' if afectadas else f'No se encontro un usuario con email {email}')
    conn.close()


def desactivar(email):
    conn = get_connection()
    cur = conn.execute('UPDATE usuarios SET activo = false WHERE email = %s', (email,))
    afectadas = cur.rowcount
    conn.commit()
    print('Usuario desactivado.' if afectadas else f'No se encontro un usuario con email {email}')
    conn.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    comando = sys.argv[1]

    if comando == 'crear':
        if len(sys.argv) < 6:
            print('Uso: python gestionar_usuarios.py crear "Nombre" email contraseña rol [centro] [zona] [sucursal] [rubro] [ejecutivo]')
            sys.exit(1)
        nombre, email, password, rol = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
        resto = sys.argv[6:11] + [None] * 5
        crear(nombre, email, password, rol, *resto[:5])

    elif comando == 'listar':
        listar()

    elif comando == 'cambiar-clave':
        if len(sys.argv) < 4:
            print('Uso: python gestionar_usuarios.py cambiar-clave email nueva_contraseña')
            sys.exit(1)
        cambiar_clave(sys.argv[2], sys.argv[3])

    elif comando == 'desactivar':
        if len(sys.argv) < 3:
            print('Uso: python gestionar_usuarios.py desactivar email')
            sys.exit(1)
        desactivar(sys.argv[2])

    else:
        print(f'Comando desconocido: {comando}')
        print(__doc__)
