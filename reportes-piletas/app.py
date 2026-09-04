# app.py
# Dashboard web con navegacion "macro a micro":
#   - Geografia: Centro Distribucion -> Zona -> Sucursal (drill-down
#     por clic, respetando siempre el limite que impone el rol).
#   - Tiempo: historico anual -> un año puntual vs. el año anterior.
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
    """Lee de la URL (?centro=...&zona=...&sucursal=...) solo los
    niveles que el rol de este usuario permite explorar. Si el rol ya
    fija un nivel, cualquier valor que venga en la URL para ese nivel
    se ignora -- ver roles.clausula_where."""
    return {campo: request.args.get(campo) for campo in CAMPOS_JERARQUIA if request.args.get(campo)}


def _opciones_siguiente_nivel(conn, usuario, filtros_drill, where, params):
    """Para el nivel de jerarquia que sigue abierto (el primero que el
    rol no fija y que el usuario todavia no eligio), arma la lista de
    valores distintos disponibles para navegar -- son los links de
    drill-down que se muestran en el dashboard."""
    libres = niveles_navegables(usuario)
    siguiente = next((c for c in libres if c not in filtros_drill), None)
    if not siguiente:
        return None, None

    filas = conn.execute(
        f'SELECT DISTINCT {siguiente} as valor FROM facturacion WHERE {where} AND {siguiente} IS NOT NULL ORDER BY 1',
        params,
    ).fetchall()
    return siguiente, [f['valor'] for f in filas]


def _calcular_datos_dashboard(usuario, conn, filtros_drill, anio_seleccionado=None):
    where, params = clausula_where(usuario, filtros_drill=filtros_drill)

    filas_fact = conn.execute(f'SELECT * FROM facturacion WHERE {where}', params).fetchall()
    filas_cartera = conn.execute(f'SELECT * FROM cartera_pendiente WHERE {where}', params).fetchall()

    por_mes = metricas.facturacion_por_mes(filas_fact)
    comparacion = metricas.comparacion_mes_actual_vs_promedio_anual(por_mes)
    top_articulos = metricas.top_n(filas_fact, 'articulo', n=5)
    top_distribuidores = metricas.top_n(filas_fact, 'distribuidor_nombre', n=5)
    cartera = metricas.cartera_pendiente_resumen(filas_cartera)
    alertas = metricas.detectar_alertas(comparacion, 0.15)

    por_anio = metricas.facturacion_por_anio(filas_fact)
    comparacion_anual = None
    if anio_seleccionado:
        comparacion_anual = metricas.anio_vs_anterior(filas_fact, anio_seleccionado)

    siguiente_nivel, opciones_nivel = _opciones_siguiente_nivel(conn, usuario, filtros_drill, where, params)

    return {
        'por_mes': por_mes, 'comparacion': comparacion,
        'top_articulos': top_articulos, 'top_distribuidores': top_distribuidores,
        'cartera': cartera, 'alertas': alertas,
        'por_anio': por_anio, 'comparacion_anual': comparacion_anual,
        'siguiente_nivel': siguiente_nivel, 'opciones_nivel': opciones_nivel,
    }


@app.route('/dashboard')
def dashboard():
    conn = get_connection()
    usuario = _usuario_actual(conn)
    if not usuario:
        conn.close()
        return redirect(url_for('login'))

    filtros_drill = _leer_filtros_drill(usuario)
    anio_seleccionado = request.args.get('anio')

    datos = _calcular_datos_dashboard(usuario, conn, filtros_drill, anio_seleccionado)
    conn.close()

    chart_data = {'labels': list(datos['por_mes'].keys()), 'valores': list(datos['por_mes'].values())}
    chart_anual = {'labels': list(datos['por_anio'].keys()), 'valores': list(datos['por_anio'].values())}

    # Migas de pan: nivel de rol (fijo, sin link) + niveles elegidos por drill-down (con link para volver)
    migas = []
    for campo in CAMPOS_JERARQUIA:
        if usuario[campo]:
            migas.append({'campo': campo, 'valor': usuario[campo], 'fijo': True})
        elif campo in filtros_drill:
            migas.append({'campo': campo, 'valor': filtros_drill[campo], 'fijo': False})

    return render_template(
        'dashboard.html',
        usuario=usuario,
        migas=migas,
        filtros_drill=filtros_drill,
        siguiente_nivel=datos['siguiente_nivel'],
        opciones_nivel=datos['opciones_nivel'],
        comparacion=datos['comparacion'],
        top_articulos=datos['top_articulos'],
        top_distribuidores=datos['top_distribuidores'],
        cartera=datos['cartera'],
        alertas=datos['alertas'],
        chart_data_json=json.dumps(chart_data),
        chart_anual_json=json.dumps(chart_anual),
        anio_seleccionado=anio_seleccionado,
        comparacion_anual=datos['comparacion_anual'],
    )


@app.route('/dashboard/descargar')
def descargar_informe():
    conn = get_connection()
    usuario = _usuario_actual(conn)
    if not usuario:
        conn.close()
        return redirect(url_for('login'))

    filtros_drill = _leer_filtros_drill(usuario)
    datos = _calcular_datos_dashboard(usuario, conn, filtros_drill)
    conn.close()

    buffer = generar_informe_excel(
        usuario, datos['por_mes'], datos['comparacion'], datos['top_articulos'],
        datos['top_distribuidores'], datos['cartera'], datos['alertas'], None,
    )

    nombre_archivo = f"informe_piletas_{usuario['nombre'].replace(' ', '_')}.xlsx"
    return send_file(
        buffer, as_attachment=True, download_name=nombre_archivo,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


if __name__ == '__main__':
    app.run(debug=False, port=5000)
