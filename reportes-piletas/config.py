# config.py
# Los valores sensibles (SMTP) salen de variables de entorno --
# listo para AWS, donde se configuran como variables del servicio, no
# hardcodeadas en el codigo. Ver .env.example.

import os

# Carpeta donde el extractor de Node (qlik-extractor) deja los CSV
DATA_DIR = os.environ.get('DATA_DIR', './data')
FACTURACION_CSV = 'facturacion_detalle.csv'
PEDIDOS_CSV = 'pedidos_detalle.csv'
CARTERA_CSV = 'cartera_pendiente.csv'

# Rubro con el que arrancamos (valor real confirmado del campo Familia1 en Qlik)
RUBROS_ACTIVOS = ['VENTA PILETAS']

# --- SMTP para el mail diario ---
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.office365.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'reportes@johnsonacero.com')

# --- Umbral por defecto si no hay uno especifico cargado en la tabla umbrales ---
DESVIO_PCT_ALERTA_DEFAULT = float(os.environ.get('DESVIO_PCT_ALERTA_DEFAULT', '0.15'))
