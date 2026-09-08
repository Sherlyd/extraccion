# analizar_calidad_datos.py
# Analisis exploratorio de calidad sobre el CSV de facturacion, ANTES
# de decidir reglas de limpieza o confiar en los numeros a ojo cerrado.
# Responde: la distribucion de importes es normal? hay outliers? hay
# inconsistencias logicas (importe negativo sin ser NC, cantidad en
# cero con importe positivo, etc)?
#
# Uso: python analizar_calidad_datos.py [ruta_al_csv]
# Por defecto usa data/facturacion_detalle.csv (el que deja extract.js).

import sys
import csv
import statistics
from collections import Counter

try:
    from scipy import stats
    import numpy as np
    TIENE_SCIPY = True
except ImportError:
    TIENE_SCIPY = False


def cargar_importes(path):
    importes, cantidades, filas_crudas = [], [], []
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row.get('_Documento') != 'Factura':
                continue
            try:
                importe = float(row.get('Importe', 0) or 0)
                cantidad = float(row.get('Cantid', 0) or 0)
            except ValueError:
                continue
            importes.append(importe)
            cantidades.append(cantidad)
            filas_crudas.append(row)
    return importes, cantidades, filas_crudas


def describir(nombre, valores):
    print(f'\n--- {nombre} ---')
    print(f'  n = {len(valores):,}')
    print(f'  media = {statistics.mean(valores):,.2f}')
    print(f'  mediana = {statistics.median(valores):,.2f}')
    print(f'  desvio estandar = {statistics.stdev(valores):,.2f}')
    print(f'  minimo = {min(valores):,.2f}')
    print(f'  maximo = {max(valores):,.2f}')

    if TIENE_SCIPY:
        arr = np.array(valores)
        print(f'  asimetria (skewness) = {stats.skew(arr):.3f}  '
              f'({"cola larga a la derecha (valores altos atipicos)" if stats.skew(arr) > 1 else "cola larga a la izquierda" if stats.skew(arr) < -1 else "razonablemente simetrica"})')
        print(f'  curtosis = {stats.kurtosis(arr):.3f}  '
              f'({"mas \"puntiaguda\" que una normal, con colas pesadas" if stats.kurtosis(arr) > 1 else "forma cercana a una normal" if abs(stats.kurtosis(arr)) < 1 else "mas \"achatada\" que una normal"})')


def evaluar_normalidad(nombre, valores):
    if not TIENE_SCIPY:
        print(f'\n(scipy no instalado -- pip install scipy numpy para el test de normalidad de {nombre})')
        return

    print(f'\n--- Normalidad de {nombre} ---')
    n = len(valores)
    arr = np.array(valores)

    # OJO: con miles/millones de filas, los tests formales de
    # normalidad (Shapiro, D'Agostino) son extremadamente sensibles --
    # CUALQUIER desvio minimo da "no es normal" con un dataset grande,
    # aunque la forma sea practicamente normal a ojo. Por eso el test
    # formal se hace sobre una MUESTRA acotada, y se complementa con
    # skewness/kurtosis (arriba) que sí son informativos a cualquier n.
    muestra = arr if n <= 5000 else np.random.choice(arr, 5000, replace=False)
    estadistico, p_valor = stats.shapiro(muestra)
    print(f'  Shapiro-Wilk sobre muestra de {len(muestra):,} filas: estadistico={estadistico:.4f}, p-valor={p_valor:.6f}')
    if p_valor < 0.05:
        print('  -> Rechaza normalidad (esperable en datos de facturacion: '
              'suelen ser asimetricos, con muchas ventas chicas y pocas muy grandes).')
    else:
        print('  -> No se rechaza normalidad en la muestra.')
    print('  Nota: en variables de facturacion/ventas, NO ser normal es lo tipico y esperado '
          '(la distribucion suele ser log-normal: muchos importes chicos, pocos muy grandes). '
          'Esto no es un problema de los datos, es la forma real del negocio.')


def detectar_outliers_iqr(nombre, valores, filas_crudas=None, campo_valor='Importe'):
    print(f'\n--- Outliers de {nombre} (metodo IQR) ---')
    ordenados = sorted(valores)
    n = len(ordenados)
    q1 = ordenados[int(n * 0.25)]
    q3 = ordenados[int(n * 0.75)]
    iqr = q3 - q1
    limite_inf = q1 - 1.5 * iqr
    limite_sup = q3 + 1.5 * iqr

    outliers_idx = [i for i, v in enumerate(valores) if v < limite_inf or v > limite_sup]
    print(f'  Q1={q1:,.2f}  Q3={q3:,.2f}  IQR={iqr:,.2f}')
    print(f'  Rango normal: [{limite_inf:,.2f} , {limite_sup:,.2f}]')
    print(f'  Outliers encontrados: {len(outliers_idx):,} ({len(outliers_idx)/n:.2%} del total)')

    if outliers_idx and filas_crudas:
        print(f'\n  Los 5 valores mas extremos (con contexto):')
        extremos = sorted(outliers_idx, key=lambda i: abs(valores[i]), reverse=True)[:5]
        for i in extremos:
            r = filas_crudas[i]
            print(f'    {campo_valor}={valores[i]:,.2f}  |  cliente={r.get("Razon Social CF","?")}  '
                  f'articulo={r.get("articu","?")}  fecha={r.get("ClaveFecha","?")}')


def chequear_inconsistencias(filas_crudas):
    print('\n--- Inconsistencias logicas ---')

    negativos = [r for r in filas_crudas if float(r.get('Importe', 0) or 0) < 0]
    print(f'  Filas con Importe negativo: {len(negativos):,} '
          f'(puede ser legitimo -- notas de credito o ajustes -- pero vale la pena confirmarlo)')

    cant_cero_importe_pos = [r for r in filas_crudas
                              if float(r.get('Cantid', 0) or 0) == 0 and float(r.get('Importe', 0) or 0) != 0]
    print(f'  Filas con Cantidad=0 pero Importe distinto de 0: {len(cant_cero_importe_pos):,} '
          f'(revisar -- puede ser un servicio/ajuste sin unidades, o un error de carga)')

    sin_cliente = [r for r in filas_crudas if not r.get('Razon Social CF', '').strip()]
    print(f'  Filas sin cliente final identificado: {len(sin_cliente):,}')

    sin_ejecutivo = [r for r in filas_crudas if not r.get('Ejecutivo de Cuenta', '').strip()]
    print(f'  Filas sin ejecutivo de cuenta asignado: {len(sin_ejecutivo):,} '
          f'(estas filas quedan invisibles en cualquier analisis por ejecutivo)')

    familias1 = Counter(r.get('Familia1', '(vacio)') for r in filas_crudas)
    print(f'\n  Distribucion por Familia1 (rubro) en este archivo:')
    for familia, cant in familias1.most_common(10):
        print(f'    {familia}: {cant:,} filas')


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'data/facturacion_detalle.csv'
    print(f'Analizando: {path}\n')

    importes, cantidades, filas_crudas = cargar_importes(path)
    if not importes:
        print('No se encontraron filas de Factura en el archivo.')
        return

    describir('Importe', importes)
    describir('Cantidad', cantidades)

    evaluar_normalidad('Importe', importes)

    detectar_outliers_iqr('Importe', importes, filas_crudas, 'Importe')
    detectar_outliers_iqr('Cantidad', cantidades, filas_crudas, 'Cantid')

    chequear_inconsistencias(filas_crudas)

    print('\n=== Fin del analisis ===')


if __name__ == '__main__':
    main()
