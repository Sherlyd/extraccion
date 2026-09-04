# config.py

DB_PATH = './db/reportes.db'

# Carpeta donde el extractor de Node (qlik-extractor) deja los CSV
DATA_DIR = './data'
FACTURACION_CSV = 'facturacion_detalle.csv'
PEDIDOS_CSV = 'pedidos_detalle.csv'
CARTERA_CSV = 'cartera_pendiente.csv'

# Rubro con el que arrancamos (los valores exactos que usa Qlik en el
# campo Familia1/rubro para identificar Piletas -- confirmar con
# list-fields / los valores reales que aparezcan al cargar datos).
RUBROS_ACTIVOS = ['VENTA PILETAS']  # valor real confirmado del campo Familia1 en Qlik

# --- SMTP para el mail diario ---
SMTP_HOST = 'smtp.office365.com'   # ajustar segun el proveedor de correo de la empresa
SMTP_PORT = 587
SMTP_USER = ''                     # completar
SMTP_PASSWORD = ''                 # completar (mejor: variable de entorno, no hardcodeado)
EMAIL_FROM = 'reportes@johnsonacero.com'

# --- Umbral por defecto si no hay uno especifico cargado en la tabla umbrales ---
DESVIO_PCT_ALERTA_DEFAULT = 0.15  # 15%
