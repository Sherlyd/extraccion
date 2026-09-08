# run_diario.py
# Orquesta el proceso completo de la mañana, SIN intervencion humana:
#   1. Carga los CSV frescos que dejo el extractor de Node
#   2. Para cada usuario activo, calcula sus metricas ya filtradas
#      por su propio alcance de rol (centro/zona/rubro/ejecutivo)
#   3. Arma el mail ya interpretado (narrativa + semaforo + alertas)
#      y lo envia solo -- nadie tiene que mandar nada uno por uno.
#
# Pensado para correr una vez por dia via Task Scheduler, despues del
# extractor de Node.

import config
import cargar_datos
import metricas
import email_informe
from db import get_connection
from roles import clausula_where, usuarios_activos


def main():
    print('Cargando datos frescos a la base...')
    cargar_datos.main()

    conn = get_connection()
    usuarios = usuarios_activos(conn)
    print(f'{len(usuarios)} usuarios activos en total')

    enviados, fallidos = 0, 0

    for usuario in usuarios:
        where, params = clausula_where(usuario)

        filas_fact = conn.execute(
            f'SELECT * FROM facturacion WHERE {where}', params
        ).fetchall()
        filas_cartera = conn.execute(
            f'SELECT * FROM cartera_pendiente WHERE {where}', params
        ).fetchall()

        comparacion = metricas.comparacion_periodo(filas_fact)
        top_articulos = metricas.top_articulos_detalle(filas_fact, n=5)
        top_distribuidores = metricas.top_n(filas_fact, 'distribuidor_nombre', n=5)
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
