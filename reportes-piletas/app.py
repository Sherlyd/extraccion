# app.py
# Dashboard web. Usa DOS fuentes de datos segun la pregunta:
#
#   - facturacion_mensual: TODO el historico (2015+), pero solo a nivel
#     centro/zona/rubro/familia4/ejecutivo -- se usa para comparaciones
#     de periodo y el grafico de tendencia multi-año.
#
#   - facturacion_detalle: solo la ventana reciente (VENTANA_DETALLE_DIAS
#     en cargar_datos.py), pero con cliente/articulo/distribuidor -- se
#     usa para tops, la tabla cruda, y el analisis por entidad cuando la
#     entidad es un cliente/articulo/distribuidor puntual (no existen en
#     el agregado mensual, ahi solo se ve la ventana reciente).
#
# Uso: python app.py

from flask import Flask, render_template, redirect, url_for, request, session, send_file
from werkzeug.security import check_password_hash
from db import get_connection
from roles import clausula_where, niveles_navegables, CAMPOS_JERARQUIA
import metricas
from generar_informe import generar_informe_excel
import json
import os

app = Flask(__name__)
app.secret_key = os.environ.get('DASHBOARD_SECRET_KEY', 'clave-de-desarrollo-cambiar-en-produccion')

UMBRAL_ALERTA = 0.15
FILAS_POR_PAGINA = 50

# Campos "tocables" para el analisis generico por entidad. Los que
# tambien existen en facturacion_mensual permiten ver la tendencia
# COMPLETA desde 2015; los que no (cliente/articulo/distribuidor/tipo)
# solo muestran la ventana reciente, porque esa granularidad no se
# conserva en el agregado (por diseño, para que siga siendo liviano).
CAMPOS_ANALIZABLES = {
    'distribuidor_nombre': 'Distribuidor',
    'cliente_final_nombre': 'Cliente Final',
    'articulo': 'Artículo',
    'ejecutivo_cuenta': 'Ejecutivo de Cuenta',
    'centro_distribucion': 'Centro de Distribución',
    'zona': 'Zona',
    'rubro': 'Rubro',
    'familia4': 'Categoría (Familia4)',
    'tipo_comp': 'Tipo de Comprobante',
}
CAMPOS_EN_MENSUAL = {'centro_distribucion', 'zona', 'rubro', 'familia4', 'ejecutivo_cuenta'}


@app.route('/')
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_connection()
        usuario = conn.execute(
            'SELECT * FROM usuarios WHERE lower(email) = %s AND activo = true', (email,)
        ).fetchone()
        conn.close()

        if usuario and check_password_hash(usuario['password_hash'], password):
            session['usuario_id'] = usuario['id']
            return redirect(url_for('dashboard'))

        return render_template('login.html', error='Email o contraseña incorrectos.')

    return render_template('login.html', error=None)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


def _usuario_actual(conn):
    if 'usuario_id' not in session:
        return None
    return conn.execute('SELECT * FROM usuarios WHERE id = %s', (session['usuario_id'],)).fetchone()


def _leer_filtros_drill(usuario):
    return {campo: request.args.get(campo) for campo in CAMPOS_JERARQUIA if request.args.get(campo)}


def _anios_a_comparar(anios_disponibles, seleccionados):
    validos = [a for a in seleccionados if a in anios_disponibles]
    if validos:
        return validos
    return anios_disponibles[-2:] if len(anios_disponibles) >= 2 else anios_disponibles


def _filtrar_por_periodo(filas, anio_filtro, mes_filtro):
    if not anio_filtro:
        return filas
    filas = [f for f in filas if f['fecha'].startswith(str(anio_filtro))]
    if mes_filtro:
        mes_str = f'{int(mes_filtro):02d}'
        filas = [f for f in filas if f['fecha'][5:7] == mes_str]
    return filas


