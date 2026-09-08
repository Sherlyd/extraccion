# Dockerfile
# Imagen para desplegar el dashboard en AWS (App Runner, ECS, o
# Elastic Beanstalk con plataforma Docker). Corre con waitress
# (server.py), no con el servidor de desarrollo de Flask.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Estas carpetas las genera/usa la app en runtime, se crean por si
# el contenedor arranca limpio.
RUN mkdir -p data logs

EXPOSE 8080

# DATABASE_URL y DASHBOARD_SECRET_KEY se pasan como variables de
# entorno al correr el contenedor (nunca hardcodeadas en la imagen).
CMD ["python", "server.py"]
