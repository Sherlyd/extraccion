# metricas.py
# Calcula las metricas del dashboard y del mail diario, a partir de
# filas ya filtradas por roles.py. Cada comparacion deja explicito
# contra que periodo exacto se esta comparando -- nunca "promedio
# historico" a secas.

from collections import defaultdict
import statistics

MESES_NOMBRE = {
    '01': 'Ene', '02': 'Feb', '03': 'Mar', '04': 'Abr', '05': 'May', '06': 'Jun',
    '07': 'Jul', '08': 'Ago', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dic',
}


def _mes_legible(clave_yyyy_mm):
    """'2026-08' -> 'Ago 2026'"""
    anio, mes = clave_yyyy_mm.split('-')
    return f"{MESES_NOMBRE.get(mes, mes)} {anio}"


def facturacion_por_mes(filas_facturacion):
    """Suma importe_neto por mes (clave 'YYYY-MM'), sobre TODOS los años
    presentes en las filas recibidas."""
    por_mes = defaultdict(float)
    for f in filas_facturacion:
        por_mes[f['fecha'][:7]] += f['importe_neto'] or 0
    return dict(sorted(por_mes.items()))


def comparacion_periodo(filas_facturacion, anio_filtro=None, mes_filtro=None):
    """Compara un periodo contra su referencia, dejando SIEMPRE explicito
    contra que se compara. Segun los filtros recibidos:

    - Con anio Y mes: compara ese mes puntual contra el MISMO mes del
      año anterior (interanual).
    - Con solo anio: compara el ultimo mes con datos de ese año contra
      el promedio de los demas meses de ESE MISMO año.
    - Sin filtros: compara el ultimo mes con datos (de cualquier año)
      contra el promedio de todos los meses anteriores disponibles.

    Devuelve None si no hay suficiente historia para comparar. Incluye
    los campos legacy (mes_actual, valor_actual, promedio_historico,
    variacion_pct) para no romper email_informe.py, ademas de los
    nuevos campos *_legible para mostrar el periodo explicito.
    """
    por_mes = facturacion_por_mes(filas_facturacion)
    if not por_mes:
        return None

    if anio_filtro and mes_filtro:
        clave = f"{anio_filtro}-{int(mes_filtro):02d}"
        clave_anterior = f"{int(anio_filtro) - 1}-{int(mes_filtro):02d}"
        valor_actual = por_mes.get(clave)
        if valor_actual is None:
            return None
        valor_comparado = por_mes.get(clave_anterior)
        variacion = ((valor_actual - valor_comparado) / valor_comparado) if valor_comparado else None
        return {
            'tipo': 'interanual',
            'mes_actual': clave,
            'valor_actual': valor_actual,
            'promedio_historico': valor_comparado or 0,
            'variacion_pct': variacion if variacion is not None else 0,
            'hay_comparacion': valor_comparado is not None,
            'periodo_actual_legible': _mes_legible(clave),
            'periodo_comparado_legible': (
                _mes_legible(clave_anterior) if valor_comparado is not None
                else f'sin datos de {_mes_legible(clave_anterior)}'
            ),
        }

    if anio_filtro:
        meses_anio = sorted(m for m in por_mes if m.startswith(str(anio_filtro)))
        if len(meses_anio) < 2:
            return None
        mes_actual = meses_anio[-1]
        meses_promedio = meses_anio[:-1]
    else:
        # Ventana movil de los ultimos 12 meses, NUNCA todo el historial
        # disponible -- con datos desde 2015, promediar "todo lo que hay"
        # diluiria el punto de comparacion con años irrelevantes para
        # saber como viene el mes actual. Se compara contra el
        # comportamiento reciente, no contra una decada entera.
        meses = sorted(por_mes.keys())
        if len(meses) < 2:
            return None
        mes_actual = meses[-1]
        meses_promedio = meses[max(0, len(meses) - 13):-1]  # hasta 12 meses previos

    promedio = statistics.mean(por_mes[m] for m in meses_promedio)
    valor_actual = por_mes[mes_actual]
    variacion = (valor_actual - promedio) / promedio if promedio else 0

    return {
        'tipo': 'promedio',
        'mes_actual': mes_actual,
        'valor_actual': valor_actual,
        'promedio_historico': promedio,
        'variacion_pct': variacion,
        'hay_comparacion': True,
        'periodo_actual_legible': _mes_legible(mes_actual),
        'periodo_comparado_legible': (
            f"promedio {_mes_legible(meses_promedio[0])}\u2013{_mes_legible(meses_promedio[-1])} "
            f"({len(meses_promedio)} {'mes' if len(meses_promedio) == 1 else 'meses'})"
        ),
    }


