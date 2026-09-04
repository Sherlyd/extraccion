# server.py
# Punto de entrada para produccion. app.py sigue sirviendo para probar
# rapido en tu compu (python app.py, servidor de desarrollo de Flask),
# pero para dejarlo corriendo de verdad -- disponible para otras
# personas de la empresa, de forma estable -- se usa este archivo con
# waitress, un servidor WSGI real (Flask avisa explicitamente que su
# servidor de desarrollo no es apto para esto).
#
# Uso: python server.py
#
# Queda escuchando en el puerto 8080 de TODAS las interfaces de red de
# la maquina (0.0.0.0), no solo localhost -- asi otras personas de la
# oficina pueden entrar desde su propia compu a http://IP-DE-ESTA-PC:8080

import os
from waitress import serve
from app import app

HOST = os.environ.get('DASHBOARD_HOST', '0.0.0.0')
PORT = int(os.environ.get('DASHBOARD_PORT', '8080'))

if __name__ == '__main__':
    print(f'Sirviendo el dashboard en http://{HOST}:{PORT}  (Ctrl+C para detener)')
    serve(app, host=HOST, port=PORT, threads=4)
