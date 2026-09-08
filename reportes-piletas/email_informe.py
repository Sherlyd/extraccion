# email_informe.py
# Arma y envia el mail diario. Pensado para alguien que NO va a
# interpretar numeros sueltos: la conclusion en palabras va primero,
# los indicadores usan semaforo de color (verde/amarillo/rojo), y no
# hay ninguna interaccion esperada del lector (nada de filtros ni
# clics para entender el estado del dia).

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config
import metricas


def _fmt_money(v):
    return f'${v:,.0f}'.replace(',', '.')


def _color_semaforo(comparacion, umbral):
    """Verde: dentro de lo esperado. Amarillo: se acerca al umbral.
    Rojo: supera el umbral (para bien o para mal, ambos ameritan
    mirarlo)."""
    if not comparacion or not comparacion.get('hay_comparacion', True):
        return '#8CA0AF', '#F3F4F2'  # gris: sin dato para comparar
    desvio = abs(comparacion['variacion_pct'])
    if desvio >= umbral:
        return '#B4472B', '#F6E6E1'  # rojo
    if desvio >= umbral * 0.6:
        return '#C9962E', '#FBF1DE'  # amarillo
    return '#2F7A5C', '#E4F0EA'      # verde


def armar_html(usuario, comparacion, top_articulos, top_distribuidores, cartera, alertas, umbral):
    narrativa = metricas.generar_narrativa(comparacion, alertas, cartera)
    color_borde, color_fondo = _color_semaforo(comparacion, umbral)

    alertas_html = ''
    if alertas:
        items = ''.join(f'<li style="margin-bottom:4px;">{a}</li>' for a in alertas)
        alertas_html = f'''
        <div style="background:#F6E6E1; border-left:4px solid #B4472B; padding:14px 18px; margin:20px 0; font-size:15px; color:#8B2E1C;">
            <strong>Para revisar hoy:</strong>
            <ul style="margin:8px 0 0 0; padding-left:20px;">{items}</ul>
        </div>'''

    filas_top_art = ''.join(
        f'<tr><td style="padding:8px 12px; font-size:14px;">{a["articulo"]}</td>'
        f'<td style="padding:8px 12px; font-size:13px; color:#8CA0AF;">{a["categoria"]}</td>'
        f'<td style="padding:8px 12px; text-align:right; font-size:14px; font-weight:600;">{_fmt_money(a["importe"])}</td></tr>'
        for a in top_articulos
    )

    filas_top_dist = ''.join(
        f'<tr><td style="padding:8px 12px; font-size:14px;">{n}</td>'
        f'<td style="padding:8px 12px; text-align:right; font-size:14px; font-weight:600;">{_fmt_money(v)}</td></tr>'
        for n, v in top_distribuidores
    )

    periodo = comparacion['periodo_actual_legible'] if comparacion else ''

    return f'''
    <html><body style="font-family: Arial, sans-serif; color:#10202E; background:#F3F4F2; margin:0; padding:0;">
    <div style="max-width:600px; margin:0 auto; background:white;">

      <div style="background:#1B2A38; padding:24px 28px; border-bottom:4px solid #B4652B;">
        <div style="color:#8CA0AF; font-size:13px; text-transform:uppercase; letter-spacing:0.05em;">Resumen diario — Piletas</div>
        <div style="color:white; font-size:20px; font-weight:bold; margin-top:4px;">Hola {usuario['nombre']}</div>
        <div style="color:#8CA0AF; font-size:13px; margin-top:2px;">{periodo}</div>
      </div>

      <div style="padding:24px 28px;">

        <div style="background:{color_fondo}; border-left:5px solid {color_borde}; padding:16px 20px; font-size:16px; line-height:1.5;">
          {narrativa}
        </div>

        {alertas_html}

        <div style="margin-top:28px;">
          <div style="font-size:13px; color:#8CA0AF; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;">Pendiente de fabricar / entregar</div>
          <div style="font-size:26px; font-weight:bold;">{_fmt_money(cartera['total'])}</div>
          <div style="font-size:13px; color:#8CA0AF; margin-top:2px;">De eso, {_fmt_money(cartera['bloqueado_onf'])} está bloqueado administrativamente.</div>
        </div>

        <div style="margin-top:28px;">
          <div style="font-size:13px; color:#8CA0AF; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;">Lo que más se vendió</div>
          <table style="width:100%; border-collapse:collapse;">{filas_top_art}</table>
        </div>

        <div style="margin-top:24px;">
          <div style="font-size:13px; color:#8CA0AF; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;">Principales distribuidores</div>
          <table style="width:100%; border-collapse:collapse;">{filas_top_dist}</table>
        </div>

        <div style="margin-top:32px; padding-top:16px; border-top:1px solid #E9EAE6; font-size:12px; color:#8CA0AF;">
          Este es un resumen automático. Si querés ver el detalle completo, entrá al panel web.
        </div>
      </div>
    </div>
    </body></html>'''


def enviar(destinatario, asunto, html):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = asunto
    msg['From'] = config.EMAIL_FROM
    msg['To'] = destinatario
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.sendmail(config.EMAIL_FROM, destinatario, msg.as_string())
