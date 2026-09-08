# run_diario.py
# Orquesta el proceso diario completo, sin intervencion humana:
#   1. Carga los CSV frescos a Postgres (agregado + ventana de detalle)
#   2. Para cada usuario activo, calcula sus metricas segun su alcance
#   3. Arma el mail ya interpretado y lo envia solo
#
# La comparacion de periodo usa SIEMPRE el agregado mensual (historico
# completo desde 2015), nunca el detalle (que solo cubre la ventana
# reciente) -- asi la comparacion "vs. los ultimos 12 meses" es exacta
# aunque el detalle linea por linea no llegue tan atras.

import config
import cargar_datos
import metricas
import email_informe
from db import get_connection
from roles import clausula_where, usuarios_activos


def _mensual_a_filas(rows_mensual):
    return [{
        'fecha': f"{r['anio']:04d}-{r['mes']:02d}-01",
        'importe_neto': float(r['importe_neto'] or 0),
        'cantidad': float(r['cantidad'] or 0),
    } for r in rows_mensual]


def main():
    print('Cargando datos frescos a la base...')
    cargar_datos.main()

    conn = get_connection()
    usuarios = usuarios_activos(conn)
    print(f'{len(usuarios)} usuarios activos en total')

    enviados, fallidos = 0, 0

    for usuario in usuarios:
        where, params = clausula_where(usuario)

        filas_mensual = _mensual_a_filas(
            conn.execute(f'SELECT * FROM facturacion_mensual WHERE {where}', params).fetchall()
        )
        filas_detalle = [
            {**dict(f), 'fecha': f['fecha'].isoformat()}
            for f in conn.execute(f'SELECT * FROM facturacion_detalle WHERE {where}', params).fetchall()
        ]
        filas_cartera = conn.execute(f'SELECT * FROM cartera_pendiente WHERE {where}', params).fetchall()

        comparacion = metricas.comparacion_periodo(filas_mensual)
        top_articulos = metricas.top_articulos_detalle(filas_detalle, n=5)
        top_distribuidores = metricas.top_n(filas_detalle, 'distribuidor_nombre', n=5)
        cartera = metricas.cartera_pendiente_resumen(filas_cartera)

        umbral = config.DESVIO_PCT_ALERTA_DEFAULT
        alertas = metricas.detectar_alertas(comparacion, umbral)

        html = email_informe.armar_html(
            usuario, comparacion, top_articulos, top_distribuidores, cartera, alertas, umbral,
        )

        asunto = f'Resumen diario Piletas — {usuario["nombre"]}'
        if alertas:
            asunto = f'⚠ {asunto}'

        try:
            email_informe.enviar(usuario['email'], asunto, html)
            print(f'  Enviado a {usuario["email"]}')
            enviados += 1
        except Exception as e:
            print(f'  ERROR enviando a {usuario["email"]}: {e}')
            fallidos += 1

    conn.close()
    print(f'Listo. Enviados: {enviados}, fallidos: {fallidos}.')


if __name__ == '__main__':
    main()
