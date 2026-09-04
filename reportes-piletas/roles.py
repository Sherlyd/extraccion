# roles.py
# El motor de reglas: dado un usuario, arma la clausula WHERE que
# determina que filas puede ver. Esto es lo que reemplaza al Section
# Access de Qlik, corriendo sobre tu propia base, sin depender de
# licencias ni usuarios de Qlik.
#
# La regla base es simple:
#   - Si el campo del usuario es NULL -> sin restriccion fija en esa
#     columna (puede ver todo, O explorar con drill-down si el
#     dashboard se lo ofrece).
#   - Si tiene un valor -> SIEMPRE esa fila coincide en esa columna,
#     sin excepcion -- ni el drill-down del dashboard puede pisar esto.
#
# Jerarquia geografica: centro_distribucion > zona > sucursal. Un
# Gerente General tiene los 3 en NULL (ve todo, puede navegar por
# cualquier nivel). Un gerente de un centro tiene centro_distribucion
# fijo pero zona/sucursal en NULL (puede navegar dentro de su centro).
# Un gerente de sucursal tiene los 3 fijos (no navega nada, ve lo suyo).

CAMPOS_JERARQUIA = ('centro_distribucion', 'zona', 'sucursal')
CAMPOS_ROL = CAMPOS_JERARQUIA + ('rubro', 'ejecutivo_cuenta')


def clausula_where(usuario, alias_tabla='', filtros_drill=None):
    """Devuelve (sql_where, params) a partir de una fila de la tabla
    usuarios, combinando la restriccion FIJA del rol con lo que el
    usuario eligio explorar via drill-down (filtros_drill).

    Regla de seguridad: si el rol ya fija un campo, el valor de
    filtros_drill para ese campo se IGNORA por completo -- nunca se usa
    para decidir que se muestra. Asi, aunque alguien arme una URL a mano
    con otro valor, no puede ver nada fuera de su alcance.
    """
    prefix = f'{alias_tabla}.' if alias_tabla else ''
    filtros_drill = filtros_drill or {}
    condiciones = []
    params = []

    for campo in CAMPOS_ROL:
        valor_rol = usuario[campo] if campo in usuario.keys() else None
        if valor_rol:
            # El rol manda, sin excepcion.
            condiciones.append(f'{prefix}{campo} = ?')
            params.append(valor_rol)
        elif campo in filtros_drill and filtros_drill[campo]:
            # Sin restriccion de rol en este campo: se puede explorar.
            condiciones.append(f'{prefix}{campo} = ?')
            params.append(filtros_drill[campo])

    if not condiciones:
        return '1=1', []
    return ' AND '.join(condiciones), params


def niveles_navegables(usuario):
    """Devuelve la lista de campos de jerarquia que el rol NO fija --
    es decir, en que niveles el usuario puede hacer drill-down. Se usa
    para que el dashboard sepa que enlaces de navegacion mostrar."""
    return [c for c in CAMPOS_JERARQUIA if not usuario[c]]


def datos_visibles(conn, usuario, tabla, columnas='*', filtros_drill=None):
    """Devuelve las filas de 'tabla' que el usuario puede ver, ya
    filtradas segun su alcance + lo que eligio explorar."""
    where, params = clausula_where(usuario, filtros_drill=filtros_drill)
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
