-- schema.sql
-- Base de datos propia: copia fiel de los datos de Qlik + modelo de roles.
-- SQLite para arrancar (cero configuracion). Si mas adelante el dashboard
-- web necesita muchos usuarios concurrentes, esto migra a Postgres sin
-- cambiar la logica, solo el motor.

-- ---------- Datos de negocio (espejo de Qlik) ----------

CREATE TABLE IF NOT EXISTS facturacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,              -- YYYY-MM-DD
    tipo_comp TEXT NOT NULL,          -- FC o NC
    distribuidor_id TEXT,
    distribuidor_nombre TEXT,
    cliente_final_nombre TEXT,
    articulo TEXT,
    rubro TEXT,                       -- Familia1 de Qlik (Piletas, Mesada, Mueblería, ...)
    familia4 TEXT,                    -- Familia4: distingue ACCESORIOS/SEGUNDA del producto principal
    ejecutivo_cuenta TEXT,            -- vendedor
    centro_distribucion TEXT,         -- nivel macro (ej: Parana, Buenos Aires)
    zona TEXT,                        -- nivel intermedio dentro de un centro
    sucursal TEXT,                    -- nivel micro
    cantidad REAL,
    importe REAL,
    importe_neto REAL,                -- ya viene neto de NC desde #Facturacion
    cargado_en TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_fact_fecha ON facturacion(fecha);
CREATE INDEX IF NOT EXISTS idx_fact_rubro ON facturacion(rubro);
CREATE INDEX IF NOT EXISTS idx_fact_ejecutivo ON facturacion(ejecutivo_cuenta);
CREATE INDEX IF NOT EXISTS idx_fact_centro ON facturacion(centro_distribucion);
CREATE INDEX IF NOT EXISTS idx_fact_zona ON facturacion(zona);
CREATE INDEX IF NOT EXISTS idx_fact_sucursal ON facturacion(sucursal);

CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nro_pedido TEXT NOT NULL,
    distribuidor_nombre TEXT,
    articulo TEXT,
    rubro TEXT,
    ejecutivo_cuenta TEXT,
    centro_distribucion TEXT,
    zona TEXT,
    sucursal TEXT,
    cantidad REAL,
    cargado_en TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ped_rubro ON pedidos(rubro);

CREATE TABLE IF NOT EXISTS cartera_pendiente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nro_pedido TEXT,
    distribuidor_nombre TEXT,
    estado_pedido TEXT,
    onf_activa TEXT,
    rubro TEXT,
    ejecutivo_cuenta TEXT,
    centro_distribucion TEXT,
    zona TEXT,
    sucursal TEXT,
    total_pendiente REAL,
    cargado_en TEXT DEFAULT (datetime('now'))
);

-- ---------- Modelo de roles y acceso ----------
-- Cada usuario tiene, ademas de su rol, un "alcance": los valores de
-- sucursal/rubro/ejecutivo_cuenta que puede ver. NULL = sin restriccion
-- en esa dimension (por ejemplo, el gerente general tiene las 3 en NULL).

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL,                -- gerente_general | gerente_sucursal | vendedor
    centro_distribucion TEXT,         -- NULL = todos los centros (ej: Gerente General)
    zona TEXT,                        -- NULL = todas las zonas de su centro
    sucursal TEXT,                    -- NULL = todas las sucursales de su zona
    rubro TEXT,                       -- NULL = todos
    ejecutivo_cuenta TEXT,            -- NULL = todos (solo aplica a rol vendedor)
    activo INTEGER DEFAULT 1
);

-- ---------- Configuracion de umbrales de alerta ----------

CREATE TABLE IF NOT EXISTS umbrales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rubro TEXT NOT NULL,
    metrica TEXT NOT NULL,            -- ej: 'facturacion_mensual'
    desvio_pct_alerta REAL NOT NULL   -- ej: 0.15 = alerta si se desvia +/-15% del promedio
);

-- ---------- Trazabilidad de cargas ----------

CREATE TABLE IF NOT EXISTS log_extracciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ejecutado_en TEXT DEFAULT (datetime('now')),
    archivo TEXT,
    filas_cargadas INTEGER,
    estado TEXT,                      -- ok | error
    detalle TEXT
);
