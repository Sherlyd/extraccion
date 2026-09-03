# Reportes diarios — Piletas

Fase 1 del proyecto: base de datos propia + roles + informe diario por
mail. El dashboard web queda para una etapa siguiente, separada.

## Antes de correr esto — checklist

1. **Agregar 2 campos a la extracción de Qlik** (ver detalle abajo):
   rubro/familia del producto y Ejecutivo de Cuenta. Sin esto, el
   filtrado por rol no puede funcionar.
2. **Completar `config.py`** con los datos SMTP reales (servidor,
   usuario, contraseña — mejor como variable de entorno que hardcodeada
   en el archivo).
3. **Cargar los usuarios reales** en la tabla `usuarios` (ver sección
   "Cargar usuarios" abajo) — reemplazando los de prueba.
4. **Confirmar el valor exacto** que usa Qlik para identificar el rubro
   Piletas en el campo Familia1 (puede ser "PILETAS", "Piletas", un
   código, etc.) y ajustar `config.RUBROS_ACTIVOS` acorde.

## 1. Agregar los campos faltantes a la extracción

El detalle de facturación que ya extraés no trae el rubro del producto
ni el vendedor — son imprescindibles para el modelo de roles. En tu
proyecto `qlik-extractor`:

```bash
npm run list-fields
```

Buscá el nombre exacto del campo de rubro/familia (probablemente
`Familia1`) y confirmá `Ejecutivo de Cuenta`. Agregalos a las
dimensiones de `extract.js`, en las tres extracciones que correspondan
(facturación, pedidos, cartera):

```javascript
dimensions: [..., 'Familia1', 'Ejecutivo de Cuenta'],
```

## 2. Instalar dependencias

Este proyecto solo usa la librería estándar de Python (sqlite3, smtplib,
csv) — no hace falta instalar nada adicional.

## 3. Crear la base de datos

```bash
python db.py
```

Esto crea `db/reportes.db` con todas las tablas. Se puede correr las
veces que sea, no borra datos.

## 4. Cargar usuarios

Por ahora no hay una pantalla para esto — se inserta directo en SQL.
Ejemplo con los 3 roles que describiste:

```python
from db import get_connection
conn = get_connection()
conn.execute('''INSERT INTO usuarios (nombre, email, rol, sucursal, rubro, ejecutivo_cuenta) VALUES
    ('Nombre Gerente General', 'gerente@johnsonacero.com', 'gerente_general', NULL, NULL, NULL),
    ('Nombre Gerente Sucursal', 'gerente.sucursal@johnsonacero.com', 'gerente_sucursal', 'Paraná', 'PILETAS', NULL),
    ('Nombre Vendedor', 'vendedor@johnsonacero.com', 'vendedor', 'Paraná', 'PILETAS', 'Nombre Exacto En Qlik')
''')
conn.commit()
```

La regla es: dejar en `NULL` cualquier campo donde el usuario no deba
tener restricción. El gerente general no tiene ninguna restricción; el
gerente de sucursal tiene sucursal + rubro; el vendedor suma además su
propio nombre de ejecutivo de cuenta (debe coincidir EXACTO con como
aparece en Qlik).

## 5. El flujo diario completo

```bash
python run_diario.py
```

Esto: carga los CSV más recientes del extractor de Node a la base,
calcula las métricas de cada usuario ya filtradas por su rol, y envía
el mail. Pensado para programarse con el Task Scheduler de Windows,
corriendo justo después del extractor de Node cada mañana.

Orden en el Task Scheduler:
1. `node extract.js` (en la carpeta de qlik-extractor)
2. `python run_diario.py` (en esta carpeta)

## Estructura

- `db/schema.sql` — las tablas: datos de negocio + usuarios/roles +
  umbrales + log de cargas.
- `db.py` — conexión y creación de la base.
- `cargar_datos.py` — lee los CSV del extractor y los carga (recarga
  completa cada vez, no incremental).
- `roles.py` — el motor de reglas: dado un usuario, arma el filtro SQL
  que determina qué puede ver. Agregar un rol nuevo es solo insertar
  una fila en `usuarios`, no tocar código.
- `metricas.py` — cálculos: facturación por mes, comparación contra
  promedio histórico, tops, detección de alertas por umbral.
- `email_informe.py` — arma el HTML del informe y lo envía por SMTP.
- `run_diario.py` — orquesta todo el flujo.

## Qué falta para las próximas iteraciones

- **Comparación interanual real** (mes actual vs. mismo mes del año
  pasado) — ahora mismo comparo contra el promedio de todos los meses
  cargados, que es un proxy razonable mientras no haya un año completo
  de historia acumulada en la base.
- **Umbrales configurables por usuario/rubro** desde la tabla
  `umbrales` (la tabla ya existe en el esquema, falta conectarla al
  cálculo de alertas en vez de usar el valor único de `config.py`).
- **Drill-down / "de dónde sale este número"** — eso vive en el
  dashboard web (etapa siguiente), no en el mail.
- **Migración a Postgres** cuando el dashboard necesite usuarios
  concurrentes — la lógica de `roles.py` y `metricas.py` no cambia,
  solo el driver de conexión en `db.py`.
