# cargar_datos.py
# Carga los CSV del extractor a Postgres, con el patron de DOS niveles:
#
#   1. Agregado mensual (facturacion_mensual/pedidos_mensual): se
#      recalcula TODO el historico cada vez via UPSERT (insertar o
#      actualizar si ya existe esa combinacion mes+dimensiones) --
#      son pocas filas, tarda segundos.
#
#   2. Detalle (facturacion_detalle/pedidos_detalle): SOLO se
#      reemplaza una ventana reciente (VENTANA_DETALLE_DIAS), no el
#      historico completo -- ahi vive el volumen real (millones de
#      filas historicas que no necesitan re-cargarse todos los dias).
#
# Las inserciones usan execute_values (lote), no una fila a la vez --
# con cientos de miles de filas, insertar de a una seria demasiado lento.

import os
import csv
from datetime import datetime, date, timedelta
from collections import defaultdict
import psycopg2.extras
import config
from db import get_connection, init_db

VENTANA_DETALLE_DIAS = int(os.environ.get('VENTANA_DETALLE_DIAS', '730'))  # ~24 meses


def _leer_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _parsear_fecha(valor):
    """Convierte una fecha tal como la devuelve Qlik (DD/MM/YYYY) a
    date de Python. None si no se puede parsear."""
    if not valor:
        return None
    for formato in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(valor.strip(), formato).date()
        except ValueError:
            continue
    return None


def cargar_facturacion(conn):
    path = os.path.join(config.DATA_DIR, config.FACTURACION_CSV)
    filas = _leer_csv(path)
    if not filas:
        return 0, 0

    fecha_corte = date.today() - timedelta(days=VENTANA_DETALLE_DIAS)
    agregados = defaultdict(lambda: {'cantidad': 0.0, 'importe_neto': 0.0})
    filas_detalle = []

    for r in filas:
        if r.get('_Documento') != 'Factura':
            continue
        fecha = _parsear_fecha(r.get('ClaveFecha'))
        if not fecha:
            continue

        importe = float(r.get('Importe', 0) or 0)
        cantidad = float(r.get('Cantid', 0) or 0)
        rubro = r.get('Familia1')
        familia4 = r.get('Familia4')
        centro = r.get('Centro Distribucion')
        zona = r.get('Zona Desc Distr')
        ejecutivo = r.get('Ejecutivo de Cuenta')

        clave = (fecha.year, fecha.month, centro, zona, rubro, familia4, ejecutivo)
        agregados[clave]['cantidad'] += cantidad
        agregados[clave]['importe_neto'] += importe

        if fecha >= fecha_corte:
            filas_detalle.append({
                'fecha': fecha, 'tipo_comp': r.get('fv0_tipcmp', ''),
                'distribuidor_id': r.get('client'), 'distribuidor_nombre': r.get('Razon Social Distr'),
                'cliente_final_nombre': r.get('Razon Social CF'), 'articulo': r.get('articu'),
                'rubro': rubro, 'familia2': r.get('Familia2'), 'familia3': r.get('Familia3'),
                'familia4': familia4, 'ejecutivo_cuenta': ejecutivo, 'centro_distribucion': centro,
                'zona': zona, 'sucursal': r.get('sucurs'), 'cantidad': cantidad,
                'importe': importe, 'importe_neto': importe,
            })

    cur = conn.cursor()

    # --- Nivel 1: agregado mensual, upsert de TODO el historico ---
    valores_agregado = [
        (anio, mes, centro, zona, rubro, familia4, ejecutivo, v['cantidad'], v['importe_neto'])
        for (anio, mes, centro, zona, rubro, familia4, ejecutivo), v in agregados.items()
    ]
    if valores_agregado:
        psycopg2.extras.execute_values(cur, '''
            INSERT INTO facturacion_mensual
                (anio, mes, centro_distribucion, zona, rubro, familia4, ejecutivo_cuenta, cantidad, importe_neto)
            VALUES %s
            ON CONFLICT (anio, mes, centro_distribucion, zona, rubro, familia4, ejecutivo_cuenta)
            DO UPDATE SET cantidad = EXCLUDED.cantidad, importe_neto = EXCLUDED.importe_neto,
                          actualizado_en = NOW()
        ''', valores_agregado)

    # --- Nivel 2: detalle, solo se reemplaza la ventana reciente ---
    cur.execute('DELETE FROM facturacion_detalle WHERE fecha >= %s', (fecha_corte,))
    if filas_detalle:
        columnas = list(filas_detalle[0].keys())
        valores_detalle = [tuple(f[c] for c in columnas) for f in filas_detalle]
        psycopg2.extras.execute_values(cur, f'''
            INSERT INTO facturacion_detalle ({', '.join(columnas)})
            VALUES %s
        ''', valores_detalle)

    conn.commit()
    cur.close()
    return len(agregados), len(filas_detalle)


