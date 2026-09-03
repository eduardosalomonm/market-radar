from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import ScanResult
from .presentation import executive_brief, recommendation_reason

INK = colors.HexColor("#0B1320")
SLATE = colors.HexColor("#4B5B70")
BLUE = colors.HexColor("#2457A6")
PALE_BLUE = colors.HexColor("#EAF1FB")
PALE_GREEN = colors.HexColor("#EAF7F1")
GRID = colors.HexColor("#D8E0EA")


def _clean(value) -> str:
    """Make saved market text safe for PDF markup and the core PDF fonts."""
    text = str(value).translate(str.maketrans({"—": "-", "–": "-", "−": "-", "×": "x"}))
    return escape(text)


def _money(value) -> str:
    return f"${value:,.2f}" if value is not None else "-"


def _format_change(value) -> str:
    return f"{value:+.1%}" if value is not None else "New"


def build_client_brief_pdf(scan: ScanResult, intelligence: dict[str, object], catalysts) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=13 * mm,
        rightMargin=13 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"FolioShift Client Brief - {scan.as_of.isoformat()}",
        author="FolioShift",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "RadarTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=26,
        textColor=INK,
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )
    subtitle = ParagraphStyle(
        "RadarSubtitle",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=SLATE,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )
    section = ParagraphStyle(
        "RadarSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=BLUE,
        spaceBefore=2.5 * mm,
        spaceAfter=1.5 * mm,
    )
    body = ParagraphStyle(
        "RadarBody",
        parent=styles["BodyText"],
        fontSize=8.2,
        leading=10.5,
        textColor=INK,
    )
    small = ParagraphStyle("RadarSmall", parent=body, fontSize=7.2, leading=9, textColor=SLATE)
    score_style = ParagraphStyle(
        "RadarScore", parent=body, fontName="Helvetica-Bold", fontSize=13, leading=15, alignment=TA_RIGHT
    )

    brief = executive_brief(scan)
    signal_by_ticker = {signal.ticker: signal for signal in scan.signals}
    story = [
        Paragraph("FOLIOSHIFT", title),
        Paragraph(
            f"After-close client brief | Session {scan.as_of.isoformat()} | {scan.provider.title()} data | "
            "Conditional research only",
            subtitle,
        ),
    ]
    metric_data = [
        [
            Paragraph("MARKET POSTURE", small),
            Paragraph("GLOBAL RISK", small),
            Paragraph("QUALIFIED IDEAS", small),
            Paragraph("HIGH EVIDENCE", small),
        ],
        [
            Paragraph(_clean(brief["posture"]), body),
            Paragraph(f"{brief.get('risk_score') or 50:.0f}/100", score_style),
            Paragraph(str(brief["idea_count"]), score_style),
            Paragraph(str(brief["high_evidence_count"]), score_style),
        ],
    ]
    metrics = Table(metric_data, colWidths=[70 * mm, 36 * mm, 36 * mm, 36 * mm], rowHeights=[6 * mm, 12 * mm])
    metrics.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.6, GRID),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, GRID),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([metrics, Spacer(1, 2 * mm)])

    left_story = "<br/>".join(f"- {_clean(item)}" for item in brief["takeaways"][:4])
    change_summary = intelligence.get("changes", {}).get("summary", [])
    right_story = "<br/>".join(f"- {_clean(item)}" for item in change_summary[:4]) or "- No prior-session comparison"
    narrative = Table(
        [
            [Paragraph("Market story", section), Paragraph("What changed", section)],
            [Paragraph(left_story, body), Paragraph(right_story, body)],
        ],
        colWidths=[89 * mm, 89 * mm],
    )
    narrative.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.5, GRID),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, GRID),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([narrative, Paragraph("Highest-ranked conditional opportunities", section)])

    idea_rows = [["Ticker / company", "Setup", "Side", "Evidence", "Trigger", "Invalidation", "Why"]]
    for idea in sorted(scan.ideas, key=lambda item: item.evidence_score, reverse=True)[:3]:
        signal = signal_by_ticker[idea.ticker]
        idea_rows.append(
            [
                Paragraph(f"<b>{_clean(idea.ticker)}</b><br/>{_clean(signal.name)}", small),
                Paragraph(_clean(idea.quadrant), small),
                _clean(idea.direction.upper()),
                f"{idea.evidence_score:.1f}",
                _money(idea.trigger),
                _money(idea.stop),
                Paragraph(_clean(recommendation_reason(signal, idea)), small),
            ]
        )
    ideas_table = Table(
        idea_rows,
        repeatRows=1,
        colWidths=[28 * mm, 23 * mm, 12 * mm, 16 * mm, 19 * mm, 20 * mm, 60 * mm],
    )
    ideas_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.2),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_GREEN]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(ideas_table)

    event_rows = [["Date / ET", "Catalyst", "Category", "Importance", "Source"]]
    for catalyst in list(catalysts)[:5]:
        event_rows.append(
            [
                Paragraph(f"{catalyst.date.strftime('%b %d')}<br/>{_clean(catalyst.time_et)}", small),
                Paragraph(_clean(catalyst.title), small),
                Paragraph(_clean(catalyst.category), small),
                Paragraph(_clean(catalyst.importance), small),
                Paragraph(_clean(catalyst.source), small),
            ]
        )
    if len(event_rows) == 1:
        event_rows.append(["-", "No verified catalyst in the configured window", "-", "-", "-"])
    events_table = Table(event_rows, colWidths=[24 * mm, 70 * mm, 29 * mm, 24 * mm, 31 * mm], repeatRows=1)
    events_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.2),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(KeepTogether([Paragraph("Upcoming verified catalysts", section), events_table]))

    risks = " | ".join(_clean(item) for item in brief["risks"][:3])
    story.extend(
        [
            Spacer(1, 2 * mm),
            Paragraph(f"<b>Risk notes:</b> {risks}", small),
            Paragraph(
                "Evidence scores are deterministic ranking proxies, not probabilities. Prices are saved session closes. "
                "Options pressure uses the identified feed and may be indicative. No broker order can be created.",
                small,
            ),
        ]
    )
    document.build(story)
    return output.getvalue()