def _mensual_a_filas(rows_mensual):
    """Adapta filas de facturacion_mensual (columnas anio/mes separadas)
    al formato 'fecha' que ya esperan las funciones de metricas.py."""
    return [{
        'fecha': f"{r['anio']:04d}-{r['mes']:02d}-01",
        'importe_neto': float(r['importe_neto'] or 0),
        'cantidad': float(r['cantidad'] or 0),
        'centro_distribucion': r['centro_distribucion'],
        'zona': r['zona'],
        'rubro': r['rubro'],
        'familia4': r['familia4'],
        'ejecutivo_cuenta': r['ejecutivo_cuenta'],
    } for r in rows_mensual]


def _fetch_mensual(conn, where, params):
    rows = conn.execute(f'SELECT * FROM facturacion_mensual WHERE {where}', params).fetchall()
    return _mensual_a_filas(rows)


def _fetch_detalle(conn, where, params):
    return conn.execute(f'SELECT * FROM facturacion_detalle WHERE {where}', params).fetchall()


def _opciones_siguiente_nivel(conn, usuario, filtros_drill, where, params):
    libres = niveles_navegables(usuario)
    siguiente = next((c for c in libres if c not in filtros_drill), None)
    if not siguiente:
        return None, None
    # Los 3 niveles de jerarquia (centro/zona/sucursal) existen en el
    # agregado mensual salvo sucursal -- si hace falta navegar por
    # sucursal (no esta en facturacion_mensual), se consulta el detalle.
    tabla = 'facturacion_mensual' if siguiente != 'sucursal' else 'facturacion_detalle'
    filas = conn.execute(
        f'SELECT DISTINCT {siguiente} as valor FROM {tabla} WHERE {where} AND {siguiente} IS NOT NULL ORDER BY 1',
        params,
    ).fetchall()
    return siguiente, [f['valor'] for f in filas]


def _calcular_datos_dashboard(usuario, conn, filtros_drill, anio_filtro=None, mes_filtro=None, anios_comparar_sel=None):
    where, params = clausula_where(usuario, filtros_drill=filtros_drill)

    filas_mensual = _fetch_mensual(conn, where, params)
    filas_detalle = _fetch_detalle(conn, where, params)
    filas_cartera = conn.execute(f'SELECT * FROM cartera_pendiente WHERE {where}', params).fetchall()

    filas_detalle_periodo = _filtrar_por_periodo(filas_detalle, anio_filtro, mes_filtro)

    # Comparaciones y tendencia: SIEMPRE desde el agregado mensual, que
    # tiene el historico completo (el detalle solo cubre la ventana
    # reciente y daria comparaciones incompletas contra años previos).
    comparacion = metricas.comparacion_periodo(filas_mensual, anio_filtro, mes_filtro)
    top_articulos = metricas.top_articulos_detalle(filas_detalle_periodo, n=8)
    top_distribuidores = metricas.top_n(filas_detalle_periodo, 'distribuidor_nombre', n=5)
    cartera = metricas.cartera_pendiente_resumen(filas_cartera)
    alertas = metricas.detectar_alertas(comparacion, UMBRAL_ALERTA)

    anios_disponibles = metricas.anios_disponibles(filas_mensual)
    anios_comparar = _anios_a_comparar(anios_disponibles, anios_comparar_sel or [])
    multianio_completo = metricas.facturacion_multianio_mensual(filas_mensual)
    multianio = {a: v for a, v in multianio_completo.items() if a in anios_comparar}

    siguiente_nivel, opciones_nivel = _opciones_siguiente_nivel(conn, usuario, filtros_drill, where, params)

    return {
        'comparacion': comparacion, 'top_articulos': top_articulos, 'top_distribuidores': top_distribuidores,
        'cartera': cartera, 'alertas': alertas, 'multianio': multianio, 'anios_disponibles': anios_disponibles,
        'anios_comparar': anios_comparar, 'siguiente_nivel': siguiente_nivel, 'opciones_nivel': opciones_nivel,
    }


