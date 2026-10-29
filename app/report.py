from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

ACCENT = colors.HexColor("#4f46e5")
STATUS_COLORS = {
    "Pass": colors.HexColor("#15803d"),
    "Fail": colors.HexColor("#b91c1c"),
    "Not assessed": colors.HexColor("#6b7280"),
}

LIMITATIONS = [
    "The audit evaluates a baseline Random Forest model trained inside this tool on the "
    "chosen dataset. It does not audit a separately trained production model.",
    "Scores, weights, thresholds and rating bands are adjustable heuristics chosen by the "
    "tool authors. They are not defined by any regulation.",
    "Fairness metrics can conflict with each other. Passing one does not mean the model is fair.",
    "Removing a sensitive column does not remove bias, because correlated features can act as proxies.",
    "Privacy screening is pattern-based. It cannot detect names or free-text addresses by value, "
    "and the Aadhaar check validates format only.",
    "Items marked Not assessed (for example human oversight and documentation) need manual review.",
    "This is a compliance readiness screen. It is not a legal opinion or a certification.",
]


def _fig_image(fig, width_cm=14):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    buf.seek(0)
    w, h = fig.get_size_inches()
    width = width_cm * cm
    return Image(buf, width=width, height=width * h / w)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 1 * cm, "AutoAudit-360 | compliance readiness screen, not a certification")
    canvas.drawRightString(A4[0] - 2 * cm, 1 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build_report(res, settings=None):
    """Build the PDF and return it as bytes. `res` is the dict returned by run_audit()."""
    settings = settings or {}
    comp = res["compliance"]

    ss = getSampleStyleSheet()
    body = ss["BodyText"]
    cell = ParagraphStyle("cell", parent=body, fontSize=8.5, leading=10.5)
    bold_cell = ParagraphStyle("boldcell", parent=cell, fontName="Helvetica-Bold")
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=ACCENT, spaceBefore=12)

    def P(text, style=body):
        return Paragraph(escape(str(text)), style)

    def grid(rows, widths, header=True):
        t = Table(rows, colWidths=[w * cm for w in widths], repeatRows=1 if header else 0)
        style = [
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        if header:
            style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff"))]
        t.setStyle(TableStyle(style))
        return t

    story = []

    # ---- Title and summary
    story.append(Paragraph("AutoAudit-360 Audit Report", ss["Title"]))
    story.append(P("End-to-End Trustworthy AI Audit and Regulatory Compliance Suite", body))
    story.append(P(f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}", cell))
    story.append(Spacer(1, 0.4 * cm))

    story.append(grid([
        [P("Trust Score", bold_cell), P(f"{comp['trust_score']}/100", cell),
         P("Rating", bold_cell), P(comp["rating"], cell)],
        [P("Checks passed", bold_cell), P(f"{comp['passed']} of {comp['assessed']} assessed", cell),
         P("Model accuracy", bold_cell), P(f"{res['accuracy']:.1%}", cell)],
        [P("Rows audited", bold_cell), P(f"{res['n_rows']:,}", cell),
         P("Needs manual review", bold_cell), P(f"{comp['not_assessed']} item(s)", cell)],
    ], [3.5, 5, 3.5, 5], header=False))

    story.append(Paragraph("Audit settings", h2))
    story.append(grid([
        [P("Dataset", bold_cell), P(settings.get("dataset", "-"), cell)],
        [P("Target column", bold_cell), P(settings.get("target", "-"), cell)],
        [P("Favourable outcome", bold_cell), P(settings.get("positive", "-"), cell)],
        [P("Sensitive attribute", bold_cell), P(settings.get("sensitive", "-"), cell)],
        [P("Fairness gap threshold", bold_cell), P(settings.get("fairness_threshold", "-"), cell)],
        [P("Max accuracy drop under noise", bold_cell), P(settings.get("max_drop", "-"), cell)],
    ], [6, 11], header=False))

    story.append(Paragraph("Module scores", h2))
    names = {"fairness": "Fairness", "explain": "Explainability",
             "robustness": "Robustness", "privacy": "Privacy"}
    story.append(grid(
        [[P("Module", bold_cell), P("Score (0-100)", bold_cell)]] +
        [[P(names[k], cell), P("-" if v is None else v, cell)]
         for k, v in comp["module_scores"].items()],
        [8, 9]))
    if res.get("dropped"):
        story.append(Spacer(1, 0.2 * cm))
        story.append(P("Columns skipped from the model (too many distinct values): "
                       + ", ".join(res["dropped"]), cell))

    # ---- Fairness
    story.append(PageBreak())
    f = res["fairness"]
    story.append(Paragraph("1. Fairness", h2))
    story.append(grid([
        [P("Metric", bold_cell), P("Value", bold_cell)],
        [P("Demographic parity difference", cell), P(f"{abs(f['demographic_parity_diff']):.3f}", cell)],
        [P("Equalized odds difference", cell), P(f"{abs(f['equalized_odds_diff']):.3f}", cell)],
        [P("Result", cell), P("Pass" if f["pass"] else "Fail", cell)],
    ], [8, 9]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(P("Accuracy by group", bold_cell))
    story.append(grid(
        [[P("Group", bold_cell), P("Accuracy", bold_cell)]] +
        [[P(k, cell), P(f"{v:.3f}", cell)] for k, v in f["accuracy_by_group"].items()],
        [8, 9]))

    # ---- Explainability
    e = res["explain"]
    story.append(Paragraph("2. Explainability", h2))
    story.append(P(f"Score: {e['score']}. Sensitive attribute in top 3 drivers: "
                   f"{'Yes' if e['sensitive_in_top3'] else 'No'}.", body))
    story.append(P("Top features: " + ", ".join(e["top_features"][:5]), cell))
    story.append(Spacer(1, 0.2 * cm))
    story.append(_fig_image(e["figure"], 13))

    # ---- Robustness
    story.append(PageBreak())
    r = res["robustness"]
    story.append(Paragraph("3. Robustness", h2))
    story.append(P(f"Score: {r['score']}. Result: {'Pass' if r['pass'] else 'Fail'}.", body))
    story.append(Spacer(1, 0.2 * cm))
    story.append(grid(
        [[P("Noise level", bold_cell), P("Accuracy", bold_cell), P("Accuracy drop", bold_cell)]] +
        [[P(k, cell), P(f"{r['noisy_accuracy'][k]:.3f}", cell), P(f"{r['accuracy_drop'][k]:.3f}", cell)]
         for k in r["noisy_accuracy"]],
        [5, 6, 6]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(_fig_image(r["figure"], 13))

    # ---- Privacy
    p = res["privacy"]
    story.append(Paragraph("4. Privacy", h2))
    story.append(P(f"Score: {p['score']}. Result: {'Pass' if p['pass'] else 'Fail'}.", body))
    if p["findings"]:
        story.append(Spacer(1, 0.2 * cm))
        story.append(grid(
            [[P("Column", bold_cell), P("Type", bold_cell), P("Evidence", bold_cell), P("Severity", bold_cell)]] +
            [[P(x["column"], cell), P(x["type"], cell), P(x["evidence"], cell), P(x["severity"], cell)]
             for x in p["findings"]],
            [3.5, 4, 7, 2.5]))
    else:
        story.append(P("No personal-data columns detected.", cell))

    # ---- Compliance checklist
    story.append(PageBreak())
    story.append(Paragraph("5. Compliance readiness checklist", h2))
    rows = [[P("Status", bold_cell), P("Requirement", bold_cell),
             P("Evidence", bold_cell), P("Regulations", bold_cell)]]
    extra = []
    for i, c in enumerate(comp["checklist"], start=1):
        rows.append([P(c["status"], bold_cell), P(c["requirement"], cell),
                     P(c["evidence"] or "-", cell), P("; ".join(c["regulations"]), cell)])
        extra.append(("TEXTCOLOR", (0, i), (0, i), STATUS_COLORS[c["status"]]))
    t = grid(rows, [2.3, 5.2, 4.8, 4.7])
    # Paragraph cells ignore TEXTCOLOR, so recolour the status paragraphs directly
    for i, c in enumerate(comp["checklist"], start=1):
        rows[i][0] = Paragraph(
            f'<font color="{STATUS_COLORS[c["status"]].hexval().replace("0x", "#")}">'
            f'{escape(c["status"])}</font>', bold_cell)
    t = grid(rows, [2.3, 5.2, 4.8, 4.7])
    story.append(t)

    # ---- Limitations
    story.append(Paragraph("Limitations", h2))
    for item in LIMITATIONS:
        story.append(Paragraph("&bull; " + escape(item), cell))
        story.append(Spacer(1, 0.1 * cm))
    story.append(Spacer(1, 0.3 * cm))
    story.append(P(comp["disclaimer"], cell))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm,
                            title="AutoAudit-360 Audit Report")
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()