def cargar_pedidos(conn):
    path = os.path.join(config.DATA_DIR, config.PEDIDOS_CSV)
    filas = _leer_csv(path)
    if not filas:
        return 0, 0

    fecha_corte = date.today() - timedelta(days=VENTANA_DETALLE_DIAS)
    agregados = defaultdict(lambda: {'cantidad': 0.0, 'importe': 0.0})
    filas_detalle = []

    for r in filas:
        if r.get('_Documento') != 'Pedido':
            continue
        # pedidos_detalle no trae fecha propia en nuestra extraccion
        # actual -- se agrupa el agregado por fecha de carga generica
        # (hoy) hasta que sumemos un campo de fecha real a esa extraccion.
        fecha = date.today()

        cantidad = float(r.get('Cantid', 0) or 0)
        importe = float(r.get('Importe', 0) or 0)
        rubro = r.get('Familia1')
        centro = r.get('Centro Distribucion')
        zona = r.get('Zona Desc Distr')
        ejecutivo = r.get('Ejecutivo de Cuenta')

        clave = (fecha.year, fecha.month, centro, zona, rubro, ejecutivo)
        agregados[clave]['cantidad'] += cantidad
        agregados[clave]['importe'] += importe

        filas_detalle.append({
            'fecha': fecha, 'nro_pedido': r.get('numero'), 'distribuidor_nombre': r.get('Razon Social Distr'),
            'articulo': r.get('articu'), 'rubro': rubro, 'ejecutivo_cuenta': ejecutivo,
            'centro_distribucion': centro, 'zona': zona, 'sucursal': r.get('sucurs'), 'cantidad': cantidad,
        })

    cur = conn.cursor()

    valores_agregado = [
        (anio, mes, centro, zona, rubro, ejecutivo, v['cantidad'], v['importe'])
        for (anio, mes, centro, zona, rubro, ejecutivo), v in agregados.items()
    ]
    if valores_agregado:
        psycopg2.extras.execute_values(cur, '''
            INSERT INTO pedidos_mensual
                (anio, mes, centro_distribucion, zona, rubro, ejecutivo_cuenta, cantidad, importe)
            VALUES %s
            ON CONFLICT (anio, mes, centro_distribucion, zona, rubro, ejecutivo_cuenta)
            DO UPDATE SET cantidad = EXCLUDED.cantidad, importe = EXCLUDED.importe, actualizado_en = NOW()
        ''', valores_agregado)

    cur.execute('DELETE FROM pedidos_detalle')  # pedidos no tiene ventana temporal propia todavia
    if filas_detalle:
        columnas = list(filas_detalle[0].keys())
        valores_detalle = [tuple(f[c] for c in columnas) for f in filas_detalle]
        psycopg2.extras.execute_values(cur, f'''
            INSERT INTO pedidos_detalle ({', '.join(columnas)})
            VALUES %s
        ''', valores_detalle)

    conn.commit()
    cur.close()
    return len(agregados), len(filas_detalle)


def cargar_cartera(conn):
    path = os.path.join(config.DATA_DIR, config.CARTERA_CSV)
    filas = _leer_csv(path)
    if not filas:
        return 0

    cur = conn.cursor()
    cur.execute('DELETE FROM cartera_pendiente')

    valores = [(
        r.get('pe1_numero'), r.get('Razon Social Distr'), r.get('estado'), r.get('ONF Activa'),
        r.get('Familia1'), r.get('Ejecutivo de Cuenta'), r.get('Centro Distribucion'),
        r.get('Zona Desc Distr'), r.get('cls_sucurs'), float(r.get('Total Pendiente', 0) or 0),
    ) for r in filas]

    if valores:
        psycopg2.extras.execute_values(cur, '''
            INSERT INTO cartera_pendiente
                (nro_pedido, distribuidor_nombre, estado_pedido, onf_activa, rubro,
                 ejecutivo_cuenta, centro_distribucion, zona, sucursal, total_pendiente)
            VALUES %s
        ''', valores)

    conn.commit()
    cur.close()
    return len(valores)


def _log(conn, archivo, filas, estado, detalle=''):
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO log_extracciones (archivo, filas_cargadas, estado, detalle) VALUES (%s,%s,%s,%s)',
        (archivo, filas, estado, detalle),
    )
    conn.commit()
    cur.close()


def main():
    init_db()
    conn = get_connection()

    try:
        n_agregado, n_detalle = cargar_facturacion(conn)
        _log(conn, config.FACTURACION_CSV, n_detalle, 'ok')
        print(f'facturacion: {n_agregado} combinaciones mensuales actualizadas, '
              f'{n_detalle} filas de detalle (ventana de {VENTANA_DETALLE_DIAS} dias)')
    except Exception as e:
        conn.rollback()
        _log(conn, config.FACTURACION_CSV, 0, 'error', str(e))
        print(f'facturacion: ERROR - {e}')

    try:
        n_agregado, n_detalle = cargar_pedidos(conn)
        _log(conn, config.PEDIDOS_CSV, n_detalle, 'ok')
        print(f'pedidos: {n_agregado} combinaciones mensuales actualizadas, {n_detalle} filas de detalle')
    except Exception as e:
        conn.rollback()
        _log(conn, config.PEDIDOS_CSV, 0, 'error', str(e))
        print(f'pedidos: ERROR - {e}')

    try:
        n = cargar_cartera(conn)
        _log(conn, config.CARTERA_CSV, n, 'ok')
        print(f'cartera: {n} filas cargadas')
    except Exception as e:
        conn.rollback()
        _log(conn, config.CARTERA_CSV, 0, 'error', str(e))
        print(f'cartera: ERROR - {e}')

    conn.close()


if __name__ == '__main__':
    main()
