# metricas.py
# Calcula las metricas del informe diario a partir de filas ya filtradas
# por roles.py (o sea, ya recortadas a lo que ese usuario puede ver).

from collections import defaultdict
from datetime import datetime
import statistics


def _mes(fecha_str):
    return fecha_str[:7]  # 'YYYY-MM-DD' -> 'YYYY-MM'


def facturacion_por_mes(filas_facturacion):
    """Suma importe_neto por mes. filas_facturacion: filas de la tabla
    facturacion (sqlite3.Row), ya filtradas por rol."""
    por_mes = defaultdict(float)
    for f in filas_facturacion:
        por_mes[_mes(f['fecha'])] += f['importe_neto'] or 0
    return dict(sorted(por_mes.items()))


def comparacion_mes_actual_vs_promedio_anual(por_mes):
    """Compara el mes mas reciente cargado contra el promedio de los
    meses del año anterior a ese, para saber si viene arriba o abajo
    de lo tipico. Devuelve None si no hay suficiente historia."""
    if len(por_mes) < 2:
        return None

    meses = list(por_mes.keys())
    mes_actual = meses[-1]
    historicos = [por_mes[m] for m in meses[:-1]]
    promedio_historico = statistics.mean(historicos)

    valor_actual = por_mes[mes_actual]
    variacion = (valor_actual - promedio_historico) / promedio_historico if promedio_historico else 0

    return {
        'mes_actual': mes_actual,
        'valor_actual': valor_actual,
        'promedio_historico': promedio_historico,
        'variacion_pct': variacion,
    }


def top_n(filas_facturacion, campo, n=5):
    """Ranking simple por un campo (ej. 'articulo', 'distribuidor_nombre')."""
    acumulado = defaultdict(float)
    for f in filas_facturacion:
        clave = f[campo] or '(sin dato)'
        acumulado[clave] += f['importe_neto'] or 0
    return sorted(acumulado.items(), key=lambda x: x[1], reverse=True)[:n]


def detectar_alertas(comparacion, umbral_pct):
    """A partir del resultado de comparacion_mes_actual_vs_promedio_anual,
    arma la lista de alertas a incluir en el mail (vacia si no hay nada
    fuera de umbral)."""
    if not comparacion:
        return []

    alertas = []
    var = comparacion['variacion_pct']
    if abs(var) >= umbral_pct:
        direccion = 'por encima' if var > 0 else 'por debajo'
        alertas.append(
            f"La facturación de {comparacion['mes_actual']} está {abs(var):.1%} "
            f"{direccion} del promedio histórico — vale la pena revisar el detalle."
        )
    return alertas


def cartera_pendiente_resumen(filas_cartera):
    total = sum(f['total_pendiente'] or 0 for f in filas_cartera)
    bloqueado_onf = sum(f['total_pendiente'] or 0 for f in filas_cartera if f['onf_activa'] == 'SÍ')
    return {'total': total, 'bloqueado_onf': bloqueado_onf}


def facturacion_por_anio(filas_facturacion):
    """Vista MACRO: total facturado por año. Punto de entrada del
    drill-down temporal -- de aca se navega hacia un año puntual."""
    por_anio = defaultdict(float)
    for f in filas_facturacion:
        anio = f['fecha'][:4]
        por_anio[anio] += f['importe_neto'] or 0
    return dict(sorted(por_anio.items()))


def anio_vs_anterior(filas_facturacion, anio):
    """Vista MICRO: facturacion mes a mes de 'anio' comparada contra el
    mismo mes del año anterior. Se llega aca haciendo drill-down desde
    facturacion_por_anio()."""
    anio = str(anio)
    anio_anterior = str(int(anio) - 1)

    actual = defaultdict(float)
    anterior = defaultdict(float)
    for f in filas_facturacion:
        a, m = f['fecha'][:4], f['fecha'][5:7]
        if a == anio:
            actual[m] += f['importe_neto'] or 0
        elif a == anio_anterior:
            anterior[m] += f['importe_neto'] or 0

    meses = [f'{i:02d}' for i in range(1, 13)]
    filas = []
    for m in meses:
        v_actual = actual.get(m, 0)
        v_anterior = anterior.get(m)
        variacion = ((v_actual - v_anterior) / v_anterior) if v_anterior else None
        filas.append({
            'mes': m, 'actual': v_actual, 'anterior': v_anterior or 0, 'variacion_pct': variacion,
        })
    return filas


def facturacion_por_dimension(filas_facturacion, campo, n=None):
    """Generico: agrupa facturacion por cualquier campo de jerarquia
    (centro_distribucion, zona, sucursal). Es el mismo patron de
    macro-a-micro que facturacion_por_anio, aplicado a geografia en vez
    de tiempo -- se usa para armar cada escalon del drill-down."""
    acumulado = defaultdict(float)
    for f in filas_facturacion:
        clave = f[campo] or '(sin dato)'
        acumulado[clave] += f['importe_neto'] or 0
    resultado = sorted(acumulado.items(), key=lambda x: x[1], reverse=True)
    return resultado[:n] if n else resultado