# Alias con el nombre viejo, para no romper codigo existente que lo llama.
def comparacion_mes_actual_vs_promedio_anual(por_mes_o_filas, *_args, **_kwargs):
    if isinstance(por_mes_o_filas, dict):
        # Alguien paso el resultado de facturacion_por_mes() directo, como antes.
        meses = sorted(por_mes_o_filas.keys())
        if len(meses) < 2:
            return None
        mes_actual = meses[-1]
        meses_promedio = meses[:-1]
        promedio = statistics.mean(por_mes_o_filas[m] for m in meses_promedio)
        valor_actual = por_mes_o_filas[mes_actual]
        variacion = (valor_actual - promedio) / promedio if promedio else 0
        return {
            'tipo': 'promedio', 'mes_actual': mes_actual, 'valor_actual': valor_actual,
            'promedio_historico': promedio, 'variacion_pct': variacion, 'hay_comparacion': True,
            'periodo_actual_legible': _mes_legible(mes_actual),
            'periodo_comparado_legible': (
                f"promedio {_mes_legible(meses_promedio[0])}\u2013{_mes_legible(meses_promedio[-1])} "
                f"({len(meses_promedio)} {'mes' if len(meses_promedio) == 1 else 'meses'})"
            ),
        }
    return comparacion_periodo(por_mes_o_filas)


def facturacion_multianio_mensual(filas_facturacion, campo_valor='importe_neto'):
    """Un array de 12 posiciones (Ene..Dic) por cada año presente en los
    datos -- para graficar todos los años superpuestos en una sola linea
    de tiempo. campo_valor permite elegir pesos o unidades."""
    datos = defaultdict(lambda: [0.0] * 12)
    for f in filas_facturacion:
        anio = f['fecha'][:4]
        mes_idx = int(f['fecha'][5:7]) - 1
        datos[anio][mes_idx] += f[campo_valor] or 0
    return dict(sorted(datos.items()))


def anios_disponibles(filas_facturacion):
    return sorted({f['fecha'][:4] for f in filas_facturacion})


def top_n(filas_facturacion, campo, campo_valor='importe_neto', n=5):
    """Ranking simple por un campo (ej. 'distribuidor_nombre'). campo_valor
    permite elegir si se suma en pesos (importe_neto) o en unidades
    (cantidad) -- el selector pe$/ctd."""
    acumulado = defaultdict(float)
    for f in filas_facturacion:
        clave = f[campo] or '(sin dato)'
        acumulado[clave] += f[campo_valor] or 0
    return sorted(acumulado.items(), key=lambda x: x[1], reverse=True)[:n]


def clientes_de_ejecutivo(filas_facturacion, ejecutivo, campo_valor='importe_neto'):
    """Cartera de clientes de un ejecutivo puntual: por cada cliente,
    cuanto factura en pesos Y en unidades (las dos siempre disponibles,
    se elige cual ordena el ranking con campo_valor). Tambien devuelve
    en que centro/zona opera, tomado de sus propias filas de venta."""
    filas_ej = [f for f in filas_facturacion if f['ejecutivo_cuenta'] == ejecutivo]

    acumulado = defaultdict(lambda: {'importe_neto': 0.0, 'cantidad': 0.0})
    ubicaciones = set()
    for f in filas_ej:
        clave = f['cliente_final_nombre'] or f['distribuidor_nombre'] or '(sin dato)'
        acumulado[clave]['importe_neto'] += f['importe_neto'] or 0
        acumulado[clave]['cantidad'] += f['cantidad'] or 0
        if f['centro_distribucion'] or f['zona']:
            ubicaciones.add((f['centro_distribucion'] or '(sin dato)', f['zona'] or '(sin dato)'))

    clientes = [
        {'cliente': cliente, 'importe_neto': d['importe_neto'], 'cantidad': d['cantidad']}
        for cliente, d in acumulado.items()
    ]
    clientes.sort(key=lambda x: x[campo_valor], reverse=True)
    return clientes, sorted(ubicaciones)


