# loaders.py
# Funciones para leer los distintos exports de Qlik y devolverlos como
# DataFrames limpios (tipos correctos, sin filas de "Totales", etc.)
#
# Si Qlik cambia el nombre de alguna columna en una nueva version del
# dashboard, este es el unico lugar donde hay que ajustar el mapeo.

import pandas as pd


def load_facturacion_detalle(path):
    """Detalle de facturacion: una fila por linea de factura/NC."""
    df = pd.read_excel(path)

    # Filtra filas de resumen ("Totales") que a veces Qlik agrega en la
    # primera fila de datos.
    if 'Tipo Comp' in df.columns:
        df = df[df['Tipo Comp'].isin(['FC', 'NC'])].copy()

    df['Fecha de Alta'] = pd.to_datetime(df['Fecha de Alta'], errors='coerce')
    df['Importe'] = pd.to_numeric(df['Importe'], errors='coerce')
    df['Cantid'] = pd.to_numeric(df.get('Cantid'), errors='coerce')

    # Las notas de credito restan facturacion neta.
    df['Importe Neto'] = df.apply(
        lambda r: -r['Importe'] if r['Tipo Comp'] == 'NC' else r['Importe'],
        axis=1,
    )

    return df.dropna(subset=['Fecha de Alta'])


def load_cartera_pendiente(path):
    """Cartera pendiente de cobro ('Detalle Colchon')."""
    df = pd.read_excel(path)

    if 'Núm. Pedido' in df.columns:
        df = df[df['Núm. Pedido'].notna()].copy()

    pendiente_col = [c for c in df.columns if 'Pendiente' in c][0]
    df[pendiente_col] = pd.to_numeric(df[pendiente_col], errors='coerce').fillna(0)
    df.rename(columns={pendiente_col: 'Total Pendiente'}, inplace=True)

    return df


def load_top_distribuidores(path):
    """Ranking de distribuidores por facturacion."""
    df = pd.read_excel(path)
    df = df[df['Razon Social Distr'] != 'Totales'].copy()

    fact_col = [c for c in df.columns if 'Fact.' in c and '%' not in c][0]
    df[fact_col] = pd.to_numeric(df[fact_col], errors='coerce')
    df.rename(columns={fact_col: 'M$ Fact.'}, inplace=True)

    return df
