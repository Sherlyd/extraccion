# gestionar_usuarios.py
# Crear y administrar usuarios del dashboard. La contraseña nunca se
# guarda en texto plano -- se guarda un hash (werkzeug, la misma
# libreria que ya usa Flask).
#
# Uso:
#   python gestionar_usuarios.py crear "Nombre Apellido" email@empresa.com contraseña rol [sucursal] [rubro] [ejecutivo_cuenta]
#   python gestionar_usuarios.py listar
#   python gestionar_usuarios.py cambiar-clave email@empresa.com nueva_contraseña
#   python gestionar_usuarios.py desactivar email@empresa.com
#
# Ejemplos:
#   python gestionar_usuarios.py crear "Juan Perez" juan.perez@johnsonacero.com "unaClaveSegura123" gerente_general
#   python gestionar_usuarios.py crear "Maria Lopez" maria.lopez@johnsonacero.com "otraClave456" gerente_sucursal Parana "VENTA PILETAS"

import sys
from werkzeug.security import generate_password_hash
from db import get_connection, init_db


def crear(nombre, email, password, rol, sucursal=None, rubro=None, ejecutivo_cuenta=None):
    init_db()
    conn = get_connection()
    try:
        conn.execute('''
            INSERT INTO usuarios (nombre, email, password_hash, rol, sucursal, rubro, ejecutivo_cuenta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, email, generate_password_hash(password), rol, sucursal, rubro, ejecutivo_cuenta))
        conn.commit()
        print(f'Usuario creado: {nombre} <{email}> — rol: {rol}')
    except Exception as e:
        print(f'Error al crear usuario: {e}')
    finally:
        conn.close()


def listar():
    conn = get_connection()
    usuarios = conn.execute('SELECT * FROM usuarios ORDER BY rol, nombre').fetchall()
    print(f'\n{len(usuarios)} usuarios:\n')
    for u in usuarios:
        estado = 'activo' if u['activo'] else 'INACTIVO'
        print(f"- {u['nombre']} <{u['email']}> — {u['rol']} — sucursal={u['sucursal']} rubro={u['rubro']} ({estado})")
    conn.close()


def cambiar_clave(email, password):
    conn = get_connection()
    cur = conn.execute('UPDATE usuarios SET password_hash = ? WHERE email = ?',
                        (generate_password_hash(password), email))
    conn.commit()
    print('Contraseña actualizada.' if cur.rowcount else f'No se encontro un usuario con email {email}')
    conn.close()


def desactivar(email):
    conn = get_connection()
    cur = conn.execute('UPDATE usuarios SET activo = 0 WHERE email = ?', (email,))
    conn.commit()
    print('Usuario desactivado.' if cur.rowcount else f'No se encontro un usuario con email {email}')
    conn.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    comando = sys.argv[1]

    if comando == 'crear':
        if len(sys.argv) < 6:
            print('Uso: python gestionar_usuarios.py crear "Nombre" email contraseña rol [sucursal] [rubro] [ejecutivo_cuenta]')
            sys.exit(1)
        nombre, email, password, rol = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
        sucursal = sys.argv[6] if len(sys.argv) > 6 else None
        rubro = sys.argv[7] if len(sys.argv) > 7 else None
        ejecutivo = sys.argv[8] if len(sys.argv) > 8 else None
        crear(nombre, email, password, rol, sucursal, rubro, ejecutivo)

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