@app.route('/dashboard')
def dashboard():
    conn = get_connection()
    usuario = _usuario_actual(conn)
    if not usuario:
        conn.close()
        return redirect(url_for('login'))

    filtros_drill = _leer_filtros_drill(usuario)
    anio_filtro = request.args.get('anio_filtro') or None
    mes_filtro = request.args.get('mes_filtro') or None
    anios_comparar_sel = request.args.getlist('anios_comparar')

    datos = _calcular_datos_dashboard(usuario, conn, filtros_drill, anio_filtro, mes_filtro, anios_comparar_sel)
    conn.close()

    chart_multianio = {
        'meses': list(metricas.MESES_NOMBRE.values()),
        'series': [{'anio': anio, 'valores': valores} for anio, valores in datos['multianio'].items()],
    }

    migas = []
    for campo in CAMPOS_JERARQUIA:
        if usuario[campo]:
            migas.append({'campo': campo, 'valor': usuario[campo], 'fijo': True})
        elif campo in filtros_drill:
            migas.append({'campo': campo, 'valor': filtros_drill[campo], 'fijo': False})

    query_periodo = {}
    if anio_filtro:
        query_periodo['anio_filtro'] = anio_filtro
    if mes_filtro:
        query_periodo['mes_filtro'] = mes_filtro
    if anios_comparar_sel:
        query_periodo['anios_comparar'] = anios_comparar_sel

    query_completa = {**filtros_drill, **query_periodo}
    descarga_href = url_for('descargar_informe', **query_completa)
    limpiar_periodo_href = url_for('dashboard', **filtros_drill)

    opciones_nivel_links = None
    if datos['siguiente_nivel'] and datos['opciones_nivel']:
        opciones_nivel_links = [
            (opcion, url_for('dashboard', **{**query_completa, datos['siguiente_nivel']: opcion}))
            for opcion in datos['opciones_nivel']
        ]

    return render_template(
        'dashboard.html', usuario=usuario, migas=migas, siguiente_nivel=datos['siguiente_nivel'],
        opciones_nivel_links=opciones_nivel_links, comparacion=datos['comparacion'],
        top_articulos=datos['top_articulos'], top_distribuidores=datos['top_distribuidores'],
        cartera=datos['cartera'], alertas=datos['alertas'], umbral_alerta=UMBRAL_ALERTA,
        chart_multianio_json=json.dumps(chart_multianio), anios_disponibles=datos['anios_disponibles'],
        anios_comparar=datos['anios_comparar'], anio_filtro=anio_filtro, mes_filtro=mes_filtro,
        meses_nombre=metricas.MESES_NOMBRE, descarga_href=descarga_href,
        limpiar_periodo_href=limpiar_periodo_href, filtros_drill=filtros_drill,
    )


