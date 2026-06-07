from __future__ import annotations

import logging
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "email"


def _template_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_email_template(template_name: str, context: dict[str, Any]) -> str:
    settings = get_settings()
    template = _template_environment().get_template(template_name)
    return template.render(
        {
            "platform_name": settings.platform_name,
            "frontend_url": settings.frontend_url,
            **context,
        }
    )


def _recipient_email(entity: Any) -> str | None:
    return getattr(entity, "email", None)


def _format_route(shipment: Any) -> str:
    return f"{getattr(shipment, 'origin', '-')} - {getattr(shipment, 'destination', '-')}"


def is_delivered_status(status: str | None) -> bool:
    normalized = (status or "").strip().lower()
    return normalized in {"delivered", "teslim edildi"} or "teslim" in normalized


async def send_email(to: str, subject: str, body: str, attachments: list[dict[str, Any]] | None = None) -> bool:
    settings = get_settings()
    if not to or not settings.mail_server:
        logger.info("Email skipped because recipient or mail server is not configured")
        return False

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content("Bu e-posta HTML destekli bir istemcide goruntulenmelidir.")
    message.add_alternative(body, subtype="html")
    for attachment in attachments or []:
        message.add_attachment(
            attachment["content"],
            maintype=attachment.get("maintype", "application"),
            subtype=attachment.get("subtype", "octet-stream"),
            filename=attachment["filename"],
        )

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.mail_server,
            port=settings.mail_port,
            username=settings.mail_username or None,
            password=settings.mail_password or None,
            start_tls=settings.mail_tls,
            use_tls=settings.mail_ssl,
        )
        return True
    except Exception:
        logger.exception("Email delivery failed")
        return False


async def send_shipment_created(shipment: Any, customer: Any) -> bool:
    to = _recipient_email(customer)
    subject = f"Sevkiyatınız Oluşturuldu - #{shipment.id}"
    body = render_email_template(
        "shipment_created.html",
        {"shipment": shipment, "customer": customer, "route": _format_route(shipment)},
    )
    return await send_email(to, subject, body) if to else False


async def send_shipment_updated(shipment: Any, customer: Any) -> bool:
    to = _recipient_email(customer)
    subject = f"Sevkiyat Durumu Güncellendi - #{shipment.id}"
    body = render_email_template(
        "shipment_updated.html",
        {"shipment": shipment, "customer": customer, "route": _format_route(shipment)},
    )
    return await send_email(to, subject, body) if to else False


async def send_shipment_delivered(shipment: Any, customer: Any) -> bool:
    to = _recipient_email(customer)
    subject = f"Sevkiyatınız Teslim Edildi - #{shipment.id}"
    body = render_email_template(
        "shipment_delivered.html",
        {"shipment": shipment, "customer": customer, "route": _format_route(shipment)},
    )
    return await send_email(to, subject, body) if to else False


async def send_welcome_email(user: Any) -> bool:
    to = _recipient_email(user)
    subject = "Platforma Hoş Geldiniz"
    body = render_email_template("welcome.html", {"user": user})
    return await send_email(to, subject, body) if to else False


async def send_carbon_report(customer: Any, summary: dict[str, Any]) -> bool:
    to = _recipient_email(customer)
    subject = "Aylık Karbon Emisyonu Raporunuz"
    body = render_email_template("carbon_report.html", {"customer": customer, "summary": summary})
    return await send_email(to, subject, body) if to else False


async def send_invoice_email(customer: Any, pdf_bytes: bytes) -> bool:
    to = _recipient_email(customer)
    if not to:
        return False
    subject = "PDF Faturanız"
    body = render_email_template("invoice.html", {"customer": customer})
    return await send_email(
        to,
        subject,
        body,
        attachments=[
            {
                "filename": "fatura.pdf",
                "content": pdf_bytes,
                "maintype": "application",
                "subtype": "pdf",
            }
        ],
    )


def queue_shipment_notification(background_tasks: Any, shipment: Any, customer: Any, event: str) -> None:
    if not background_tasks or not customer:
        return
    if event == "created":
        background_tasks.add_task(send_shipment_created, shipment, customer)
    elif event == "delivered" or is_delivered_status(getattr(shipment, "status", None)):
        background_tasks.add_task(send_shipment_delivered, shipment, customer)
    elif event == "updated":
        background_tasks.add_task(send_shipment_updated, shipment, customer)
