# app.py
# Dashboard web con navegacion "macro a micro":
#   - Geografia: Centro Distribucion -> Zona (drill-down por clic,
#     respetando siempre el limite que impone el rol).
#   - Tiempo: linea de tiempo con TODOS los años superpuestos, mas
#     filtros opcionales de año/mes para acotar tablas y comparaciones
#     a un periodo puntual.
#
# Uso: python app.py
# Despues abrir http://localhost:5000 en el navegador.

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

# Umbral de alerta: si la facturacion se desvia mas de esto (en
# cualquier direccion) respecto al periodo de comparacion, se marca
# como alerta. Se muestra siempre en el dashboard, no solo cuando salta.
UMBRAL_ALERTA = 0.15


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
            'SELECT * FROM usuarios WHERE lower(email) = ? AND activo = 1', (email,)
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
    return conn.execute('SELECT * FROM usuarios WHERE id = ?', (session['usuario_id'],)).fetchone()


def _leer_filtros_drill(usuario):
    """Lee de la URL (?centro_distribucion=...&zona=...) solo los
    niveles que el rol de este usuario permite explorar."""
    return {campo: request.args.get(campo) for campo in CAMPOS_JERARQUIA if request.args.get(campo)}


def _opciones_siguiente_nivel(conn, usuario, filtros_drill, where, params):
    libres = niveles_navegables(usuario)
    siguiente = next((c for c in libres if c not in filtros_drill), None)
    if not siguiente:
        return None, None

    filas = conn.execute(
        f'SELECT DISTINCT {siguiente} as valor FROM facturacion WHERE {where} AND {siguiente} IS NOT NULL ORDER BY 1',
        params,
    ).fetchall()
    return siguiente, [f['valor'] for f in filas]


def _filtrar_por_periodo(filas_facturacion, anio_filtro, mes_filtro):
    """Acota una lista de filas a un año (y opcionalmente un mes)
    puntual. Se usa para las tablas (top articulos/distribuidores),
    NO para el grafico multi-año (que siempre muestra todos los años
    disponibles para poder compararlos) ni para comparacion_periodo
    (que necesita ver los demas meses para calcular el promedio)."""
    if not anio_filtro:
        return filas_facturacion
    filas = [f for f in filas_facturacion if f['fecha'].startswith(str(anio_filtro))]
    if mes_filtro:
        mes_str = f'{int(mes_filtro):02d}'
        filas = [f for f in filas if f['fecha'][5:7] == mes_str]
    return filas


def _calcular_datos_dashboard(usuario, conn, filtros_drill, anio_filtro=None, mes_filtro=None):
    where, params = clausula_where(usuario, filtros_drill=filtros_drill)

    filas_fact = conn.execute(f'SELECT * FROM facturacion WHERE {where}', params).fetchall()
    filas_cartera = conn.execute(f'SELECT * FROM cartera_pendiente WHERE {where}', params).fetchall()

    filas_fact_periodo = _filtrar_por_periodo(filas_fact, anio_filtro, mes_filtro)

    comparacion = metricas.comparacion_periodo(filas_fact, anio_filtro, mes_filtro)
    top_articulos = metricas.top_articulos_detalle(filas_fact_periodo, n=8)
    top_distribuidores = metricas.top_n(filas_fact_periodo, 'distribuidor_nombre', n=5)
    cartera = metricas.cartera_pendiente_resumen(filas_cartera)
    alertas = metricas.detectar_alertas(comparacion, UMBRAL_ALERTA)

    multianio = metricas.facturacion_multianio_mensual(filas_fact)
    anios_disponibles = metricas.anios_disponibles(filas_fact)

    siguiente_nivel, opciones_nivel = _opciones_siguiente_nivel(conn, usuario, filtros_drill, where, params)

    return {
        'comparacion': comparacion,
        'top_articulos': top_articulos,
        'top_distribuidores': top_distribuidores,
        'cartera': cartera,
        'alertas': alertas,
        'multianio': multianio,
        'anios_disponibles': anios_disponibles,
        'siguiente_nivel': siguiente_nivel,
        'opciones_nivel': opciones_nivel,
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

    datos = _calcular_datos_dashboard(usuario, conn, filtros_drill, anio_filtro, mes_filtro)
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

    # Armamos ac\u00e1, en Python, todos los links que el template necesita --
    # evita mezclar **dict con argumentos con nombre dentro de Jinja
    # (no es una sintaxis valida ahi, aunque si lo sea en Python).
    query_periodo = {}
    if anio_filtro:
        query_periodo['anio_filtro'] = anio_filtro
    if mes_filtro:
        query_periodo['mes_filtro'] = mes_filtro

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
        'dashboard.html',
        usuario=usuario,
        migas=migas,
        siguiente_nivel=datos['siguiente_nivel'],
        opciones_nivel_links=opciones_nivel_links,
        comparacion=datos['comparacion'],
        top_articulos=datos['top_articulos'],
        top_distribuidores=datos['top_distribuidores'],
        cartera=datos['cartera'],
        alertas=datos['alertas'],
        umbral_alerta=UMBRAL_ALERTA,
        chart_multianio_json=json.dumps(chart_multianio),
        anios_disponibles=datos['anios_disponibles'],
        anio_filtro=anio_filtro,
        mes_filtro=mes_filtro,
        meses_nombre=metricas.MESES_NOMBRE,
        descarga_href=descarga_href,
        limpiar_periodo_href=limpiar_periodo_href,
        filtros_drill=filtros_drill,
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
        usuario, datos['comparacion'], datos['top_articulos'],
        datos['top_distribuidores'], datos['cartera'], datos['alertas'], UMBRAL_ALERTA,
    )

    nombre_archivo = f"informe_piletas_{usuario['nombre'].replace(' ', '_')}.xlsx"
    return send_file(
        buffer, as_attachment=True, download_name=nombre_archivo,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


if __name__ == '__main__':
    app.run(debug=False, port=5000)