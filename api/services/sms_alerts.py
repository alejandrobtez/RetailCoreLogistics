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
    date_str = datetime.now().strftime("%d/%m/%Y · %H:%M")
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
</head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:40px 16px;">
  <tr><td align="center">
  <table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.10);">

    <!-- ░░ HEADER GRADIENTE ░░ -->
    <tr>
      <td style="background:linear-gradient(135deg,#1a2e4a 0%,#1e4080 60%,#2563eb 100%);padding:36px 40px 28px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <div style="font-size:11px;font-weight:700;color:#93c5fd;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:8px;">Sistema de Predicción de Entregas</div>
              <div style="font-size:26px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;line-height:1.2;">📦 RetailCore<br/>Logistics</div>
            </td>
            <td align="right" valign="top">
              <div style="background:rgba(255,255,255,0.12);border:1.5px solid rgba(255,255,255,0.25);border-radius:12px;padding:14px 18px;text-align:center;min-width:80px;">
                <div style="font-size:32px;font-weight:900;color:#fbbf24;line-height:1;">{pct}%</div>
                <div style="font-size:10px;color:#fde68a;font-weight:600;margin-top:4px;text-transform:uppercase;letter-spacing:0.08em;">Riesgo fallo</div>
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- ░░ BANDA DE ALERTA ░░ -->
    <tr>
      <td style="background:linear-gradient(90deg,#ef4444,#dc2626);padding:12px 40px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <span style="font-size:13px;font-weight:700;color:#ffffff;letter-spacing:0.04em;">🔴 &nbsp;ALERTA DE RIESGO ALTO — ENTREGA EN PELIGRO</span>
            </td>
            <td align="right">
              <span style="font-size:11px;color:#fecaca;">{date_str}</span>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- ░░ CUERPO ░░ -->
    <tr>
      <td style="padding:36px 40px 0;">

        <p style="font-size:16px;color:#1e293b;font-weight:600;margin:0 0 6px 0;">Estimado destinatario,</p>
        <p style="font-size:14px;color:#64748b;line-height:1.7;margin:0 0 28px 0;">
          Nuestro sistema de inteligencia artificial ha analizado los factores de su entrega y ha detectado
          una <strong style="color:#dc2626;">alta probabilidad de fallo</strong>. Para garantizar que reciba
          su paquete, le proponemos reagendar la franja horaria.
        </p>

        <!-- CARD DETALLES -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;margin-bottom:28px;overflow:hidden;">
          <tr>
            <td style="background:#1e293b;padding:12px 20px;">
              <span style="font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.1em;">📋 &nbsp;Detalles de la entrega</span>
            </td>
          </tr>
          <tr>
            <td style="padding:0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding:14px 20px;font-size:13px;color:#64748b;border-bottom:1px solid #f1f5f9;width:45%;">ID de entrega</td>
                  <td style="padding:14px 20px;font-size:13px;font-weight:700;color:#1e293b;border-bottom:1px solid #f1f5f9;"><span style="background:#dbeafe;color:#1d4ed8;padding:2px 10px;border-radius:999px;font-size:12px;">{delivery_id}</span></td>
                </tr>
                <tr>
                  <td style="padding:14px 20px;font-size:13px;color:#64748b;border-bottom:1px solid #f1f5f9;">Ciudad</td>
                  <td style="padding:14px 20px;font-size:13px;font-weight:700;color:#1e293b;border-bottom:1px solid #f1f5f9;">📍 {city.capitalize()}</td>
                </tr>
                <tr>
                  <td style="padding:14px 20px;font-size:13px;color:#64748b;">Generado el</td>
                  <td style="padding:14px 20px;font-size:13px;font-weight:700;color:#1e293b;">{date_str}</td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <!-- BARRA DE RIESGO -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
          <tr>
            <td>
              <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:10px;">Probabilidad de fallo estimada</div>
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#fee2e2;border-radius:999px;height:14px;overflow:hidden;">
                    <div style="background:linear-gradient(90deg,#f87171,#dc2626);width:{pct}%;height:14px;border-radius:999px;"></div>
                  </td>
                  <td style="width:52px;padding-left:12px;font-size:20px;font-weight:900;color:#dc2626;">{pct}%</td>
                </tr>
              </table>
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:6px;">
                <tr>
                  <td style="font-size:10px;color:#94a3b8;">0%</td>
                  <td align="center" style="font-size:10px;color:#f59e0b;">⚠️ Umbral (70%)</td>
                  <td align="right" style="font-size:10px;color:#94a3b8;">100%</td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <!-- OPCIONES -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#fff7ed,#fef3c7);border:1px solid #fde68a;border-radius:12px;margin-bottom:28px;">
          <tr>
            <td style="padding:20px 24px;">
              <div style="font-size:13px;font-weight:700;color:#92400e;margin-bottom:12px;">💡 ¿Qué puede hacer?</div>
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding:5px 0;font-size:13px;color:#78350f;line-height:1.6;">✅ &nbsp;Confirmar disponibilidad respondiendo a este email</td>
                </tr>
                <tr>
                  <td style="padding:5px 0;font-size:13px;color:#78350f;line-height:1.6;">🕐 &nbsp;Indicarnos una franja alternativa: mañana (9–14h) o tarde (16–20h)</td>
                </tr>
                <tr>
                  <td style="padding:5px 0;font-size:13px;color:#78350f;line-height:1.6;">📦 &nbsp;Solicitar entrega en punto de recogida cercano</td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <!-- BOTONES CTA -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:36px;">
          <tr>
            <td align="center" style="padding-right:8px;" width="50%">
              <a href="mailto:logistica@retailcore.es?subject=Confirmo disponibilidad - {delivery_id}&body=Confirmo que estare disponible para recibir mi entrega {delivery_id}."
                 style="display:block;background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#ffffff;text-decoration:none;font-size:13px;font-weight:700;padding:14px 20px;border-radius:10px;text-align:center;">
                ✅ Confirmar disponibilidad
              </a>
            </td>
            <td align="center" style="padding-left:8px;" width="50%">
              <a href="mailto:logistica@retailcore.es?subject=Cambio de franja - {delivery_id}&body=Para la entrega {delivery_id}, prefiero la siguiente franja horaria:"
                 style="display:block;background:#ffffff;color:#1e293b;text-decoration:none;font-size:13px;font-weight:700;padding:14px 20px;border-radius:10px;text-align:center;border:1.5px solid #e2e8f0;">
                🕐 Cambiar franja horaria
              </a>
            </td>
          </tr>
        </table>

      </td>
    </tr>

    <!-- ░░ FOOTER ░░ -->
    <tr>
      <td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:20px 40px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <p style="font-size:11px;color:#94a3b8;margin:0;line-height:1.6;">
                Generado automáticamente por <strong style="color:#64748b;">RetailCore Logistics AI</strong><br/>
                Modelo XGBoost · AUC-ROC 0.744 · Tajamar 2026
              </p>
            </td>
            <td align="right">
              <span style="font-size:20px;">📦</span>
            </td>
          </tr>
        </table>
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
