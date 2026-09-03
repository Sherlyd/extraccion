# email_informe.py
# Arma el HTML del informe diario para un usuario puntual (ya con sus
# datos filtrados por rol) y lo envia por correo.

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config
import metricas


def _fmt_money(v):
    return f'${v:,.0f}'.replace(',', '.')


def armar_html(usuario, por_mes, comparacion, top_articulos, top_distribuidores,
                cartera, alertas):
    alertas_html = ''
    if alertas:
        items = ''.join(f'<li style="color:#9C0006;">{a}</li>' for a in alertas)
        alertas_html = f'''
        <div style="background:#FFC7CE; padding:12px 16px; border-radius:6px; margin-bottom:20px;">
            <strong>Alertas de hoy</strong>
            <ul style="margin:8px 0 0 0;">{items}</ul>
        </div>'''

    comp_html = ''
    if comparacion:
        signo = '+' if comparacion['variacion_pct'] >= 0 else ''
        comp_html = f'''
        <p><strong>{comparacion['mes_actual']}:</strong> {_fmt_money(comparacion['valor_actual'])}
        ({signo}{comparacion['variacion_pct']:.1%} vs. promedio histórico de
        {_fmt_money(comparacion['promedio_historico'])})</p>'''

    filas_mes = ''.join(
        f'<tr><td style="padding:4px 12px;">{m}</td>'
        f'<td style="padding:4px 12px; text-align:right;">{_fmt_money(v)}</td></tr>'
        for m, v in por_mes.items()
    )

    filas_top_art = ''.join(
        f'<tr><td style="padding:4px 12px;">{a}</td>'
        f'<td style="padding:4px 12px; text-align:right;">{_fmt_money(v)}</td></tr>'
        for a, v in top_articulos
    )

    filas_top_dist = ''.join(
        f'<tr><td style="padding:4px 12px;">{a}</td>'
        f'<td style="padding:4px 12px; text-align:right;">{_fmt_money(v)}</td></tr>'
        for a, v in top_distribuidores
    )

    return f'''
    <html><body style="font-family: Arial, sans-serif; color:#333;">
    <h2 style="color:#1F4E78;">Informe diario — Piletas</h2>
    <p style="color:#888;">Hola {usuario['nombre']}, este es tu resumen del día.</p>

    {alertas_html}

    <h3 style="color:#1F4E78;">Facturación</h3>
    {comp_html}
    <table style="border-collapse:collapse; margin-bottom:20px;">{filas_mes}</table>

    <h3 style="color:#1F4E78;">Top artículos</h3>
    <table style="border-collapse:collapse; margin-bottom:20px;">{filas_top_art}</table>

    <h3 style="color:#1F4E78;">Top distribuidores</h3>
    <table style="border-collapse:collapse; margin-bottom:20px;">{filas_top_dist}</table>

    <h3 style="color:#1F4E78;">Pedidos pendientes de fabricar/entregar</h3>
    <p>Total: {_fmt_money(cartera['total'])} — Bloqueado por ONF: {_fmt_money(cartera['bloqueado_onf'])}</p>
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