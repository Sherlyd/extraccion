# cargar_datos.py
# Lee los CSV que genera el extractor de Node (qlik-extractor/extract.js)
# y los carga a la base de datos propia. Los nombres de columna de aca
# abajo son los campos REALES de Qlik (confirmados via API).

import os
import csv
from datetime import datetime
import config
from db import get_connection, init_db


def _leer_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _parsear_fecha(valor):
    """Convierte una fecha tal como la devuelve Qlik (normalmente
    DD/MM/YYYY) a formato ISO YYYY-MM-DD."""
    if not valor:
        return None
    for formato in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(valor.strip(), formato).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return valor


def cargar_facturacion(conn):
    path = os.path.join(config.DATA_DIR, config.FACTURACION_CSV)
    filas = _leer_csv(path)
    if not filas:
        return 0

    conn.execute('DELETE FROM facturacion')
    cargadas = 0
    for r in filas:
        if r.get('_Documento') != 'Factura':
            continue

        importe = float(r.get('Importe', 0) or 0)
        tipo = r.get('fv0_tipcmp', '')
        importe_neto = importe  # #Facturacion ya viene neto de NC (validado contra Qlik)

        conn.execute('''
            INSERT INTO facturacion
                (fecha, tipo_comp, distribuidor_id, distribuidor_nombre,
                 cliente_final_nombre, articulo, rubro, ejecutivo_cuenta,
                 centro_distribucion, zona, sucursal, cantidad, importe, importe_neto)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            _parsear_fecha(r.get('fv0_fecalt')), tipo, r.get('client'), r.get('Razon Social Distr'),
            r.get('Razon Social CF'), r.get('articu'), r.get('Familia1'),
            r.get('Ejecutivo de Cuenta'), r.get('Centro Distribucion'), r.get('Zona Desc Distr'),
            r.get('sucurs'), float(r.get('Cantid', 0) or 0), importe, importe_neto,
        ))
        cargadas += 1
    conn.commit()
    return cargadas


def cargar_pedidos(conn):
    path = os.path.join(config.DATA_DIR, config.PEDIDOS_CSV)
    filas = _leer_csv(path)
    if not filas:
        return 0

    conn.execute('DELETE FROM pedidos')
    cargadas = 0
    for r in filas:
        if r.get('_Documento') != 'Pedido':
            continue
        conn.execute('''
            INSERT INTO pedidos
                (nro_pedido, distribuidor_nombre, articulo, rubro,
                 ejecutivo_cuenta, centro_distribucion, zona, sucursal, cantidad)
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (
            r.get('numero'), r.get('Razon Social Distr'), r.get('articu'),
            r.get('Familia1'), r.get('Ejecutivo de Cuenta'), r.get('Centro Distribucion'),
            r.get('Zona Desc Distr'), r.get('sucurs'), float(r.get('Cantid', 0) or 0),
        ))
        cargadas += 1
    conn.commit()
    return cargadas


def cargar_cartera(conn):
    path = os.path.join(config.DATA_DIR, config.CARTERA_CSV)
    filas = _leer_csv(path)
    if not filas:
        return 0

    conn.execute('DELETE FROM cartera_pendiente')
    for r in filas:
        conn.execute('''
            INSERT INTO cartera_pendiente
                (nro_pedido, distribuidor_nombre, estado_pedido, onf_activa,
                 rubro, ejecutivo_cuenta, centro_distribucion, zona, sucursal, total_pendiente)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', (
            r.get('pe1_numero'), r.get('Razon Social Distr'), r.get('estado'),
            r.get('ONF Activa'), r.get('Familia1'), r.get('Ejecutivo de Cuenta'),
            r.get('Centro Distribucion'), r.get('Zona Desc Distr'), r.get('cls_sucurs'),
            float(r.get('Total Pendiente', 0) or 0),
        ))
    conn.commit()
    return len(filas)


def _log(conn, archivo, filas, estado, detalle=''):
    conn.execute(
        'INSERT INTO log_extracciones (archivo, filas_cargadas, estado, detalle) VALUES (?,?,?,?)',
        (archivo, filas, estado, detalle),
    )
    conn.commit()


def main():
    init_db()
    conn = get_connection()

    for nombre, funcion, archivo in [
        ('facturacion', cargar_facturacion, config.FACTURACION_CSV),
        ('pedidos', cargar_pedidos, config.PEDIDOS_CSV),
        ('cartera', cargar_cartera, config.CARTERA_CSV),
    ]:
        try:
            n = funcion(conn)
            _log(conn, archivo, n, 'ok')
            print(f'{nombre}: {n} filas cargadas')
        except Exception as e:
            _log(conn, archivo, 0, 'error', str(e))
            print(f'{nombre}: ERROR - {e}')

    conn.close()


if __name__ == '__main__':
    main()
