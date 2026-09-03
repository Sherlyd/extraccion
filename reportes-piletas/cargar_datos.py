# cargar_datos.py
# Lee los CSV que genera el extractor de Node (qlik-extractor/extract.js)
# y los carga a la base de datos propia. Pensado para correr despues del
# extractor, como parte de la tarea programada diaria.
#
# Estrategia simple: cada corrida BORRA e inserta de nuevo el periodo
# cargado (no intenta hacer upsert fila por fila). Esto es correcto
# porque Qlik siempre exporta el periodo completo, no incrementos.

import os
import csv
import config
from db import get_connection, init_db


def _leer_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def cargar_facturacion(conn):
    path = os.path.join(config.DATA_DIR, config.FACTURACION_CSV)
    filas = _leer_csv(path)
    if not filas:
        return 0

    conn.execute('DELETE FROM facturacion')  # recarga completa
    for r in filas:
        importe = float(r.get('Importe', 0) or 0)
        tipo = r.get('Tipo Comp', '')
        importe_neto = -importe if tipo == 'NC' else importe
        conn.execute('''
            INSERT INTO facturacion
                (fecha, tipo_comp, distribuidor_id, distribuidor_nombre,
                 cliente_final_nombre, articulo, rubro, ejecutivo_cuenta,
                 sucursal, cantidad, importe, importe_neto)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            r.get('Fecha de Alta'), tipo, r.get('Distr.'), r.get('Razon Social Distr'),
            r.get('Razon Social CF'), r.get('Artículo'), r.get('Familia1'),
            r.get('Ejecutivo de Cuenta'), r.get('Suc.'),
            float(r.get('Cantid', 0) or 0), importe, importe_neto,
        ))
    conn.commit()
    return len(filas)


def cargar_pedidos(conn):
    path = os.path.join(config.DATA_DIR, config.PEDIDOS_CSV)
    filas = _leer_csv(path)
    if not filas:
        return 0

    conn.execute('DELETE FROM pedidos')
    for r in filas:
        conn.execute('''
            INSERT INTO pedidos
                (nro_pedido, distribuidor_nombre, articulo, rubro,
                 ejecutivo_cuenta, sucursal, cantidad)
            VALUES (?,?,?,?,?,?,?)
        ''', (
            r.get('Nro. Pedido'), r.get('Razon Social Distr'), r.get('Artículo'),
            r.get('Familia1'), r.get('Ejecutivo de Cuenta'), r.get('Suc.'),
            float(r.get('Cantid', 0) or 0),
        ))
    conn.commit()
    return len(filas)


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
                 rubro, ejecutivo_cuenta, sucursal, total_pendiente)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (
            r.get('Núm. Pedido'), r.get('Razon Social Distr'), r.get('Estado Pedido'),
            r.get('ONF Activa'), r.get('Familia1'), r.get('Ejecutivo de Cuenta'),
            r.get('Suc.'), float(r.get('Total Pendiente M$', 0) or 0),
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
