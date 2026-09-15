from datetime import date as date_type

from fastapi import APIRouter, Query, Response

from ..db import get_session
from ..report_service import build_pdf, fetch_stats_for_range

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/report/pdf")
def download_pdf_report(
    date_from: date_type = Query(..., description="Inclusive start date"),
    date_to: date_type = Query(..., description="Inclusive end date"),
) -> Response:
    with get_session() as session:
        data = fetch_stats_for_range(session, date_from, date_to)

    pdf_bytes = build_pdf(date_from, date_to, data)
    filename = f"pcrf_report_{date_from.isoformat()}_{date_to.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
