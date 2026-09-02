# Qlik Análisis

Cruza los distintos exports de Qlik (facturación, cartera pendiente,
ranking de distribuidores) y genera un informe en Excel con tablas
formateadas, un gráfico y las filas de riesgo resaltadas.

## Estructura

- 'config.py' : rutas de archivos y parámetros de los cruces (umbral de
  riesgo, cuántos meses/clientes mostrar, etc.)
- 'loaders.py' : lee cada tipo de export de Qlik y lo limpia (filtra
  filas de "Totales", convierte tipos de dato).
- 'cruces.py' : la lógica de análisis: evolución mensual con detección
  de meses atípicos, ranking de clientes, concentración de
  distribuidores (Pareto), cartera por cliente, y el cruce central de
  riesgo (facturación vs. cartera pendiente).
- 'generar_informe.py' : arma el Excel final.
- 'main.py' : corre todo el flujo.

## Uso

1. Instalar dependencias:
   '''bash
   pip install pandas openpyxl
   '''

2. Poner los 3 archivos de Qlik en la carpeta 'data/', con
   estos nombres exactos (o ajustá las rutas en 'config.py'):
   - 'facturacion_detalle.xlsx' : el detalle de facturación línea por
     línea (el que tiene columnas como Tipo Comp, Fecha de Alta,
     Artículo, Importe).
   - 'cartera_pendiente.xlsx' : el "Detalle Colchón" con la cartera
     pendiente de cobro.
   - 'top_distribuidores.xlsx' : el ranking de distribuidores con
     "M$ Fact." y "Fact. %".

3. Correr:
   '''bash
   python main.py
   '''

4. El informe queda en 'output/informe_qlik.xlsx', con estas hojas:
   - **Resumen** : KPIs generales (total facturado, cartera pendiente,
     % bloqueado por ONF, meses atípicos, clientes en riesgo).
   - **Evolución Mensual** : facturación neta por mes + gráfico +
     marca de meses que se desvían de la tendencia.
   - **Top Clientes** : ranking por facturación neta.
   - **Concentración Distrib.** : análisis de Pareto (cuánto concentran
     los top 5/10/20/50 distribuidores).
   - **Cartera Pendiente** : cartera por cliente, separando lo
     bloqueado por ONF.
   - **Riesgo Cartera** : el cruce principal: facturación vs. cartera
     pendiente por cliente, con las filas de riesgo alto resaltadas en
     rojo.

## agregar cruces

Cada análisis en 'cruces.py' es una función independiente que recibe
DataFrames ya limpios y devuelve un DataFrame. Para agregar uno nuevo:

1. Escribir la función en 'cruces.py' (por ejemplo 'cruce_riesgo_cartera', cruza dos tablas por nombre de cliente).
2. Se debe llamar desde 'main.py'.
3. Agregar una hoja nueva en 'generar_informe.py' con '_write_table()'.

## Conectar esto con la automatización de Qlik

Si en el futuro el script de extracción de Qlik ('qlik-extractor') genera los CSV/Excel automáticamente, se puede encadenar este script después, apuntando 'config.py' a esos
archivos generados, así todo el flujo (extraer de Qlik → cruzar → informe) corre sin intervención manual y solo habría que hacer reflexión sobre los resultados.
