# app.py
# Dashboard web minimo para visualizar el avance en vivo. Por ahora
# soporta 2 roles: gerente_general (ve todo) y gerente_sucursal (ve su
# sucursal + rubro). El "login" es solo elegir el usuario de una lista
# -- es un standin temporal, NO es autenticacion real. Reemplazar por
# un login de verdad antes de exponer esto fuera de tu compu.
#
# Uso: python app.py
# Despues abrir http://localhost:5000 en el navegador.

from flask import Flask, render_template, redirect, url_for, request, session, send_file
from werkzeug.security import check_password_hash
from db import get_connection
from roles import clausula_where
import metricas
from generar_informe import generar_informe_excel
import json

app = Flask(__name__)
app.secret_key = 'cambiar-esto-antes-de-produccion'


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


def _calcular_datos_dashboard(usuario, conn):
    """Calcula todo lo que necesita el dashboard (y el informe
    descargable) para un usuario dado, ya filtrado por su rol."""
    where, params = clausula_where(usuario)

    filas_fact = conn.execute(f'SELECT * FROM facturacion WHERE {where}', params).fetchall()
    filas_cartera = conn.execute(f'SELECT * FROM cartera_pendiente WHERE {where}', params).fetchall()

    por_mes = metricas.facturacion_por_mes(filas_fact)
    comparacion = metricas.comparacion_mes_actual_vs_promedio_anual(por_mes)
    top_articulos = metricas.top_n(filas_fact, 'articulo', n=5)
    top_distribuidores = metricas.top_n(filas_fact, 'distribuidor_nombre', n=5)
    cartera = metricas.cartera_pendiente_resumen(filas_cartera)
    alertas = metricas.detectar_alertas(comparacion, 0.15)

    por_sucursal = None
    if usuario['rol'] == 'gerente_general':
        rows = conn.execute('''
            SELECT sucursal, SUM(importe_neto) as total
            FROM facturacion
            GROUP BY sucursal
            ORDER BY total DESC
        ''').fetchall()
        por_sucursal = [(r['sucursal'] or '(sin dato)', r['total'] or 0) for r in rows]

    return {
        'por_mes': por_mes,
        'comparacion': comparacion,
        'top_articulos': top_articulos,
        'top_distribuidores': top_distribuidores,
        'cartera': cartera,
        'alertas': alertas,
        'por_sucursal': por_sucursal,
    }


@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    usuario = conn.execute('SELECT * FROM usuarios WHERE id = ?', (session['usuario_id'],)).fetchone()
    if not usuario:
        session.clear()
        conn.close()
        return redirect(url_for('login'))

    datos = _calcular_datos_dashboard(usuario, conn)
    conn.close()

    chart_data = {
        'labels': list(datos['por_mes'].keys()),
        'valores': list(datos['por_mes'].values()),
    }

    return render_template(
        'dashboard.html',
        usuario=usuario,
        comparacion=datos['comparacion'],
        top_articulos=datos['top_articulos'],
        top_distribuidores=datos['top_distribuidores'],
        cartera=datos['cartera'],
        alertas=datos['alertas'],
        por_sucursal=datos['por_sucursal'],
        chart_data_json=json.dumps(chart_data),
    )


@app.route('/dashboard/descargar')
def descargar_informe():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    usuario = conn.execute('SELECT * FROM usuarios WHERE id = ?', (session['usuario_id'],)).fetchone()
    if not usuario:
        session.clear()
        conn.close()
        return redirect(url_for('login'))

    datos = _calcular_datos_dashboard(usuario, conn)
    conn.close()

    buffer = generar_informe_excel(
        usuario, datos['por_mes'], datos['comparacion'], datos['top_articulos'],
        datos['top_distribuidores'], datos['cartera'], datos['alertas'], datos['por_sucursal'],
    )

    nombre_archivo = f"informe_piletas_{usuario['nombre'].replace(' ', '_')}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


if __name__ == '__main__':
    app.run(debug=False, port=5000)
