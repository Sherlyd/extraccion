# Reportes Piletas

Dashboard + informe diario automático para Johnson Acero, alimentado
por datos extraídos de Qlik Sense. Arquitectura en dos niveles de
detalle sobre Postgres, lista para desplegar en AWS.

## Arquitectura de datos — por qué dos niveles

- **`facturacion_mensual` / `pedidos_mensual`** — agregado por mes,
  con **todo el historial desde 2015**. Pocas filas (miles). Se
  actualiza todos los días con `UPSERT` (no se borra ni se duplica).
  Alimenta comparaciones de período y el gráfico de tendencia
  multi-año. Solo tiene las dimensiones de menor cardinalidad (centro,
  zona, rubro, familia4, ejecutivo) — no cliente/artículo/distribuidor.

- **`facturacion_detalle` / `pedidos_detalle`** — línea por línea, con
  cliente/artículo/distribuidor, pero **solo una ventana reciente**
  (`VENTANA_DETALLE_DIAS`, default 730 días / ~24 meses). Se reemplaza
  completa cada día, pero al ser una ventana acotada, es rápido.
  Alimenta tops, la tabla cruda, y el análisis por entidad cuando la
  entidad es un cliente/artículo/distribuidor específico.

**Consecuencia práctica:** el análisis histórico completo (2015+) está
disponible a nivel centro/zona/ejecutivo/rubro, pero el detalle de
"qué le vendiste a tal cliente" solo cubre la ventana reciente. Es una
decisión deliberada — mantener el detalle completo desde 2015 con
cliente/artículo haría la base tan grande como el problema que
resolvimos.

## Requisitos

- Python 3.12+
- Postgres 14+ (local para desarrollo, RDS en AWS para producción)
- Node.js (para el extractor de Qlik, proyecto aparte `qlik-extractor`)

## Configuración

Copiar `.env.example` como `.env` (o configurar las mismas variables
en el entorno) y completar:

```bash
DATABASE_URL=postgresql://usuario:password@host:5432/nombre_base
DASHBOARD_SECRET_KEY=una-clave-larga-y-aleatoria
SMTP_USER=...
SMTP_PASSWORD=...
```

## Uso local

```bash
pip install -r requirements.txt
python db.py                    # crea las tablas si no existen
python gestionar_usuarios.py crear "Nombre" email@empresa.com "clave" gerente_general
python cargar_datos.py          # carga los CSV que dejó el extractor de Qlik
python app.py                   # dashboard en http://localhost:5000
```

Para producción (o para probar el servidor real):
```bash
python server.py                # usa waitress, no el server de desarrollo
```

## Análisis de calidad de datos

Antes de confiar en los números, correr sobre el CSV recién extraído:
```bash
python analizar_calidad_datos.py data/facturacion_detalle.csv
```
Reporta distribución (media, mediana, asimetría), detecta outliers
(método IQR) con contexto de a qué fila pertenecen, e inconsistencias
lógicas (importes negativos, cantidad=0 con importe≠0, filas sin
ejecutivo asignado, etc).

## Despliegue en AWS

El `Dockerfile` empaqueta la app para correr en App Runner, ECS, o
Elastic Beanstalk (plataforma Docker) — cualquiera de los tres conecta
directo a un repositorio de GitHub y hace build/deploy automático en
cada push, sin necesidad de manejar servidores a mano.

Variables de entorno a configurar en el servicio de AWS: las mismas de
`.env.example`. `DATABASE_URL` normalmente apunta a una instancia RDS
Postgres separada del contenedor de la app.

**Recomendación para empezar simple:** AWS App Runner — se conecta
directo al repo de GitHub, no requiere configurar VPC/load
balancer/etc a mano para un primer despliegue. Si más adelante hace
falta más control (ej. tareas programadas dentro de la misma
infraestructura), se puede migrar a ECS sin cambiar el Dockerfile.

**Importante:** el extractor de Qlik (`qlik-extractor`, proyecto
Node.js aparte) necesita conectividad de red directa al servidor Qlik
on-premise — eso significa que ese proceso puntual (no el dashboard)
tiene que correr desde una máquina con VPN/acceso a la red de la
empresa, no puede correr libremente en cualquier servicio de AWS sin
esa conectividad resuelta primero.

## Estructura

- `db/schema_postgres.sql`, `db.py` — esquema y conexión.
- `cargar_datos.py` — carga con el patrón de dos niveles + upsert en
  lote (`execute_values`, no fila por fila).
- `roles.py` — motor de reglas de acceso por rol/jerarquía.
- `metricas.py` — cálculos: comparaciones de período (siempre con
  período explícito, nunca "promedio histórico" sin decir cuál),
  alertas, desgloses.
- `app.py` — rutas del dashboard: vista general, ejecutivos, tabla
  cruda, análisis por entidad, vista simple (no técnica).
- `run_diario.py`, `email_informe.py` — informe diario automático,
  con narrativa en lenguaje simple y semáforo de color.
- `gestionar_usuarios.py` — alta/baja de usuarios con contraseña
  (hash, nunca texto plano).
- `analizar_calidad_datos.py` — diagnóstico de la calidad del CSV
  antes de cargarlo.
