# roles.py
# El motor de reglas: dado un usuario, arma la clausula WHERE que
# determina que filas puede ver. Esto es lo que reemplaza al Section
# Access de Qlik, pero corriendo sobre tu propia base, sin depender de
# licencias ni usuarios de Qlik.
#
# La regla es simple y generaliza los 3 roles que describiste:
#   - Si el campo del usuario es NULL -> sin restriccion en esa columna.
#   - Si tiene un valor -> solo esa fila coincide en esa columna.
# Un gerente general tiene sucursal=NULL, rubro=NULL, ejecutivo=NULL.
# Un gerente de sucursal de Piletas tiene sucursal='X', rubro='PILETAS',
# ejecutivo=NULL. Un vendedor tiene ademas ejecutivo_cuenta='Su Nombre'.
# Agregar un rol nuevo el dia de mañana es solo agregar una fila en
# la tabla usuarios, no tocar codigo.

def clausula_where(usuario, alias_tabla=''):
    """Devuelve (sql_where, params) a partir de una fila de la tabla
    usuarios (sqlite3.Row o dict)."""
    prefix = f'{alias_tabla}.' if alias_tabla else ''
    condiciones = []
    params = []

    for campo in ('sucursal', 'rubro', 'ejecutivo_cuenta'):
        valor = usuario[campo] if usuario[campo] is not None else None
        if valor:
            condiciones.append(f'{prefix}{campo} = ?')
            params.append(valor)

    if not condiciones:
        return '1=1', []
    return ' AND '.join(condiciones), params


def datos_visibles(conn, usuario, tabla, columnas='*'):
    """Devuelve las filas de 'tabla' que el usuario puede ver, ya
    filtradas segun su alcance."""
    where, params = clausula_where(usuario)
    sql = f'SELECT {columnas} FROM {tabla} WHERE {where}'
    return conn.execute(sql, params).fetchall()


def usuarios_activos(conn, rubro=None):
    """Trae los usuarios activos, opcionalmente filtrados por rubro
    (para correr el mail diario solo de un rubro a la vez, como Piletas)."""
    if rubro:
        return conn.execute(
            'SELECT * FROM usuarios WHERE activo = 1 AND (rubro = ? OR rubro IS NULL)',
            (rubro,),
        ).fetchall()
    return conn.execute('SELECT * FROM usuarios WHERE activo = 1').fetchall()
