# cruces.py
# Cada funcion toma uno o mas DataFrames ya limpios (ver loaders.py) y
# devuelve un DataFrame con el resultado del cruce/analisis, listo para
# volcar al informe.

import pandas as pd
import numpy as np


def evolucion_mensual(df_facturacion, z_score_outlier=1.5):
    """Factura neta por mes + marca de meses atipicos (fuera de tendencia)."""
    mensual = (
        df_facturacion
        .assign(mes=df_facturacion['Fecha de Alta'].dt.to_period('M').astype(str))
        .groupby('mes')
        .agg(Importe_Neto=('Importe Neto', 'sum'), Comprobantes=('Importe Neto', 'count'))
        .reset_index()
    )

    media = mensual['Importe_Neto'].mean()
    desvio = mensual['Importe_Neto'].std()
    mensual['z_score'] = (mensual['Importe_Neto'] - media) / desvio if desvio else 0
    mensual['Atipico'] = mensual['z_score'].abs() > z_score_outlier

    return mensual


def top_clientes(df_facturacion, n=20):
    """Ranking de clientes finales por facturacion neta."""
    col_cliente = 'Razon Social CF' if 'Razon Social CF' in df_facturacion.columns else 'Razon Social Distr'
    resumen = (
        df_facturacion
        .groupby(col_cliente)
        .agg(Importe_Neto=('Importe Neto', 'sum'), Comprobantes=('Importe Neto', 'count'))
        .sort_values('Importe_Neto', ascending=False)
        .reset_index()
    )
    total = resumen['Importe_Neto'].sum()
    resumen['% del Total'] = resumen['Importe_Neto'] / total
    return resumen.head(n)


def concentracion_distribuidores(df_top_distribuidores):
    """Analisis de Pareto: cuanto concentran los distribuidores top."""
    df = df_top_distribuidores.sort_values('M$ Fact.', ascending=False).reset_index(drop=True)
    df['% Acumulado'] = df['M$ Fact.'].cumsum() / df['M$ Fact.'].sum()

    hitos = [5, 10, 20, 50]
    resumen = []
    for h in hitos:
        if len(df) >= h:
            resumen.append({
                'Top N distribuidores': h,
                '% de la facturacion total': df.iloc[h - 1]['% Acumulado'],
            })

    cola_larga = (df['M$ Fact.'] / df['M$ Fact.'].sum() < 0.0001).sum()
    resumen.append({
        'Top N distribuidores': f'Cola larga (< 0.01% c/u, de {len(df)} totales)',
        '% de la facturacion total': cola_larga / len(df),
    })

    return pd.DataFrame(resumen), df


def cartera_por_cliente(df_cartera, n=20):
    """Cartera pendiente agrupada por cliente, separando lo bloqueado por ONF."""
    col_cliente = 'Razon Social Distr' if 'Razon Social Distr' in df_cartera.columns else 'Razon Social CF'

    resumen = (
        df_cartera
        .groupby(col_cliente)
        .agg(
            Total_Pendiente=('Total Pendiente', 'sum'),
            Con_ONF=('Total Pendiente', lambda s: s[df_cartera.loc[s.index, 'ONF Activa'] == 'SÍ'].sum()),
        )
        .sort_values('Total_Pendiente', ascending=False)
        .reset_index()
    )
    resumen['% Bloqueado por ONF'] = np.where(
        resumen['Total_Pendiente'] > 0,
        resumen['Con_ONF'] / resumen['Total_Pendiente'],
        0,
    )
    return resumen.head(n)


def cruce_riesgo_cartera(df_facturacion, df_cartera, umbral=0.5):
    """
    El cruce central: por cada cliente, cuanto factura vs. cuanto tiene
    pendiente de cobro. Un cliente con mucha cartera pendiente en relacion
    a lo que factura es una señal de riesgo (venden mucho pero cobran poco,
    o hay algo trabado).
    """
    col_fact = 'Razon Social CF' if 'Razon Social CF' in df_facturacion.columns else 'Razon Social Distr'
    col_cartera = 'Razon Social Distr' if 'Razon Social Distr' in df_cartera.columns else 'Razon Social CF'

    fact = df_facturacion.groupby(col_fact)['Importe Neto'].sum().rename('Facturacion')
    cartera = df_cartera.groupby(col_cartera)['Total Pendiente'].sum().rename('Cartera Pendiente')

    cruce = pd.concat([fact, cartera], axis=1).fillna(0).reset_index()
    cruce.rename(columns={'index': 'Cliente'}, inplace=True)

    # Solo tiene sentido calcular el ratio para clientes que efectivamente
    # facturan algo (evita division por cero / ratios infinitos con ruido).
    cruce = cruce[cruce['Facturacion'] > 0].copy()
    cruce['% Cartera / Facturacion'] = cruce['Cartera Pendiente'] / cruce['Facturacion']
    cruce['Riesgo Alto'] = cruce['% Cartera / Facturacion'] > umbral

    return cruce.sort_values('% Cartera / Facturacion', ascending=False).reset_index(drop=True)
