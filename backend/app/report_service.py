"""
PDF + email report generation. Refactored from the old
daily_report_handler.py Lambda: the same fetch/build/send logic, but
split into functions usable two ways:

  1. On a schedule (app/scheduler.py), for the daily SES email -- same
     10:30 UTC cadence as before.
  2. On demand (routers/reports.py GET /api/report/pdf), for an
     arbitrary date range -- this is the PDF/CSV export feature from
     the PCRF frontend, now generalized past "just today".

WHAT "TODAY" MEANS FOR THE SCHEDULED EMAIL, AND AN IMPORTANT CAVEAT
(carried over from the original): RDS Postgres' CURRENT_DATE uses the
instance's configured timezone (UTC by default). At a 10:30 UTC send
time this lines up correctly with a 16:00 Colombo send -- re-check
this if the schedule ever moves earlier than ~05:30 Colombo. New data
has historically arrived weekly, not daily, so most days' "today"
report will legitimately say "no new data" -- that's expected, not a
bug.
"""
from __future__ import annotations

import io
import os
from datetime import date, datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import text

from .db import get_session

SENDER = os.environ.get("SES_SENDER_EMAIL", "")
RECIPIENTS = [r.strip() for r in os.environ.get("REPORT_RECIPIENTS", "").split(",") if r.strip()]
HIGH_RISK_THRESHOLD = float(os.environ.get("HIGH_RISK_THRESHOLD", "70"))
MAX_REPORT_ROWS = int(os.environ.get("MAX_REPORT_ROWS", "200"))


def fetch_stats_for_range(session, date_from: date, date_to: date) -> dict:
    kpi_sql = text("""
        SELECT
            COUNT(DISTINCT subscriber_id)      AS total_subscribers,
            COALESCE(SUM(sessions_per_day), 0) AS total_sessions,
            COALESCE(AVG(risk_score_0_100), 0) AS average_risk,
            COALESCE(MAX(risk_score_0_100), 0) AS maximum_risk,
            COALESCE(SUM(daily_usage_gb), 0)   AS total_usage_gb,
            SUM(CASE WHEN risk_score_0_100 >= :threshold THEN 1 ELSE 0 END) AS high_risk_count,
            SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END)  AS block_count,
            SUM(CASE WHEN decision = 'REVIEW' THEN 1 ELSE 0 END) AS review_count
        FROM subscribers_daily
        WHERE session_date >= :date_from AND session_date <= :date_to
    """)
    kpis = session.execute(
        kpi_sql, {"date_from": date_from, "date_to": date_to, "threshold": HIGH_RISK_THRESHOLD}
    ).mappings().one()

    rows_sql = text("""
        SELECT subscriber_id, account_num, risk_score_0_100, decision, final_score,
               sessions_per_day, daily_usage_gb, offer_name, triggered_rules
        FROM subscribers_daily
        WHERE session_date >= :date_from AND session_date <= :date_to
          AND risk_score_0_100 >= :threshold
        ORDER BY risk_score_0_100 DESC
        LIMIT :limit
    """)
    high_risk_rows = session.execute(
        rows_sql,
        {"date_from": date_from, "date_to": date_to, "threshold": HIGH_RISK_THRESHOLD, "limit": MAX_REPORT_ROWS},
    ).mappings().all()

    return {"kpis": kpis, "high_risk_rows": high_risk_rows}


