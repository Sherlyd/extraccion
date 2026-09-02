# config.py
# Configuracion central: rutas de los archivos exportados de Qlik y
# parametros de los cruces/analisis.
#
# Los nombres de archivo que exporta Qlik cambian cada vez (traen un ID
# random), asi que cada vez que baje datos nuevos, debo actualizar estas rutas
# (o simplemente renombra los archivos nuevos con estos mismos nombres
# antes de correr el script).

DATA_DIR = "./qlik-analisis/data/"

# --- Archivos de entrada ---
# Detalle de facturacion: una fila por linea de factura/NC (Tipo Comp,
# Fecha de Alta, Distr., Cons. Final, Articulo, Importe, etc.)
FACTURACION_DETALLE = 'facturacion_detalle.xlsx'

# Cartera pendiente de cobro ("Detalle Colchon"): Nro Pedido, Estado
# Pedido, Razon Social Distr, ONF Activa, Total Pendiente M$, etc.
CARTERA_PENDIENTE = 'cartera_pendiente.xlsx'

# Ranking de distribuidores: Razon Social Distr, M$ Fact., Fact. %,
# Cant. Unidades Facturadas, # Vend.
TOP_DISTRIBUIDORES = 'top_distribuidores.xlsx'

# --- Parametros de los cruces ---

# Si la cartera pendiente de un cliente supera este % de lo que factura,
# se marca como riesgo alto en el cruce cartera-vs-facturacion.
UMBRAL_RIESGO_CARTERA = 0.5  # 50%

# Cuantos clientes/distribuidores mostrar en cada ranking del informe.
TOP_N = 20

# Un mes se marca como "atipico" en la evolucion mensual si su desvio
# respecto al promedio supera este numero de desvios estandar.
Z_SCORE_OUTLIER = 1.5

# --- Salida ---
OUTPUT_PATH = './output/informe_qlik.xlsx'
