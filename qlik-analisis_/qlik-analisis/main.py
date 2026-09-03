# main.py
# Orquesta todo el flujo: carga los 3 exports de Qlik, corre los cruces
# y genera el informe final en Excel.
#
# Uso: python main.py

import os
import config
import loaders
import cruces
from generar_informe import generar_informe


def main():
    fact_path = os.path.join(config.DATA_DIR, config.FACTURACION_DETALLE)
    cartera_path = os.path.join(config.DATA_DIR, config.CARTERA_PENDIENTE)
    top_dist_path = os.path.join(config.DATA_DIR, config.TOP_DISTRIBUIDORES)

    print('Cargando datos...')
    df_fact = loaders.load_facturacion_detalle(fact_path)
    df_cartera = loaders.load_cartera_pendiente(cartera_path)
    df_top_dist = loaders.load_top_distribuidores(top_dist_path)
    print(f'  Facturacion: {len(df_fact)} filas')
    print(f'  Cartera: {len(df_cartera)} filas')
    print(f'  Distribuidores: {len(df_top_dist)} filas')

    print('Calculando cruces...')
    mensual = cruces.evolucion_mensual(df_fact, config.Z_SCORE_OUTLIER)
    top_cli = cruces.top_clientes(df_fact, config.TOP_N)
    pareto_resumen, pareto_detalle = cruces.concentracion_distribuidores(df_top_dist)
    cartera_cli = cruces.cartera_por_cliente(df_cartera, config.TOP_N)
    cruce_riesgo = cruces.cruce_riesgo_cartera(df_fact, df_cartera, config.UMBRAL_RIESGO_CARTERA)

    # KPIs para la hoja de resumen
    total_facturado = df_fact['Importe Neto'].sum()
    total_cartera = df_cartera['Total Pendiente'].sum()
    cartera_onf = df_cartera[df_cartera['ONF Activa'] == 'SÍ']['Total Pendiente'].sum() if 'ONF Activa' in df_cartera.columns else 0
    meses_atipicos = mensual[mensual['Atipico']]['mes'].dt.strftime('%d-%m-%Y').tolist()
    clientes_riesgo = int(cruce_riesgo['Riesgo Alto'].sum())

    kpis = [
        ('Total facturado (neto, periodo cargado)', total_facturado, '$#,##0'),
        ('Total cartera pendiente de cobro', total_cartera, '$#,##0'),
        ('Cartera bloqueada por ONF', cartera_onf, '$#,##0'),
        ('% cartera bloqueada por ONF', (cartera_onf / total_cartera) if total_cartera else 0, '0.0%'),
        ('Meses con facturacion atipica', ', '.join(meses_atipicos) if meses_atipicos else 'Ninguno', None),
        (f'Clientes con riesgo alto de cartera (> {config.UMBRAL_RIESGO_CARTERA:.0%} de lo facturado)',
         clientes_riesgo, '0'),
    ]

    print('Generando informe...')
    os.makedirs(os.path.dirname(config.OUTPUT_PATH), exist_ok=True)
    generar_informe(
        config.OUTPUT_PATH,
        mensual, top_cli, pareto_resumen, pareto_detalle,
        cartera_cli, cruce_riesgo, kpis,
    )
    print(f'Listo: {config.OUTPUT_PATH}')


if __name__ == '__main__':
    main()