def build_pdf(date_from: date, date_to: date, data: dict) -> bytes:
    buffer = io.BytesIO()
    label = date_from.isoformat() if date_from == date_to else f"{date_from.isoformat()} to {date_to.isoformat()}"
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), title=f"PCRF Fraud Risk Report {label}")
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("PCRF Fraud Risk Report", styles["Title"]))
    story.append(Paragraph(
        f"Range: {label} &nbsp;|&nbsp; Generated: {datetime.utcnow().isoformat(timespec='seconds')} UTC",
        styles["Normal"],
    ))
    story.append(Spacer(1, 10 * mm))

    kpis = data["kpis"]
    kpi_table = Table(
        [
            ["Subscribers", "Sessions", "Avg risk", "Max risk", "Usage (GB)", "Block", "Review"],
            [
                f"{int(kpis['total_subscribers']):,}",
                f"{int(kpis['total_sessions']):,}",
                f"{float(kpis['average_risk']):.2f}",
                f"{float(kpis['maximum_risk']):.2f}",
                f"{float(kpis['total_usage_gb']):.2f}",
                f"{int(kpis['block_count'] or 0):,}",
                f"{int(kpis['review_count'] or 0):,}",
            ],
        ],
        hAlign="LEFT",
    )
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b1f3a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7e4ee")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 8 * mm))

    rows = data["high_risk_rows"]
    if not rows:
        story.append(Paragraph(
            f"No subscribers scored at or above {HIGH_RISK_THRESHOLD} for {label}.", styles["Normal"]
        ))
    else:
        story.append(Paragraph(f"High-risk subscribers (score \u2265 {HIGH_RISK_THRESHOLD:.0f})", styles["Heading2"]))
        table_data = [["Subscriber", "Account", "Risk", "Decision", "Sessions/day", "Usage (GB)", "Rules"]]
        for r in rows:
            table_data.append([
                str(r["subscriber_id"]),
                str(r["account_num"] or ""),
                f"{float(r['risk_score_0_100']):.2f}",
                str(r["decision"] or "-"),
                f"{int(r['sessions_per_day'] or 0):,}",
                f"{float(r['daily_usage_gb'] or 0):.2f}",
                str(r["triggered_rules"] or "")[:40],
            ])
        risk_table = Table(table_data, repeatRows=1, hAlign="LEFT")
        risk_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b1f3a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7e4ee")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f9fb")]),
        ]))
        story.append(risk_table)
        if len(rows) >= MAX_REPORT_ROWS:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph(f"Showing the top {MAX_REPORT_ROWS} rows by risk score.", styles["Italic"]))

    doc.build(story)
    return buffer.getvalue()


def send_email(today: date, pdf_bytes: bytes, kpis: dict) -> bool:
    if not RECIPIENTS:
        return False
    if not SENDER:
        raise RuntimeError("SES_SENDER_EMAIL is not set -- cannot send.")

    ses = boto3.client("ses", region_name=os.environ.get("AWS_REGION"))
    msg = MIMEMultipart()
    msg["Subject"] = f"PCRF Daily Risk Report - {today.isoformat()}"
    msg["From"] = SENDER
    msg["To"] = ", ".join(RECIPIENTS)

    body = (
        f"Automated PCRF fraud-risk summary for {today.isoformat()}.\n\n"
        f"Total subscribers: {int(kpis['total_subscribers']):,}\n"
        f"Average risk score: {float(kpis['average_risk']):.2f}\n"
        f"Block decisions: {int(kpis['block_count'] or 0):,}\n"
        f"Review decisions: {int(kpis['review_count'] or 0):,}\n\n"
        "Full detail is attached as a PDF. This is an automated message."
    )
    msg.attach(MIMEText(body, "plain"))

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename=f"pcrf_daily_report_{today.isoformat()}.pdf")
    msg.attach(attachment)

    ses.send_raw_email(Source=SENDER, Destinations=RECIPIENTS, RawMessage={"Data": msg.as_string()})
    return True


def run_daily_report() -> dict:
    """Called by the APScheduler job (app/scheduler.py) at the configured time."""
    today = date.today()
    with get_session() as session:
        data = fetch_stats_for_range(session, today, today)

    pdf_bytes = build_pdf(today, today, data)
    sent = send_email(today, pdf_bytes, data["kpis"])

    return {
        "date": today.isoformat(),
        "high_risk_rows_included": len(data["high_risk_rows"]),
        "recipients_configured": len(RECIPIENTS),
        "sent": sent,
    }
