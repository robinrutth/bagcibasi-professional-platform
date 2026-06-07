from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config import get_settings

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "pdf"
BRAND_GREEN = colors.HexColor("#16a34a")
LIGHT_GREEN = colors.HexColor("#dcfce7")
TEXT_DARK = colors.HexColor("#172033")
MUTED = colors.HexColor("#64748b")


def _template_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_pdf_template(template_name: str, context: dict[str, Any]) -> str:
    settings = get_settings()
    template = _template_environment().get_template(template_name)
    return template.render({"platform_name": settings.platform_name, **context})


def _money(value: float | int | None) -> str:
    amount = float(value or 0)
    return f"{amount:,.2f} TRY"


def _number(value: float | int | None, suffix: str = "") -> str:
    amount = float(value or 0)
    return f"{amount:,.2f}{suffix}"


def _safe(value: Any, fallback: str = "-") -> str:
    if value is None or value == "":
        return fallback
    text = str(value)
    replacements = {
        "\u0130": "I",   # İ
        "\u0131": "i",   # ı
        "\u015f": "s",   # ş
        "\u015e": "S",   # Ş
        "\u00fc": "u",   # ü
        "\u00dc": "U",   # Ü
        "\u00f6": "o",   # ö
        "\u00d6": "O",   # Ö
        "\u00e7": "c",   # ç
        "\u00c7": "C",   # Ç
        "\u011f": "g",   # ğ
        "\u011e": "G",   # Ğ
        "\u00e2": "a",   # â
        "\u00ee": "i",   # î
        "\u00fb": "u",   # û
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def _invoice_number(shipment: Any, issued_at: datetime) -> str:
    short_id = str(getattr(shipment, "id", "NA")).split("-")[0]
    return f"INV-{short_id}-{issued_at:%Y%m%d}"


def _emission_label(total_co2: float) -> str:
    if total_co2 <= 100:
        return "Dusuk"
    if total_co2 <= 500:
        return "Orta"
    return "Yuksek"


def _build_doc(title: str) -> tuple[BytesIO, SimpleDocTemplate, list[Any], dict[str, ParagraphStyle]]:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=title,
    )
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("title", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=TEXT_DARK),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=MUTED),
        "section": ParagraphStyle("section", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=TEXT_DARK),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=TEXT_DARK),
        "small": ParagraphStyle("small", parent=base["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=MUTED),
        "badge": ParagraphStyle("badge", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=BRAND_GREEN),
    }
    return buffer, doc, [], styles


def _header(platform_name: str, title: str, meta: Iterable[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    meta_rows = [[Paragraph(f"<b>{label}</b>", styles["small"]), Paragraph(value, styles["small"])] for label, value in meta]
    table = Table(
        [
            [
                Paragraph(f"<font color='#16a34a'><b>{platform_name}</b></font><br/>{title}", styles["title"]),
                Table(meta_rows, colWidths=[28 * mm, 44 * mm]),
            ]
        ],
        colWidths=[112 * mm, 72 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 1, BRAND_GREEN),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _key_value_table(rows: list[tuple[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    table = Table(
        [[Paragraph(label, styles["small"]), Paragraph(_safe(value), styles["body"])] for label, value in rows],
        colWidths=[42 * mm, 50 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe4ee")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _styled_table(rows: list[list[Any]], widths: list[float], styles: dict[str, ParagraphStyle]) -> Table:
    normalized = [
        [cell if not isinstance(cell, str) else Paragraph(cell, styles["body"]) for cell in row]
        for row in rows
    ]
    table = Table(normalized, colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe4ee")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def generate_shipment_invoice(shipment: Any, customer: Any) -> bytes:
    issued_at = datetime.utcnow()
    invoice_no = _invoice_number(shipment, issued_at)
    total_amount = float(getattr(shipment, "invoice_amount", 0) or 0)
    context = {
        "shipment": shipment,
        "customer": customer,
        "invoice_no": invoice_no,
        "issued_at": issued_at,
        "subtotal": total_amount,
        "tax_amount": 0,
        "total_amount": total_amount,
    }
    render_pdf_template("invoice.html", context)

    settings = get_settings()
    buffer, doc, story, styles = _build_doc(invoice_no)
    story.append(
        _header(
            settings.platform_name,
            "PDF Fatura",
            [("Fatura No", invoice_no), ("Tarih", issued_at.strftime("%Y-%m-%d %H:%M UTC"))],
            styles,
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        Table(
            [
                [
                    _key_value_table(
                        [
                            ("Musteri", getattr(customer, "name", getattr(shipment, "customer_name", "-"))),
                            ("Adres", getattr(customer, "address", None)),
                            ("Vergi No", getattr(customer, "tax_number", None)),
                            ("E-posta", getattr(customer, "email", None)),
                        ],
                        styles,
                    ),
                    _key_value_table(
                        [
                            ("Cikis", getattr(shipment, "origin", None)),
                            ("Varis", getattr(shipment, "destination", None)),
                            ("Agirlik", _number(getattr(shipment, "weight_kg", None) or (getattr(shipment, "tonnage", 0) or 0) * 1000, " kg")),
                            ("Mesafe", _number(getattr(shipment, "distance_km", None), " km")),
                            ("Arac Tipi", getattr(shipment, "vehicle_type", None)),
                        ],
                        styles,
                    ),
                ]
            ],
            colWidths=[92 * mm, 92 * mm],
        )
    )
    story.append(Spacer(1, 10))
    story.append(Paragraph("Fatura Kalemleri", styles["section"]))
    story.append(
        _styled_table(
            [
                ["Aciklama", "Miktar", "Birim", "Tutar"],
                [
                    f"{_safe(getattr(shipment, 'origin', None))} - {_safe(getattr(shipment, 'destination', None))} lojistik hizmeti",
                    "1",
                    "Sevkiyat",
                    _money(total_amount),
                ],
                ["Karbon emisyonu bilgilendirme", _number(getattr(shipment, "co2_kg", None), " kg CO2"), "Rapor", _money(0)],
                ["Toplam", "", "", _money(total_amount)],
            ],
            [82 * mm, 28 * mm, 34 * mm, 40 * mm],
            styles,
        )
    )
    story.append(Spacer(1, 10))
    carbon_box = Table(
        [[Paragraph("Karbon Emisyonu", styles["badge"]), Paragraph(_number(getattr(shipment, "co2_kg", None), " kg CO2"), styles["badge"])]],
        colWidths=[92 * mm, 92 * mm],
    )
    carbon_box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREEN), ("BOX", (0, 0), (-1, -1), 0.6, BRAND_GREEN), ("PADDING", (0, 0), (-1, -1), 8)]))
    story.append(carbon_box)
    story.append(Spacer(1, 10))
    story.append(Paragraph("ISO 14083:2023 Emisyon Metodolojisi", styles["section"]))
    co2_kg = float(getattr(shipment, "co2_kg", 0) or 0)
    distance_km = float(getattr(shipment, "distance_km", 0) or 0)
    weight_kg = float(getattr(shipment, "weight_kg", None) or (getattr(shipment, "tonnage", 0) or 0) * 1000 or 0)
    load_tons = weight_kg / 1000.0
    efficiency = round((co2_kg * 1000) / (load_tons * distance_km), 1) if load_tons > 0 and distance_km > 0 else 0
    iso_table = _styled_table(
        [
            ["Parametre", "Deger"],
            ["Metodoloji", "ISO 14083:2023"],
            ["Hesaplama Tipi", "WTW (Well-to-Wheel)"],
            ["Emisyon Faktoru Kaynagi", "EMEP/EEA 2023, IPCC AR6"],
            ["Toplam CO2 Emisyonu", _number(co2_kg, " kg CO2e")],
            ["Verimlilik Metigi", _number(efficiency, " gCO2e/ton-km")],
            ["Mesafe", _number(distance_km, " km")],
            ["Yuk", _number(load_tons, " ton")],
        ],
        [92 * mm, 92 * mm],
        styles,
    )
    story.append(iso_table)
    story.append(Spacer(1, 8))
    iso_note = Table(
        [[Paragraph("Bu belge ISO 14083:2023 Well-to-Wheel (WTW) metodolojisine gore hesaplanmis karbon emisyonu bilgilerini icermektedir. Emisyon faktorleri EMEP/EEA 2023 ve IPCC AR6 raporlarindan alinmistir.", styles["small"])]],
        colWidths=[184 * mm],
    )
    iso_note.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREEN), ("BOX", (0, 0), (-1, -1), 0.6, BRAND_GREEN), ("PADDING", (0, 0), (-1, -1), 8)]))
    story.append(iso_note)
    story.append(Spacer(1, 16))
    story.append(Paragraph(f"{settings.platform_name} | operasyon@bagcibasi-lojistik.local | +90 236 000 00 00", styles["small"]))
    doc.build(story)
    return buffer.getvalue()


def generate_carbon_report_pdf(customer: Any, summary: dict[str, Any], period: str) -> bytes:
    issued_at = datetime.utcnow()
    total_co2 = float(summary.get("total_co2_kg", summary.get("total_co2", 0)) or 0)
    label = summary.get("label") or _emission_label(total_co2)
    context = {"customer": customer, "summary": summary, "period": period, "issued_at": issued_at, "label": label}
    render_pdf_template("carbon_report.html", context)

    settings = get_settings()
    buffer, doc, story, styles = _build_doc("CBAM ISO 14083 Karbon Emisyon Raporu")
    story.append(
        _header(
            settings.platform_name,
            "Karbon Emisyon Raporu",
            [("Musteri", _safe(getattr(customer, "name", "Tum Musteriler"))), ("Donem", period), ("Tarih", issued_at.strftime("%Y-%m-%d %H:%M UTC"))],
            styles,
        )
    )
    story.append(Spacer(1, 10))
    story.append(
        _styled_table(
            [
                ["Toplam CO2", "Shipment", "Ortalama", "Etiket"],
                [
                    _number(total_co2, " kg"),
                    str(summary.get("shipment_count", 0)),
                    _number(summary.get("average_co2_kg", 0), " kg"),
                    str(label),
                ],
            ],
            [46 * mm, 46 * mm, 46 * mm, 46 * mm],
            styles,
        )
    )
    story.append(Spacer(1, 10))
    story.append(Paragraph("Arac Tipi Dagilimi", styles["section"]))
    vehicle_rows = [["Arac Tipi", "CO2"]]
    vehicle_rows.extend([[_safe(row.get("vehicle_type", "-")).capitalize(), _number(row.get("co2", 0), " kg")] for row in summary.get("by_vehicle", [])])
    if len(vehicle_rows) == 1:
        vehicle_rows.append(["Veri yok", "0 kg"])
    story.append(_styled_table(vehicle_rows, [92 * mm, 92 * mm], styles))
    story.append(Spacer(1, 10))
    story.append(Paragraph("En Kirletici Rotalar", styles["section"]))
    route_rows = [["Rota", "Arac", "Shipment", "CO2"]]
    route_rows.extend(
        [
            [f"{_safe(row.get('origin', '-'))} - {_safe(row.get('destination', '-'))}", _safe(row.get("vehicle_type")), str(row.get("shipment_count", 0)), _number(row.get("co2", 0), " kg")]
            for row in summary.get("top_routes", [])
        ]
    )
    if len(route_rows) == 1:
        route_rows.append(["Veri yok", "-", "0", "0 kg"])
    story.append(_styled_table(route_rows, [72 * mm, 40 * mm, 30 * mm, 42 * mm], styles))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Sektor ortalamasi karsilastirmasi", styles["section"]))
    story.append(Paragraph(f"Bu donemde musteri etiketi <b>{label}</b>. Referans deger: {summary.get('benchmark_note', 'Sektor ortalamasi 0.35 kg CO2/km varsayimi ile izlenir.')}", styles["body"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Yesil lojistik rozeti: Emisyon takipli operasyon", styles["badge"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("ISO 14083:2023 Uyumluluk Beyani", styles["section"]))
    story.append(
        _styled_table(
            [
                ["Standart", "Kapsam", "Durum"],
                ["ISO 14083:2023", "WTW Emisyon Hesaplama", "Uyumlu"],
                ["EMEP/EEA 2023", "Emisyon Faktoru Kaynagi", "Aktif"],
                ["IPCC AR6", "Kuresel Isinma Potansiyeli", "Aktif"],
            ],
            [62 * mm, 72 * mm, 50 * mm],
            styles,
        )
    )
    story.append(Spacer(1, 8))
    total_co2 = float(summary.get("total_co2_kg", summary.get("total_co2", 0)) or 0)
    shipment_count = int(summary.get("shipment_count", 0))
    avg_co2 = float(summary.get("average_co2_kg", 0) or 0)
    story.append(Paragraph(f"Bu rapor {shipment_count} sevkiyati kapsamakta olup toplam {_number(total_co2, ' kg')} CO2e emisyonu ISO 14083:2023 WTW metodolojisiyle hesaplanmistir. Ortalama emisyon sevkiyat basina {_number(avg_co2, ' kg CO2e')} olarak gerceklesmistir.", styles["body"]))
    doc.build(story)
    return buffer.getvalue()
