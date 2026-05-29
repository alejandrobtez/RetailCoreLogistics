"""
api/services/sms_alerts.py — Alertas SMS via Azure Logic Apps
=============================================================================
Cuando prob_fallo > 0.70 (HIGH), llama al webhook HTTP de la Logic App
que dispara el SMS al destinatario.

Configurar en .env:
    LOGIC_APP_SMS_URL=https://prod-xx.westeurope.logic.azure.com/workflows/...
"""
import os
import logging
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger("api.sms_alerts")

SMS_THRESHOLD = 0.70
_LOGIC_APP_URL: Optional[str] = None


def _get_logic_app_url() -> Optional[str]:
    global _LOGIC_APP_URL
    if _LOGIC_APP_URL is None:
        _LOGIC_APP_URL = os.getenv("LOGIC_APP_SMS_URL", "").strip() or None
    return _LOGIC_APP_URL


def build_sms_message(delivery_id: str, city: str, prob_fallo: float) -> str:
    pct = round(prob_fallo * 100)
    return (
        f"RetailCore: Su entrega {delivery_id} en {city.capitalize()} "
        f"tiene un {pct}% de probabilidad de fallo hoy. "
        f"Le proponemos cambiar de franja horaria. "
        f"Responda SI para reprogramar."
    )


def build_html_email(delivery_id: str, city: str, prob_fallo: float) -> str:
    pct = round(prob_fallo * 100)
    color = "#ef4444" if prob_fallo >= 0.7 else "#f59e0b"
    bar_width = pct
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

        <!-- HEADER -->
        <tr>
          <td style="background:#1a2e4a;padding:28px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <div style="font-size:22px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;">📦 RetailCore Logistics</div>
                  <div style="font-size:12px;color:#94a3b8;margin-top:4px;">Sistema de predicción de entregas · Alerta automática</div>
                </td>
                <td align="right">
                  <span style="background:{color};color:#fff;padding:6px 14px;border-radius:999px;font-size:12px;font-weight:700;">🔴 RIESGO ALTO</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- BODY -->
        <tr>
          <td style="padding:32px;">

            <p style="font-size:16px;color:#1e293b;margin:0 0 8px 0;">Estimado destinatario,</p>
            <p style="font-size:14px;color:#475569;margin:0 0 24px 0;">
              Nuestro sistema de inteligencia artificial ha detectado que su entrega de hoy tiene una
              <strong style="color:{color};">alta probabilidad de fallo</strong>.
              Le proponemos cambiar la franja horaria para garantizar la recepción.
            </p>

            <!-- CARD ENTREGA -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;margin-bottom:24px;">
              <tr>
                <td style="padding:20px 24px;">
                  <div style="font-size:11px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:12px;">Detalles de la entrega</div>
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="padding:5px 0;font-size:13px;color:#64748b;width:160px;">ID de entrega</td>
                      <td style="padding:5px 0;font-size:13px;font-weight:700;color:#1e293b;">{delivery_id}</td>
                    </tr>
                    <tr>
                      <td style="padding:5px 0;font-size:13px;color:#64748b;">Ciudad</td>
                      <td style="padding:5px 0;font-size:13px;font-weight:700;color:#1e293b;">{city.capitalize()}</td>
                    </tr>
                    <tr>
                      <td style="padding:5px 0;font-size:13px;color:#64748b;">Fecha</td>
                      <td style="padding:5px 0;font-size:13px;font-weight:700;color:#1e293b;">{date_str}</td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>

            <!-- BARRA DE RIESGO -->
            <div style="margin-bottom:24px;">
              <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;">Probabilidad de fallo</span>
                <span style="font-size:18px;font-weight:800;color:{color};">{pct}%</span>
              </div>
              <div style="background:#e2e8f0;border-radius:999px;height:10px;overflow:hidden;">
                <div style="background:{color};width:{bar_width}%;height:100%;border-radius:999px;"></div>
              </div>
            </div>

            <!-- CTA -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;margin-bottom:24px;">
              <tr>
                <td style="padding:16px 20px;">
                  <div style="font-size:13px;color:#9a3412;font-weight:600;">💡 ¿Qué puede hacer?</div>
                  <ul style="margin:8px 0 0 0;padding-left:18px;font-size:13px;color:#7c2d12;line-height:1.7;">
                    <li>Responder a este email confirmando que estará disponible</li>
                    <li>Indicarnos una franja horaria alternativa (mañana / tarde)</li>
                    <li>Solicitar entrega en punto de recogida cercano</li>
                  </ul>
                </td>
              </tr>
            </table>

          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:16px 32px;">
            <p style="font-size:11px;color:#94a3b8;margin:0;text-align:center;">
              Este mensaje ha sido generado automáticamente por <strong>RetailCore Logistics AI</strong> ·
              XGBoost · AUC-ROC 0.744 · Tajamar 2026
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


async def send_alert(
    delivery_id: str,
    city: str,
    prob_fallo: float,
    phone: str = "+34000000000",
) -> dict:
    """
    Envía una alerta SMS via Azure Logic Apps para una entrega HIGH risk.
    Retorna un dict con el resultado: sent, simulated, timestamp, detail.
    """
    message = build_sms_message(delivery_id, city, prob_fallo)
    html_body = build_html_email(delivery_id, city, prob_fallo)
    timestamp = datetime.now().isoformat()
    url = _get_logic_app_url()

    if url:
        payload = {
            "delivery_id": delivery_id,
            "city": city,
            "prob_fallo": round(prob_fallo, 4),
            "phone": phone,
            "message": message,
            "html_body": html_body,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            logger.info(f"SMS enviado via Logic Apps: {delivery_id} → {phone}")
            return {
                "sent": True,
                "simulated": False,
                "delivery_id": delivery_id,
                "phone": phone,
                "message": message,
                "timestamp": timestamp,
                "detail": f"Logic Apps respondió {resp.status_code}",
            }
        except Exception as e:
            logger.warning(f"Logic Apps no disponible ({e}). Simulando SMS.")

    # Sin URL configurada → simulación (útil para demo y desarrollo)
    logger.info(f"SMS simulado (sin LOGIC_APP_SMS_URL): {delivery_id}")
    return {
        "sent": True,
        "simulated": True,
        "delivery_id": delivery_id,
        "phone": phone,
        "message": message,
        "timestamp": timestamp,
        "detail": "Simulado — configura LOGIC_APP_SMS_URL para envío real",
    }


async def process_batch_alerts(predictions: list[dict]) -> list[dict]:
    """
    Procesa una lista de predicciones y envía SMS a todas las HIGH risk.
    Retorna la lista de alertas enviadas/simuladas.
    """
    alerts = []
    for p in predictions:
        if p.get("prob_fallo", 0) >= SMS_THRESHOLD:
            alert = await send_alert(
                delivery_id=p["delivery_id"],
                city=p.get("zone") or p.get("city", "desconocida"),
                prob_fallo=p["prob_fallo"],
            )
            alerts.append(alert)
    return alerts
