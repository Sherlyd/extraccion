# roles.py
# El motor de reglas: dado un usuario, arma la clausula WHERE que
# determina que filas puede ver. Reemplaza al Section Access de Qlik,
# corriendo sobre la base propia, sin depender de licencias de Qlik.
#
# Sintaxis Postgres: placeholders %s (no ? como en SQLite).

CAMPOS_JERARQUIA = ('centro_distribucion', 'zona', 'sucursal')
CAMPOS_ROL = CAMPOS_JERARQUIA + ('rubro', 'ejecutivo_cuenta')


def clausula_where(usuario, alias_tabla='', filtros_drill=None):
    """Devuelve (sql_where, params) a partir de una fila de la tabla
    usuarios, combinando la restriccion FIJA del rol con lo que el
    usuario eligio explorar via drill-down (filtros_drill).

    Regla de seguridad: si el rol ya fija un campo, filtros_drill para
    ese campo se IGNORA por completo -- nunca se usa para decidir que
    se muestra. Asi, aunque alguien arme una URL a mano con otro valor,
    no puede ver nada fuera de su alcance.
    """
    prefix = f'{alias_tabla}.' if alias_tabla else ''
    filtros_drill = filtros_drill or {}
    condiciones = []
    params = []

    for campo in CAMPOS_ROL:
        valor_rol = usuario[campo] if campo in usuario.keys() else None
        if valor_rol:
            condiciones.append(f'{prefix}{campo} = %s')
            params.append(valor_rol)
        elif campo in filtros_drill and filtros_drill[campo]:
            condiciones.append(f'{prefix}{campo} = %s')
            params.append(filtros_drill[campo])

    if not condiciones:
        return '1=1', []
    return ' AND '.join(condiciones), params


def niveles_navegables(usuario):
    """Campos de jerarquia que el rol NO fija -- en que niveles el
    usuario puede hacer drill-down."""
    return [c for c in CAMPOS_JERARQUIA if not usuario[c]]


def usuarios_activos(conn, rubro=None):
    """Trae los usuarios activos, opcionalmente filtrados por rubro."""
    cur = conn.cursor()
    if rubro:
        cur.execute(
            'SELECT * FROM usuarios WHERE activo = true AND (rubro = %s OR rubro IS NULL)',
            (rubro,),
        )
    else:
        cur.execute('SELECT * FROM usuarios WHERE activo = true')
    filas = cur.fetchall()
    cur.close()
    return filas