@app.route('/dashboard/descargar')
def descargar_informe():
    conn = get_connection()
    usuario = _usuario_actual(conn)
    if not usuario:
        conn.close()
        return redirect(url_for('login'))

    filtros_drill = _leer_filtros_drill(usuario)
    anio_filtro = request.args.get('anio_filtro') or None
    mes_filtro = request.args.get('mes_filtro') or None
    datos = _calcular_datos_dashboard(usuario, conn, filtros_drill, anio_filtro, mes_filtro)
    conn.close()

    buffer = generar_informe_excel(
        usuario, datos['comparacion'], datos['top_articulos'], datos['top_distribuidores'],
        datos['cartera'], datos['alertas'], UMBRAL_ALERTA,
    )
    nombre_archivo = f"informe_piletas_{usuario['nombre'].replace(' ', '_')}.xlsx"
    return send_file(buffer, as_attachment=True, download_name=nombre_archivo,
                      mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/dashboard/ejecutivos')
def ejecutivos():
    conn = get_connection()
    usuario = _usuario_actual(conn)
    if not usuario:
        conn.close()
        return redirect(url_for('login'))

    filtros_drill = _leer_filtros_drill(usuario)
    anio_filtro = request.args.get('anio_filtro') or None
    mes_filtro = request.args.get('mes_filtro') or None
    anios_comparar_sel = request.args.getlist('anios_comparar')
    unidad = request.args.get('unidad', 'pesos')
    campo_valor = 'importe_neto' if unidad == 'pesos' else 'cantidad'
    ejecutivo_sel = request.args.get('ejecutivo') or None

    where, params = clausula_where(usuario, filtros_drill=filtros_drill)
    filas_mensual = _fetch_mensual(conn, where, params)
    filas_detalle = _fetch_detalle(conn, where, params)
    conn.close()

    # Ranking y evolucion del ejecutivo: desde el agregado mensual --
    # ejecutivo_cuenta SI esta en facturacion_mensual, asi que esto
    # cubre el historico completo, no solo la ventana reciente.
    filas_mensual_periodo = _filtrar_por_periodo(filas_mensual, anio_filtro, mes_filtro)
    ranking = metricas.top_n(filas_mensual_periodo, 'ejecutivo_cuenta', campo_valor=campo_valor, n=20)
    anios_disp = metricas.anios_disponibles(filas_mensual)
    anios_comparar = _anios_a_comparar(anios_disp, anios_comparar_sel)

    detalle = None
    if ejecutivo_sel:
        # La cartera de CLIENTES si necesita el detalle (cliente no
        # existe en el agregado mensual) -- por eso esto queda acotado
        # a la ventana reciente, a diferencia del ranking de arriba.
        filas_detalle_periodo = _filtrar_por_periodo(filas_detalle, anio_filtro, mes_filtro)
        clientes, ubicaciones = metricas.clientes_de_ejecutivo(filas_detalle_periodo, ejecutivo_sel, campo_valor)

        multianio_completo = metricas.facturacion_multianio_mensual(
            [f for f in filas_mensual if f['ejecutivo_cuenta'] == ejecutivo_sel], campo_valor,
        )
        multianio = {a: v for a, v in multianio_completo.items() if a in anios_comparar}
        detalle = {
            'nombre': ejecutivo_sel, 'ubicaciones': ubicaciones, 'clientes': clientes,
            'chart_json': json.dumps({
                'meses': list(metricas.MESES_NOMBRE.values()),
                'series': [{'anio': a, 'valores': v} for a, v in multianio.items()],
            }),
        }

    query_periodo = {}
    if anio_filtro:
        query_periodo['anio_filtro'] = anio_filtro
    if mes_filtro:
        query_periodo['mes_filtro'] = mes_filtro
    if anios_comparar_sel:
        query_periodo['anios_comparar'] = anios_comparar_sel
    query_base = {**filtros_drill, **query_periodo, 'unidad': unidad}

    ranking_links = [(nombre, valor, url_for('ejecutivos', **{**query_base, 'ejecutivo': nombre}))
                      for nombre, valor in ranking]

    return render_template(
        'ejecutivos.html', usuario=usuario, unidad=unidad, ranking_links=ranking_links, detalle=detalle,
        anios_disponibles=anios_disp, anios_comparar=anios_comparar, anio_filtro=anio_filtro,
        mes_filtro=mes_filtro, meses_nombre=metricas.MESES_NOMBRE, query_base=query_base,
        toggle_unidad_href=url_for('ejecutivos', **{**query_base, 'unidad': 'ctd' if unidad == 'pesos' else 'pesos'}),
    )


@app.route('/dashboard/tabla')
def tabla_datos():
    conn = get_connection()
    usuario = _usuario_actual(conn)
    if not usuario:
        conn.close()
        return redirect(url_for('login'))

    filtros_drill = _leer_filtros_drill(usuario)
    anio_filtro = request.args.get('anio_filtro') or None
    mes_filtro = request.args.get('mes_filtro') or None
    pagina = max(1, int(request.args.get('pagina', 1)))

    where, params = clausula_where(usuario, filtros_drill=filtros_drill)
    filas_detalle = _fetch_detalle(conn, where, params)
    conn.close()

    filas_periodo = _filtrar_por_periodo(
        [{**f, 'fecha': f['fecha'].isoformat()} for f in filas_detalle], anio_filtro, mes_filtro,
    )
    filas_periodo = sorted(filas_periodo, key=lambda f: f['fecha'], reverse=True)

    total_filas = len(filas_periodo)
    total_paginas = max(1, (total_filas + FILAS_POR_PAGINA - 1) // FILAS_POR_PAGINA)
    pagina = min(pagina, total_paginas)
    inicio = (pagina - 1) * FILAS_POR_PAGINA
    filas_pagina = filas_periodo[inicio:inicio + FILAS_POR_PAGINA]

    query_periodo = {}
    if anio_filtro:
        query_periodo['anio_filtro'] = anio_filtro
    if mes_filtro:
        query_periodo['mes_filtro'] = mes_filtro
    query_base = {**filtros_drill, **query_periodo}

    def href_analisis(campo, valor):
        return url_for('analisis_entidad', campo=campo, valor=valor, **query_base)

    return render_template(
        'tabla_datos.html', usuario=usuario, filas=filas_pagina, campos_analizables=CAMPOS_ANALIZABLES,
        href_analisis=href_analisis, pagina=pagina, total_paginas=total_paginas, total_filas=total_filas,
        query_base=query_base, anios_disponibles=metricas.anios_disponibles(filas_periodo),
        anio_filtro=anio_filtro, mes_filtro=mes_filtro, meses_nombre=metricas.MESES_NOMBRE,
    )


@app.route('/dashboard/analisis')
def analisis_entidad():
    campo = request.args.get('campo')
    valor = request.args.get('valor')
    if campo not in CAMPOS_ANALIZABLES or not valor:
        return redirect(url_for('dashboard'))

    conn = get_connection()
    usuario = _usuario_actual(conn)
    if not usuario:
        conn.close()
        return redirect(url_for('login'))

    filtros_drill = _leer_filtros_drill(usuario)
    anio_filtro = request.args.get('anio_filtro') or None
    mes_filtro = request.args.get('mes_filtro') or None
    anios_comparar_sel = request.args.getlist('anios_comparar')

    where, params = clausula_where(usuario, filtros_drill=filtros_drill)
    filas_detalle = [{**f, 'fecha': f['fecha'].isoformat()} for f in _fetch_detalle(conn, where, params)]

    filas_entidad_detalle = [f for f in filas_detalle if (f[campo] or '(sin dato)') == valor]
    filas_entidad_periodo = _filtrar_por_periodo(filas_entidad_detalle, anio_filtro, mes_filtro)

    total_importe = sum(f['importe_neto'] or 0 for f in filas_entidad_periodo)
    total_cantidad = sum(f['cantidad'] or 0 for f in filas_entidad_periodo)

    aviso_ventana = False
    if campo in CAMPOS_EN_MENSUAL:
        # Esta dimension SI existe en el agregado -- se puede mostrar
        # la tendencia completa desde 2015.
        filas_mensual = _mensual_a_filas(
            conn.execute(f'SELECT * FROM facturacion_mensual WHERE {where}', params).fetchall()
        )
        filas_entidad_mensual = [f for f in filas_mensual if (f[campo] or '(sin dato)') == valor]
        anios_disp = metricas.anios_disponibles(filas_entidad_mensual)
        anios_comparar = _anios_a_comparar(anios_disp, anios_comparar_sel)
        multianio_completo = metricas.facturacion_multianio_mensual(filas_entidad_mensual)
    else:
        # Solo existe a nivel detalle -- la tendencia queda acotada a
        # la ventana reciente, se lo advertimos al usuario en pantalla.
        aviso_ventana = True
        anios_disp = metricas.anios_disponibles(filas_entidad_detalle)
        anios_comparar = _anios_a_comparar(anios_disp, anios_comparar_sel)
        multianio_completo = metricas.facturacion_multianio_mensual(filas_entidad_detalle)

    multianio = {a: v for a, v in multianio_completo.items() if a in anios_comparar}

    desgloses = {}
    for otro_campo, etiqueta in CAMPOS_ANALIZABLES.items():
        if otro_campo == campo:
            continue
        ranking = metricas.top_n(filas_entidad_periodo, otro_campo, n=5)
        if ranking:
            desgloses[etiqueta] = {'campo': otro_campo, 'ranking': ranking}

    conn.close()

    query_periodo = {}
    if anio_filtro:
        query_periodo['anio_filtro'] = anio_filtro
    if mes_filtro:
        query_periodo['mes_filtro'] = mes_filtro
    if anios_comparar_sel:
        query_periodo['anios_comparar'] = anios_comparar_sel
    query_base = {**filtros_drill, **query_periodo}

    def href_analisis(otro_campo, otro_valor):
        return url_for('analisis_entidad', campo=otro_campo, valor=otro_valor, **query_base)

    return render_template(
        'analisis_entidad.html', usuario=usuario, etiqueta_campo=CAMPOS_ANALIZABLES[campo], valor=valor,
        total_importe=total_importe, total_cantidad=total_cantidad, desgloses=desgloses,
        href_analisis=href_analisis, aviso_ventana=aviso_ventana,
        chart_json=json.dumps({
            'meses': list(metricas.MESES_NOMBRE.values()),
            'series': [{'anio': a, 'valores': v} for a, v in multianio.items()],
        }),
        anios_disponibles=anios_disp, anios_comparar=anios_comparar, anio_filtro=anio_filtro,
        mes_filtro=mes_filtro, meses_nombre=metricas.MESES_NOMBRE, query_base=query_base,
    )


@app.route('/dashboard/simple')
def dashboard_simple():
    conn = get_connection()
    usuario = _usuario_actual(conn)
    if not usuario:
        conn.close()
        return redirect(url_for('login'))

    filtros_drill = _leer_filtros_drill(usuario)
    where, params = clausula_where(usuario, filtros_drill=filtros_drill)
    filas_mensual = _fetch_mensual(conn, where, params)
    filas_detalle = _fetch_detalle(conn, where, params)
    filas_cartera = conn.execute(f'SELECT * FROM cartera_pendiente WHERE {where}', params).fetchall()
    conn.close()

    comparacion = metricas.comparacion_periodo(filas_mensual)
    alertas = metricas.detectar_alertas(comparacion, UMBRAL_ALERTA)
    cartera = metricas.cartera_pendiente_resumen(filas_cartera)

    anios = metricas.anios_disponibles(filas_mensual)
    anio_actual = anios[-1] if anios else None
    filas_anio_actual = [f for f in filas_mensual if f['fecha'].startswith(str(anio_actual))] if anio_actual else []
    por_mes_actual = metricas.facturacion_por_mes(filas_anio_actual)
    valores_12_meses = [por_mes_actual.get(f'{anio_actual}-{m:02d}', 0) for m in range(1, 13)]

    top_articulos = metricas.top_n(
        [{**f, 'fecha': f['fecha'].isoformat()} for f in filas_detalle], 'articulo', n=5,
    )
    top_distribuidores = metricas.top_n(
        [{**f, 'fecha': f['fecha'].isoformat()} for f in filas_detalle], 'distribuidor_nombre', n=5,
    )

    estado = 'ok'
    if comparacion and abs(comparacion['variacion_pct']) >= UMBRAL_ALERTA:
        estado = 'alerta'

    return render_template(
        'dashboard_simple.html', usuario=usuario, comparacion=comparacion, alertas=alertas, cartera=cartera,
        estado=estado, anio_actual=anio_actual,
        chart_mensual_json=json.dumps({'meses': list(metricas.MESES_NOMBRE.values()), 'valores': valores_12_meses}),
        chart_articulos_json=json.dumps({'nombres': [n for n, v in top_articulos], 'valores': [v for n, v in top_articulos]}),
        chart_distribuidores_json=json.dumps({'nombres': [n for n, v in top_distribuidores], 'valores': [v for n, v in top_distribuidores]}),
    )


if __name__ == '__main__':
    app.run(debug=False, port=5000)
