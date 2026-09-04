# explorar_jerarquia.py
# Muestra la facturacion real de Piletas agrupada por Centro -> Zona ->
# Sucursal, para elegir valores reales al crear usuarios de prueba (en
# vez de inventar nombres que capaz no tienen ninguna venta real).
#
# Uso: python explorar_jerarquia.py

from db import get_connection

conn = get_connection()

print("=== Facturacion Piletas por Centro de Distribucion ===\n")
centros = conn.execute("""
    SELECT centro_distribucion, SUM(importe_neto) as total, COUNT(*) as filas
    FROM facturacion
    WHERE rubro = 'VENTA PILETAS'
    GROUP BY centro_distribucion
    ORDER BY total DESC
""").fetchall()
for c in centros:
    print(f"  {c['centro_distribucion'] or '(sin dato)':20s}  ${c['total']:>15,.0f}   ({c['filas']} filas)")

print("\n=== Top 10 Zonas (dentro de cualquier centro) ===\n")
zonas = conn.execute("""
    SELECT centro_distribucion, zona, SUM(importe_neto) as total, COUNT(*) as filas
    FROM facturacion
    WHERE rubro = 'VENTA PILETAS'
    GROUP BY centro_distribucion, zona
    ORDER BY total DESC
    LIMIT 10
""").fetchall()
for z in zonas:
    print(f"  [{z['centro_distribucion']}] {z['zona'] or '(sin dato)':30s}  ${z['total']:>15,.0f}   ({z['filas']} filas)")

print("\n=== Top 10 Sucursales (dentro de cualquier zona) ===\n")
sucursales = conn.execute("""
    SELECT centro_distribucion, zona, sucursal, SUM(importe_neto) as total, COUNT(*) as filas
    FROM facturacion
    WHERE rubro = 'VENTA PILETAS'
    GROUP BY centro_distribucion, zona, sucursal
    ORDER BY total DESC
    LIMIT 10
""").fetchall()
for s in sucursales:
    print(f"  [{s['centro_distribucion']}/{s['zona']}] {s['sucursal'] or '(sin dato)':20s}  ${s['total']:>15,.0f}   ({s['filas']} filas)")

conn.close()
