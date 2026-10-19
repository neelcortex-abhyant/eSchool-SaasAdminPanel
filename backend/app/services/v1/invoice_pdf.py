"""Render an issued receipt from its stored snapshot. Does not read live school or plan rows."""

from __future__ import annotations

from fpdf import FPDF

from app.models.tables import SubscriptionInvoice


def render_invoice_pdf(invoice: SubscriptionInvoice) -> bytes:
    pdf = FPDF()
    pdf.set_compression(False)
    pdf.add_page()
    pdf.set_font("Helvetica", size=16)
    pdf.cell(0, 10, "Subscription payment receipt", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, f"Invoice number: {invoice.invoice_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Issue date: {invoice.issued_at.date().isoformat()}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.cell(0, 8, "Billed to", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, invoice.school_name, new_x="LMARGIN", new_y="NEXT")
    if invoice.school_address:
        pdf.cell(0, 7, invoice.school_address, new_x="LMARGIN", new_y="NEXT")
    if invoice.school_email:
        pdf.cell(0, 7, invoice.school_email, new_x="LMARGIN", new_y="NEXT")
    if invoice.school_phone:
        pdf.cell(0, 7, invoice.school_phone, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    description = invoice.plan_description or ""
    pdf.cell(0, 8, f"Plan: {invoice.plan_name}", new_x="LMARGIN", new_y="NEXT")
    if description:
        pdf.cell(0, 7, description, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Cycle: {invoice.cycle}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        7,
        f"Period: {invoice.period_start.isoformat()} to {invoice.period_end.isoformat()}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)
    pdf.cell(0, 8, f"Gateway: {invoice.gateway}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Order: {invoice.gateway_order_id}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Payment: {invoice.gateway_payment_id}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.cell(
        0,
        8,
        f"Amount paid: {invoice.amount_paise} {invoice.currency} paise",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    if invoice.tax_amount_paise is None:
        pdf.cell(0, 7, "Tax: not configured", new_x="LMARGIN", new_y="NEXT")
    else:
        label = invoice.tax_label or "Tax"
        rate = "" if invoice.tax_rate_percent is None else f" {invoice.tax_rate_percent}%"
        pdf.cell(
            0,
            7,
            f"{label}{rate}: {invoice.tax_amount_paise} {invoice.currency} paise",
            new_x="LMARGIN",
            new_y="NEXT",
        )
    pdf.cell(
        0,
        8,
        f"Total: {invoice.total_amount_paise} {invoice.currency} paise",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    output = pdf.output()
    return bytes(output)


def invoice_filename(invoice_number: str) -> str:
    safe = "".join(character for character in invoice_number if character.isalnum() or character == "-")
    return f"{safe or 'invoice'}.pdf"
