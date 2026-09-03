# run_diario.py
# Orquesta el proceso completo de la mañana:
#   1. (afuera de este script) el extractor de Node ya corrio y dejo CSVs frescos
#   2. Carga esos CSV a la base propia
#   3. Para cada usuario activo del rubro, calcula sus metricas ya filtradas por rol
#   4. Arma y envia el mail
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

    for rubro in config.RUBROS_ACTIVOS:
        print(f'--- Rubro: {rubro} ---')
        usuarios = usuarios_activos(conn, rubro=rubro)
        print(f'{len(usuarios)} usuarios activos para este rubro')

        for usuario in usuarios:
            where, params = clausula_where(usuario)

            filas_fact = conn.execute(
                f'SELECT * FROM facturacion WHERE {where}', params
            ).fetchall()
            filas_cartera = conn.execute(
                f'SELECT * FROM cartera_pendiente WHERE {where}', params
            ).fetchall()

            por_mes = metricas.facturacion_por_mes(filas_fact)
            comparacion = metricas.comparacion_mes_actual_vs_promedio_anual(por_mes)
            top_articulos = metricas.top_n(filas_fact, 'articulo', n=5)
            top_distribuidores = metricas.top_n(filas_fact, 'distribuidor_nombre', n=5)
            cartera = metricas.cartera_pendiente_resumen(filas_cartera)

            umbral = config.DESVIO_PCT_ALERTA_DEFAULT
            alertas = metricas.detectar_alertas(comparacion, umbral)

            html = email_informe.armar_html(
                usuario, por_mes, comparacion, top_articulos, top_distribuidores,
                cartera, alertas,
            )

            asunto = f'Informe diario Piletas — {usuario["nombre"]}'
            if alertas:
                asunto = f'⚠ {asunto}'

            try:
                email_informe.enviar(usuario['email'], asunto, html)
                print(f'  Enviado a {usuario["email"]}')
            except Exception as e:
                print(f'  ERROR enviando a {usuario["email"]}: {e}')

    conn.close()
    print('Listo.')


if __name__ == '__main__':
    main()