def top_articulos_detalle(filas_facturacion, n=10):
    """Como top_n pero identifica si el articulo es un accesorio/segunda
    (via Familia4) en vez de dejarlo ambiguo -- antes 'VENTA PILETAS' no
    distinguia una pileta de un accesorio de pileta."""
    acumulado = defaultdict(lambda: {'importe': 0.0, 'familias4': set()})
    for f in filas_facturacion:
        clave = f['articulo'] or '(sin dato)'
        acumulado[clave]['importe'] += f['importe_neto'] or 0
        acumulado[clave]['familias4'].add(f['familia4'] or '(sin dato)')

    resultado = []
    for articulo, datos in acumulado.items():
        es_accesorio = any(fam in ('ACCESORIOS', 'SEGUNDA') for fam in datos['familias4'])
        resultado.append({
            'articulo': articulo,
            'importe': datos['importe'],
            'categoria': 'Accesorio/Segunda' if es_accesorio else 'Producto principal',
            'es_accesorio': es_accesorio,
        })
    resultado.sort(key=lambda x: x['importe'], reverse=True)
    return resultado[:n]


def detectar_alertas(comparacion, umbral_pct):
    """Genera la alerta si la variacion supera el umbral, dejando el
    periodo comparado explicito en el propio texto."""
    if not comparacion or not comparacion.get('hay_comparacion', True):
        return []

    alertas = []
    var = comparacion['variacion_pct']
    if abs(var) >= umbral_pct:
        direccion = 'por encima' if var > 0 else 'por debajo'
        alertas.append(
            f"{comparacion['periodo_actual_legible']} está {abs(var):.1%} {direccion} de "
            f"{comparacion['periodo_comparado_legible']}."
        )
    return alertas


def cartera_pendiente_resumen(filas_cartera):
    total = sum(f['total_pendiente'] or 0 for f in filas_cartera)
    bloqueado_onf = sum(f['total_pendiente'] or 0 for f in filas_cartera if f['onf_activa'] == 'SÍ')
    return {'total': total, 'bloqueado_onf': bloqueado_onf}


def _fmt_money(v):
    return f'${v:,.0f}'.replace(',', '.')


def generar_narrativa(comparacion, alertas, cartera):
    """Traduce los numeros a un parrafo en lenguaje simple -- pensado
    para alguien que no va a interpretar un numero suelto ni un
    porcentaje sin contexto. Esto es lo que arma el 'diagnostico en
    3 lineas' del mail automatico."""
    partes = []

    if not comparacion:
        partes.append('Todavía no hay suficiente historial cargado para comparar este período.')
    elif not comparacion.get('hay_comparacion', True):
        partes.append(f"En {comparacion['periodo_actual_legible']} se facturó "
                       f"{_fmt_money(comparacion['valor_actual'])}, sin un período anterior para comparar.")
    else:
        direccion = 'por encima' if comparacion['variacion_pct'] >= 0 else 'por debajo'
        partes.append(
            f"En {comparacion['periodo_actual_legible']} se facturó {_fmt_money(comparacion['valor_actual'])}, "
            f"un {abs(comparacion['variacion_pct']):.0%} {direccion} de lo habitual reciente."
        )

    if alertas:
        partes.append('Atención: ' + ' '.join(alertas))
    else:
        partes.append('No se registraron desvíos importantes respecto a lo habitual.')

    if cartera['total'] > 0:
        partes.append(f"Quedan {_fmt_money(cartera['total'])} pendientes de fabricar o entregar.")

    return ' '.join(partes)


def facturacion_por_dimension(filas_facturacion, campo, n=None):
    """Generico: agrupa facturacion por cualquier campo de jerarquia
    (centro_distribucion, zona). Se usa para cada escalon del
    drill-down geografico."""
    acumulado = defaultdict(float)
    for f in filas_facturacion:
        clave = f[campo] or '(sin dato)'
        acumulado[clave] += f['importe_neto'] or 0
    resultado = sorted(acumulado.items(), key=lambda x: x[1], reverse=True)
    return resultado[:n] if n else resultado
