#!/usr/bin/env python3
"""
Lion of Functional Safety Engine\u2122 — Professional Compliance Assessment Report Generator (PDF)
========================================================================
Generates audit-grade PDF compliance reports using ReportLab.
Matches the structure and content of the DOCX report generator.

Usage:
  python report_generator.py compliance_report_agnostic.json [output.pdf]

Or from code:
  from report_generator import generate_compliance_pdf
  generate_compliance_pdf(report_dict, "output.pdf")
"""

import json
import os
import sys
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    KeepTogether, HRFlowable, Image as RLImage
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.pdfgen import canvas
import tempfile

# Import chart generators from DOCX module for shared use
try:
    from report_generator_docx import (
        generate_layer_chart, generate_severity_pie, generate_compliance_gauge,
        generate_trace_coverage_chart, generate_confirmation_review_chart,
        generate_verification_coverage_chart, generate_radar_chart,
        generate_risk_heatmap, generate_waterfall_chart,
        generate_traceability_slope_chart, generate_safety_decomposition_tree,
        generate_compliance_timeline_chart,
    )
    HAS_CHARTS = True
except ImportError:
    HAS_CHARTS = False


# ═══════════════════════════════════════════════════
#  COLOR PALETTE
# ═══════════════════════════════════════════════════

NAVY       = HexColor("#0D2B4E")
DARK_BLUE  = HexColor("#1A4780")
MID_BLUE   = HexColor("#2E6EB5")
LIGHT_BLUE = HexColor("#D9E6F2")
ACCENT     = HexColor("#D46B08")
GREEN_OK   = HexColor("#166B34")
YELLOW_WARN = HexColor("#CA8A04")
RED_CRIT   = HexColor("#B91C1C")
GREY_TEXT  = HexColor("#4B5563")
GREY_LIGHT = HexColor("#F3F4F6")
GREY_LINE  = HexColor("#D1D5DB")
WHITE_CLR  = HexColor("#FFFFFF")
BLACK_CLR  = HexColor("#1F2A37")


# ═══════════════════════════════════════════════════
#  STYLES
# ═══════════════════════════════════════════════════

def get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'CoverTitle', parent=styles['Title'],
        fontSize=24, leading=30, textColor=NAVY,
        alignment=TA_CENTER, spaceAfter=6, fontName='Helvetica-Bold'))

    styles.add(ParagraphStyle(
        'CoverSub', parent=styles['Normal'],
        fontSize=12, leading=16, textColor=DARK_BLUE,
        alignment=TA_CENTER, spaceAfter=20, fontName='Helvetica-Oblique'))

    styles.add(ParagraphStyle(
        'SectionH1', parent=styles['Heading1'],
        fontSize=16, leading=20, textColor=NAVY,
        spaceAfter=8, spaceBefore=16, fontName='Helvetica-Bold'))

    styles.add(ParagraphStyle(
        'SectionH2', parent=styles['Heading2'],
        fontSize=12, leading=15, textColor=DARK_BLUE,
        spaceAfter=6, spaceBefore=10, fontName='Helvetica-Bold'))

    styles.add(ParagraphStyle(
        'BodyText2', parent=styles['Normal'],
        fontSize=9, leading=13, textColor=BLACK_CLR,
        alignment=TA_JUSTIFY, spaceAfter=6))

    styles.add(ParagraphStyle(
        'SmallGrey', parent=styles['Normal'],
        fontSize=7.5, leading=10, textColor=GREY_TEXT,
        spaceAfter=4))

    styles.add(ParagraphStyle(
        'CellText', parent=styles['Normal'],
        fontSize=7.5, leading=10, textColor=BLACK_CLR))

    styles.add(ParagraphStyle(
        'CellBold', parent=styles['Normal'],
        fontSize=7.5, leading=10, textColor=BLACK_CLR, fontName='Helvetica-Bold'))

    styles.add(ParagraphStyle(
        'CellHeader', parent=styles['Normal'],
        fontSize=7.5, leading=10, textColor=white, fontName='Helvetica-Bold'))

    styles.add(ParagraphStyle(
        'VerdictBanner', parent=styles['Normal'],
        fontSize=16, leading=22, textColor=white,
        alignment=TA_CENTER, fontName='Helvetica-Bold'))

    styles.add(ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=7, leading=9, textColor=GREY_TEXT, alignment=TA_CENTER))

    return styles


# ═══════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════

def score_color(score):
    if score >= 80: return GREEN_OK
    if score >= 60: return YELLOW_WARN
    return RED_CRIT

def verdict_color(verdict):
    v = (verdict or "").upper()
    if ("NOT COMPLIANT" in v or "NOT ACCEPTABLE" in v) and "CONDITIONALLY" not in v:
        return RED_CRIT
    if "CONDITIONALLY" in v:
        return ACCENT
    return GREEN_OK

def severity_color(sev):
    sev = (sev or "").upper()
    if sev == "CRITICAL": return RED_CRIT
    if sev == "MAJOR": return ACCENT
    if sev == "WARNING": return YELLOW_WARN
    return GREY_TEXT

def status_color(status):
    s = (status or "").lower()
    if "not compliant" in s or "non-compliant" in s: return RED_CRIT
    if "missing" in s: return RED_CRIT
    if "partial" in s or "conditional" in s: return YELLOW_WARN
    if s == "n/a": return GREY_TEXT
    if "compliant" in s or "acceptable" in s: return GREEN_OK
    return GREY_TEXT

def make_hr(width=6.7*inch, thickness=1, color=NAVY):
    return HRFlowable(width=width, thickness=thickness, color=color,
                      spaceBefore=4, spaceAfter=8)

def make_table(data, col_widths=None, header=True, alt_row=True):
    """Build a styled table."""
    if not data:
        return Spacer(1, 0)
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style_cmds = [
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('TEXTCOLOR', (0, 0), (-1, -1), BLACK_CLR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, GREY_LINE),
    ]
    if header:
        style_cmds.extend([
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ])
    if alt_row and len(data) > 2:
        for i in range(2, len(data), 2):
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), GREY_LIGHT))
    t.setStyle(TableStyle(style_cmds))
    return t

def resolve_fields(report):
    project = report.get("project", {})
    if not project:
        art_src = report.get("artifact_source", "")
        project = {"name": os.path.basename(art_src).replace(".json", "").replace("_", " ").title()
                    if art_src else "N/A"}
    std_name = report.get("standard_name",
               report.get("standard",
               report.get("discovered_schema", {}).get("standard_name", "")))
    if not std_name:
        src = report.get("standard_source", "")
        if "26262" in src: std_name = "ISO 26262:2018 — Functional Safety"
        elif "21434" in src: std_name = "ISO/SAE 21434 — Cybersecurity Engineering"
        else: std_name = os.path.basename(src) if src else "Standard"
    return project, std_name


# ═══════════════════════════════════════════════════
#  PAGE TEMPLATE
# ═══════════════════════════════════════════════════

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 7)
        self.setFillColor(GREY_TEXT)
        self.drawCentredString(
            letter[0] / 2,
            0.4 * inch,
            f"Lion of Functional Safety Engine\u2122 — Page {self._pageNumber} of {page_count}"
        )


# ═══════════════════════════════════════════════════
#  MAIN REPORT BUILDER
# ═══════════════════════════════════════════════════

def generate_compliance_pdf(report: dict, output_path: str):
    """Generate professional PDF compliance assessment report."""

    styles = get_styles()
    elements = []

    # ── Resolve Fields ──
    project, std_name = resolve_fields(report)
    score = report.get("compliance_score", 0)
    grd = report.get("grade", "N/A")
    gap = report.get("gap_analysis", {})
    layers = report.get("layer_results", {})
    summary = report.get("summary", {})
    risk_level = report.get("target_risk_level", "")
    check_date = report.get("check_date", "")[:10]
    decision = report.get("assessment_decision", {})
    wp_register = report.get("work_product_register", [])
    trace_mx = report.get("traceability_matrix", {})
    stds_assessed = report.get("standards_assessed", [])
    arts_assessed = report.get("artifacts_assessed", [])
    sev_counts = gap.get("severity_counts", {})
    verdict = decision.get("verdict", "PENDING")

    grade_text = grd
    for sep in ["\u2014", "—", " - ", "-"]:
        if sep in grd:
            grade_text = grd.split(sep)[0].strip()
            break

    doc_id = f"CIQ-FSA-{check_date.replace('-', '')}" if check_date else "CIQ-FSA-DRAFT"

    # ═══════════════════════════════════
    #  COVER PAGE
    # ═══════════════════════════════════
    elements.append(Spacer(1, 1.5*inch))
    elements.append(make_hr(thickness=3))
    elements.append(Paragraph("FUNCTIONAL SAFETY<br/>COMPLIANCE ASSESSMENT REPORT",
                              styles['CoverTitle']))
    elements.append(make_hr(thickness=3))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph(std_name, styles['CoverSub']))
    elements.append(Spacer(1, 0.3*inch))

    # Info table
    info_data = [
        ["Document ID", doc_id],
        ["Revision", "1.0"],
        ["Assessment Date", check_date],
        ["Project", project.get("name", "N/A")],
        ["Standard", std_name],
        ["Target ASIL", risk_level or "All"],
        ["Overall Score", f"{score}%"],
        ["Grade", grd],
        ["Verdict", verdict],
    ]
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_style = [
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), NAVY),
        ('TEXTCOLOR', (1, 0), (1, -1), BLACK_CLR),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, GREY_LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]
    info_table.setStyle(TableStyle(info_style))
    elements.append(info_table)

    elements.append(Spacer(1, 0.3*inch))

    # Verdict banner
    vc = verdict_color(verdict)
    v_data = [[Paragraph(f"<b>{verdict}</b>", styles['VerdictBanner'])]]
    v_table = Table(v_data, colWidths=[5*inch])
    v_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), vc),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(v_table)

    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph("CONFIDENTIAL — FOR AUTHORIZED RECIPIENTS ONLY",
                              styles['SmallGrey']))
    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  1. EXECUTIVE SUMMARY
    # ═══════════════════════════════════
    elements.append(Paragraph("1.  Executive Summary", styles['SectionH1']))
    elements.append(make_hr())

    vc_hex = f"#{vc.hexval()[2:]}" if hasattr(vc, 'hexval') else "#166B34"
    elements.append(Paragraph(
        f'Assessment Verdict: <b><font color="{vc_hex}">{verdict}</font></b>',
        styles['BodyText2']))
    elements.append(Paragraph(decision.get("description", ""), styles['BodyText2']))

    if decision.get("conditions"):
        conds_html = "<br/>".join(f"&bull; {c}" for c in decision["conditions"])
        elements.append(Paragraph(
            f'<b><font color="#D46B08">Conditions:</font></b><br/>{conds_html}',
            styles['BodyText2']))

    elements.append(Spacer(1, 0.15*inch))

    # Metrics row
    met_data = [
        ["Compliance Score", "Grade", "Findings", "Critical", "Risk Score"],
        [f"{score}%", grade_text,
         str(summary.get("total_findings", 0)),
         str(sev_counts.get("CRITICAL", 0)),
         str(summary.get("risk_score", 0))],
    ]
    met_table = Table(met_data, colWidths=[1.34*inch]*5)
    met_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('TEXTCOLOR', (0, 0), (-1, 0), GREY_TEXT),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 13),
        ('TEXTCOLOR', (0, 1), (-1, 1), NAVY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, GREY_LINE),
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, GREY_LINE),
    ]))
    elements.append(met_table)

    elements.append(Spacer(1, 0.15*inch))

    # Priority actions
    elements.append(Paragraph("Priority Actions", styles['SectionH2']))
    recs = summary.get("top_recommendations", gap.get("recommendations", []))
    for i, rec in enumerate(recs[:5], 1):
        display = rec.replace("[HIGH]", "").replace("[MEDIUM]", "").replace("[LOW]", "").strip()
        elements.append(Paragraph(f"<b>{i}.</b> {display}", styles['BodyText2']))

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  2. ASSESSMENT SCOPE & METHODOLOGY
    # ═══════════════════════════════════
    elements.append(Paragraph("2.  Assessment Scope &amp; Methodology", styles['SectionH1']))
    elements.append(make_hr())

    elements.append(Paragraph("2.1  Scope of Assessment", styles['SectionH2']))
    elements.append(Paragraph(
        f"This report presents the results of an automated compliance assessment against "
        f"<b>{std_name}</b>. The assessment covers all applicable parts and clauses.",
        styles['BodyText2']))

    elements.append(Paragraph("2.4  Assessment Methodology", styles['SectionH2']))
    elements.append(Paragraph(
        "The assessment employs an 8-layer algorithmic analysis pipeline with "
        "risk-weighted ensemble scoring.",
        styles['BodyText2']))

    method_data = [
        ["Layer", "Technique", "Weight", "Purpose"],
        ["1. Node Coverage", "Decision Tree", "20%", "Requirement clause coverage"],
        ["2. Content Alignment", "TF-IDF + Cosine", "15%", "Textual similarity measurement"],
        ["3. Semantic Matching", "Ratcliff-Obershelp", "10%", "Fuzzy semantic matching"],
        ["4. Concept Coverage", "Set Analysis", "10%", "Required concept verification"],
        ["5. Reference Integrity", "Graph BFS", "15%", "Cross-reference validation"],
        ["6. Method Audit", "Risk-Aware Rules", "10%", "Method/technique verification"],
        ["7. Traceability Chain", "Directed Graph", "20%", "Bidirectional trace paths"],
        ["8. Gap Analysis", "Bayesian Risk", "—", "Risk scoring and prioritization"],
    ]
    elements.append(make_table(method_data, col_widths=[1.4*inch, 1.3*inch, 0.6*inch, 3.4*inch]))

    elements.append(Spacer(1, 0.1*inch))

    # Assessment criteria
    elements.append(Paragraph("2.5  Assessment Criteria", styles['SectionH2']))
    crit_data = [
        ["Verdict", "Criteria", "Action"],
        ["COMPLIANT", "Score \u2265 85%, 0 critical, \u2264 2 major", "No corrective action"],
        ["CONDITIONALLY\nCOMPLIANT", "Score \u2265 60%, \u2264 2 critical", "Corrective actions required"],
        ["NOT COMPLIANT", "Score < 60% or > 2 critical", "Remediation and re-assessment"],
    ]
    elements.append(make_table(crit_data, col_widths=[1.6*inch, 2.5*inch, 2.6*inch]))

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  3. WORK PRODUCT REGISTER
    # ═══════════════════════════════════
    elements.append(Paragraph("3.  Work Product Register", styles['SectionH1']))
    elements.append(make_hr())

    elements.append(Paragraph(
        "The following work products were submitted and evaluated.",
        styles['BodyText2']))

    if wp_register:
        wp_data = [["#", "Work Product", "Format", "Mapped Parts", "Findings", "Status"]]
        for idx, wp in enumerate(wp_register):
            name = (wp.get("name", "") or wp.get("id", ""))[:35]
            fmt = wp.get("format", "—")
            parts = ", ".join(p.replace("part_", "P") for p in wp.get("mapped_parts", []))[:25] or "—"
            findings = f"{wp.get('critical_count', 0)}C/{wp.get('major_count', 0)}M"
            status = wp.get("status", "—")
            wp_data.append([str(idx+1), name, fmt, parts, findings, status])
        elements.append(make_table(wp_data,
                                   col_widths=[0.3*inch, 2.2*inch, 0.7*inch, 1.3*inch, 0.8*inch, 1.4*inch]))

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  4. COMPLIANCE DASHBOARD
    # ═══════════════════════════════════
    elements.append(Paragraph("4.  Compliance Assessment Dashboard", styles['SectionH1']))
    elements.append(make_hr())

    sc = score_color(score)
    sc_hex = f"#{sc.hexval()[2:]}" if hasattr(sc, 'hexval') else "#166B34"
    elements.append(Paragraph(
        f'<font size="24" color="{sc_hex}"><b>{score}%</b></font>'
        f'&nbsp;&nbsp;&nbsp;'
        f'<font size="24" color="{sc_hex}"><b>{grade_text}</b></font>',
        ParagraphStyle('DashScore', parent=styles['Normal'], alignment=TA_CENTER,
                       spaceAfter=18, spaceBefore=6)))

    # Severity boxes
    sev_data = [
        ["CRITICAL", "MAJOR", "WARNING", "INFO"],
        [str(sev_counts.get("CRITICAL", 0)), str(sev_counts.get("MAJOR", 0)),
         str(sev_counts.get("WARNING", 0)), str(sev_counts.get("INFO", 0))],
    ]
    sev_table = Table(sev_data, colWidths=[1.67*inch]*4)
    sev_style_cmds = [
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 16),
        ('TEXTCOLOR', (0, 0), (-1, -1), white),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (0, 0), (0, -1), RED_CRIT),
        ('BACKGROUND', (1, 0), (1, -1), ACCENT),
        ('BACKGROUND', (2, 0), (2, -1), YELLOW_WARN),
        ('BACKGROUND', (3, 0), (3, -1), GREY_TEXT),
    ]
    sev_table.setStyle(TableStyle(sev_style_cmds))
    elements.append(sev_table)

    elements.append(Spacer(1, 0.15*inch))

    # Layer performance
    elements.append(Paragraph("Algorithm Layer Performance", styles['SectionH2']))
    layer_labels = {
        "node_coverage": "Node Coverage (20%)",
        "content_alignment": "Content Alignment (15%)",
        "semantic_matching": "Semantic Matching (10%)",
        "concept_coverage": "Concept Coverage (10%)",
        "reference_integrity": "Reference Integrity (15%)",
        "method_audit": "Method Audit (10%)",
        "traceability_chain": "Traceability Chain (20%)",
    }
    # ── Chart images for PDF (shared with DOCX generator) ──
    _pdf_chart_files = []

    layer_weights_dict = {
        "node_coverage": 0.20, "content_alignment": 0.15,
        "semantic_matching": 0.10, "concept_coverage": 0.10,
        "reference_integrity": 0.15, "method_audit": 0.10,
        "traceability_chain": 0.20,
    }
    layer_labels_short = {
        "node_coverage": "Node Coverage",
        "content_alignment": "Content Alignment",
        "semantic_matching": "Semantic Matching",
        "concept_coverage": "Concept Coverage",
        "reference_integrity": "Reference Integrity",
        "method_audit": "Method Audit",
        "traceability_chain": "Traceability Chain",
    }

    if HAS_CHARTS:
        # Layer performance chart
        layer_chart = generate_layer_chart(layers, layer_labels_short, layer_weights_dict)
        if layer_chart:
            _pdf_chart_files.append(layer_chart)
            elements.append(RLImage(layer_chart, width=5.5*inch, height=2.8*inch))
            elements.append(Spacer(1, 0.1*inch))

        # Severity donut chart
        sev_chart = generate_severity_pie(sev_counts)
        if sev_chart:
            _pdf_chart_files.append(sev_chart)
            elements.append(RLImage(sev_chart, width=3.0*inch, height=3.0*inch))
            elements.append(Spacer(1, 0.1*inch))

        # Radar chart
        radar_chart = generate_radar_chart(layers, layer_labels_short)
        if radar_chart:
            _pdf_chart_files.append(radar_chart)
            elements.append(Paragraph("Multi-Layer Compliance Radar", styles['SectionH2']))
            elements.append(RLImage(radar_chart, width=4.0*inch, height=4.0*inch))
            elements.append(Spacer(1, 0.1*inch))

        # Waterfall chart
        waterfall_chart = generate_waterfall_chart(layers, layer_labels_short, layer_weights_dict, score)
        if waterfall_chart:
            _pdf_chart_files.append(waterfall_chart)
            elements.append(Paragraph("Score Composition Waterfall", styles['SectionH2']))
            elements.append(RLImage(waterfall_chart, width=5.5*inch, height=2.8*inch))
            elements.append(Spacer(1, 0.1*inch))
    else:
        # Fallback text-based layer display
        for key, label in layer_labels.items():
            if key in layers:
                lscore = layers[key].get("score", 0)
                lsc = score_color(lscore)
                lsc_hex = f"#{lsc.hexval()[2:]}" if hasattr(lsc, 'hexval') else "#4B5563"
                elements.append(Paragraph(
                    f'<font size="8" color="#4B5563">{label}</font>&nbsp;&nbsp;'
                    f'<font size="8" color="{lsc_hex}"><b>{lscore:.0f}%</b></font>',
                    styles['SmallGrey']))

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  5. REQUIREMENTS COMPLIANCE MATRIX
    # ═══════════════════════════════════
    elements.append(Paragraph("5.  Requirements Compliance Matrix", styles['SectionH1']))
    elements.append(make_hr())

    nc = layers.get("node_coverage", {})
    ca = layers.get("content_alignment", {})
    ca_scores = ca.get("scores", {})
    sorted_findings = sorted(nc.get("findings", []),
                             key=lambda f: (f.get("group", ""), f.get("node_id", "")))

    missing_ids = set()
    partial_ids = set()

    if sorted_findings:
        matrix_data = [["Part", "Clause", "Title", "Status", "Align %"]]
        for f in sorted_findings[:80]:
            nid = f.get("node_id", "")
            group = f.get("group", "").replace("part_", "Part ")
            title = f.get("title", "")[:40]
            ftype = f.get("type", "")
            if ftype == "MISSING_COVERAGE":
                st = "Missing"
                missing_ids.add(nid)
                pct = "—"
            elif ftype == "LOW_CONTENT_ALIGNMENT":
                st = "Not Compliant"
                missing_ids.add(nid)
                pct_val = ca_scores.get(nid, "—")
                pct = f"{pct_val}%" if pct_val != "—" else "—"
            else:
                st = "Partially Compliant"
                partial_ids.add(nid)
                pct_val = ca_scores.get(nid, "—")
                pct = f"{pct_val}%" if pct_val != "—" else "—"
            matrix_data.append([group, nid, title, st, pct])
        elements.append(make_table(matrix_data,
                                   col_widths=[0.8*inch, 0.9*inch, 2.5*inch, 1.2*inch, 0.7*inch]))

        total_applicable = nc.get("applicable_nodes", 0)
        n_covered = total_applicable - len(missing_ids) - len(partial_ids)
        elements.append(Paragraph(
            f"<b>Summary:</b> {n_covered} compliant, {len(partial_ids)} partial, "
            f"{len(missing_ids)} non-compliant of {total_applicable} applicable.",
            styles['BodyText2']))
    else:
        elements.append(Paragraph(
            '<font color="#166B34"><b>All requirement clauses are fully covered.</b></font>',
            styles['BodyText2']))

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  6. TRACEABILITY MATRIX
    # ═══════════════════════════════════
    elements.append(Paragraph("6.  Traceability Matrix", styles['SectionH1']))
    elements.append(make_hr())

    trace_cov = trace_mx.get("coverage_summary", {})
    elements.append(Paragraph(
        "Bidirectional traceability is assessed per ISO 26262 requirements.",
        styles['BodyText2']))

    trace_met = [
        ["Total Reqs", "Traced", "Coverage", "Orphan Reqs", "Orphan Artifacts"],
        [str(trace_cov.get("total_requirements", 0)),
         str(trace_cov.get("traced_requirements", 0)),
         f"{trace_cov.get('trace_coverage_pct', 0)}%",
         str(trace_cov.get("orphan_requirements_count", 0)),
         str(trace_cov.get("orphan_artifacts_count", 0))],
    ]
    tmet = Table(trace_met, colWidths=[1.34*inch]*5)
    tmet.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('TEXTCOLOR', (0, 0), (-1, 0), GREY_TEXT),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 12),
        ('TEXTCOLOR', (0, 1), (-1, 1), NAVY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, GREY_LINE),
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, GREY_LINE),
    ]))
    elements.append(tmet)
    elements.append(Spacer(1, 0.1*inch))

    # ── Charts for traceability section ──
    if HAS_CHARTS:
        trace_bar_chart = generate_trace_coverage_chart(trace_cov)
        if trace_bar_chart:
            _pdf_chart_files.append(trace_bar_chart)
            elements.append(RLImage(trace_bar_chart, width=4.0*inch, height=2.4*inch))
            elements.append(Spacer(1, 0.1*inch))

        slope_chart = generate_traceability_slope_chart(trace_mx, layers)
        if slope_chart:
            _pdf_chart_files.append(slope_chart)
            elements.append(Paragraph("Requirement–Evidence Flow", styles['SectionH2']))
            elements.append(RLImage(slope_chart, width=5.0*inch, height=3.2*inch))
            elements.append(Spacer(1, 0.1*inch))

        tree_chart = generate_safety_decomposition_tree(report)
        if tree_chart:
            _pdf_chart_files.append(tree_chart)
            elements.append(Paragraph("Safety Requirements Decomposition", styles['SectionH2']))
            try:
                elements.append(RLImage(tree_chart, width=5.0*inch, height=3.5*inch))
                elements.append(Spacer(1, 0.1*inch))
            except Exception:
                pass

    # Missing traces
    tc = layers.get("traceability_chain", {})
    tc_findings = tc.get("findings", [])
    trace_findings = [f for f in tc_findings if f.get("type") != "NO_TRACEABILITY_MODEL"]
    if trace_findings:
        elements.append(Paragraph("Missing Traceability Links", styles['SectionH2']))
        tt_data = [["From", "To", "Type", "Status"]]
        for f in trace_findings[:25]:
            tt_data.append([
                f.get("from", "—"), f.get("to", "—"),
                f.get("type", "—"), "MISSING"
            ])
        elements.append(make_table(tt_data,
                                   col_widths=[1.8*inch, 1.8*inch, 1.6*inch, 1.5*inch]))

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  7. GAP ANALYSIS
    # ═══════════════════════════════════
    elements.append(Paragraph("7.  Gap Analysis", styles['SectionH1']))
    elements.append(make_hr())

    gaps = gap.get("gaps", [])
    if gaps:
        gap_data = [["Priority", "Gap Category", "Count", "Risk", "Top Finding"]]
        for g_item in gaps[:25]:
            priority = g_item.get("priority", "LOW")
            key = g_item.get("key", "")[:35]
            count = g_item.get("count", 0)
            risk_w = g_item.get("risk_weighted", 0)
            top_msg = ""
            fl = g_item.get("findings", [])
            if fl:
                top_msg = fl[0].get("message", "")[:90]
            gap_data.append([priority, key, str(count), str(risk_w), top_msg])
        elements.append(make_table(gap_data,
                                   col_widths=[0.7*inch, 1.8*inch, 0.5*inch, 0.6*inch, 3.1*inch]))

    # ── Risk heatmap ──
    if HAS_CHARTS:
        heatmap = generate_risk_heatmap(gaps, layers)
        if heatmap:
            _pdf_chart_files.append(heatmap)
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph("Risk Heatmap — Gap Category × Severity", styles['SectionH2']))
            elements.append(RLImage(heatmap, width=5.0*inch, height=3.0*inch))

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  8-9. METHOD AUDIT + RISK
    # ═══════════════════════════════════
    elements.append(Paragraph("8.  Method &amp; Practice Audit", styles['SectionH1']))
    elements.append(make_hr())

    ma = layers.get("method_audit", {})
    elements.append(Paragraph(
        f"Required methods: <b>{ma.get('required_count', 0)}</b>, "
        f"Documented: <b>{ma.get('matched_count', 0)}</b> "
        f"(<b>{ma.get('score', 0):.0f}%</b>)",
        styles['BodyText2']))

    ma_findings = ma.get("findings", [])
    if ma_findings:
        ma_data = [["Severity", "Activity", "Required Methods"]]
        for f in ma_findings[:15]:
            sev = f.get("severity", "WARNING")
            activity = f.get("activity", "")[:35]
            methods = ", ".join(f.get("methods", [])[:4])
            ma_data.append([sev, activity, methods])
        elements.append(make_table(ma_data,
                                   col_widths=[0.8*inch, 2.4*inch, 3.5*inch]))

    elements.append(Spacer(1, 0.2*inch))

    elements.append(Paragraph("9.  Risk Assessment", styles['SectionH1']))
    elements.append(make_hr())

    risk_met = [
        ["Total Risk", "Critical", "Major", "Warnings"],
        [str(gap.get("total_risk", 0)),
         str(sev_counts.get("CRITICAL", 0)),
         str(sev_counts.get("MAJOR", 0)),
         str(sev_counts.get("WARNING", 0))],
    ]
    rmet = Table(risk_met, colWidths=[1.67*inch]*4)
    rmet.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('TEXTCOLOR', (0, 0), (-1, 0), GREY_TEXT),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 13),
        ('TEXTCOLOR', (0, 1), (-1, 1), NAVY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, GREY_LINE),
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, GREY_LINE),
    ]))
    elements.append(rmet)

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  10. CORRECTIVE ACTIONS
    # ═══════════════════════════════════
    elements.append(Paragraph("10.  Corrective Action Register", styles['SectionH1']))
    elements.append(make_hr())

    if recs:
        ca_data = [["#", "Priority", "Corrective Action", "Status"]]
        for idx, rec in enumerate(recs[:15]):
            if "[HIGH]" in rec: pri = "HIGH"
            elif "[MEDIUM]" in rec: pri = "MEDIUM"
            else: pri = "LOW"
            display = rec.replace("[HIGH]", "").replace("[MEDIUM]", "").replace("[LOW]", "").strip()
            ca_data.append([str(idx+1), pri, display[:90], "OPEN"])
        elements.append(make_table(ca_data,
                                   col_widths=[0.3*inch, 0.7*inch, 4.8*inch, 0.9*inch]))

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  11. CONFIRMATION REVIEW (ISO 26262-2:2018 §6.4.4)
    # ═══════════════════════════════════
    elements.append(Paragraph("11.  Confirmation Review", styles['SectionH1']))
    elements.append(make_hr())

    conf_review = report.get("confirmation_review", {})
    conf_checklist = conf_review.get("checklist", [])
    conf_summary = conf_review.get("summary", {})

    elements.append(Paragraph(
        "Per ISO 26262-2:2018 §6.4.4, a confirmation review evaluates whether the work "
        "products achieve the safety objectives and comply with applicable requirements.",
        styles['BodyText2']))

    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("Reviewer Independence", styles['SectionH2']))

    req_indep = conf_review.get("required_independence", "I1")
    target_asil_cr = conf_review.get("target_asil", "Not specified")
    indep_data = [
        ["Parameter", "Value"],
        ["Target ASIL", str(target_asil_cr)],
        ["Required Independence", req_indep],
        ["I0: Same person", "QM only"],
        ["I1: Different person, same team", "ASIL A\u2013B"],
        ["I2: Different department", "ASIL C"],
        ["I3: Different organization", "ASIL D"],
    ]
    elements.append(make_table(indep_data, col_widths=[3*inch, 3.5*inch]))
    elements.append(Spacer(1, 0.15*inch))

    elements.append(Paragraph("Confirmation Checklist", styles['SectionH2']))
    if conf_checklist:
        cr_data = [["ID", "Item", "Status", "Evidence"]]
        for item in conf_checklist:
            cr_data.append([
                item.get("id", ""),
                item.get("item", ""),
                item.get("status", "N/A"),
                item.get("evidence", "")[:70],
            ])
        elements.append(make_table(cr_data,
                                   col_widths=[0.6*inch, 1.2*inch, 0.6*inch, 4.3*inch]))

    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("Confirmation Review Summary", styles['SectionH2']))

    cr_result = conf_summary.get("result", "N/A")
    cr_bg = GREEN_OK if cr_result == "PASSED" else (YELLOW_WARN if cr_result == "CONDITIONAL" else RED_CRIT)
    cr_banner_data = [[Paragraph(
        f'<b>CONFIRMATION REVIEW: {cr_result}</b>',
        ParagraphStyle('CRBanner', parent=styles['VerdictBanner']))]]
    cr_banner_table = Table(cr_banner_data, colWidths=[5*inch])
    cr_banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cr_bg),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(cr_banner_table)

    cr_stats_text = (f"Pass: {conf_summary.get('pass', 0)} | "
                     f"Partial: {conf_summary.get('partial', 0)} | "
                     f"Fail: {conf_summary.get('fail', 0)} | "
                     f"Pass Rate: {conf_summary.get('pass_rate', 0):.0f}%")
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph(cr_stats_text, styles['BodyText2']))

    # Confirmation review chart
    if HAS_CHARTS and conf_summary:
        conf_chart = generate_confirmation_review_chart(conf_summary)
        if conf_chart:
            _pdf_chart_files.append(conf_chart)
            elements.append(Spacer(1, 0.1*inch))
            elements.append(RLImage(conf_chart, width=3.5*inch, height=2.2*inch))

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  12. VERIFICATION REVIEW (ISO 26262-2:2018 §6.4.10 / Part 8)
    # ═══════════════════════════════════
    elements.append(Paragraph("12.  Verification Review", styles['SectionH1']))
    elements.append(make_hr())

    verif_review = report.get("verification_review", {})
    verif_wps = verif_review.get("work_products", [])
    verif_methods = verif_review.get("method_recommendations", [])
    verif_summary = verif_review.get("summary", {})
    verif_asil = verif_review.get("asil_key", "B")

    elements.append(Paragraph(
        "Per ISO 26262-2:2018 §6.4.10 and Part 8, verification confirms that work products "
        "satisfy the requirements allocated to them. Legend: ++ = Highly recommended, "
        "+ = Recommended, o = No recommendation.",
        styles['BodyText2']))
    elements.append(Spacer(1, 0.1*inch))

    elements.append(Paragraph("Verification Methods by ASIL", styles['SectionH2']))
    if verif_methods:
        vm_data = [["Method", "ASIL A", "ASIL B", "ASIL C", "ASIL D"]]
        for vm in verif_methods:
            vm_data.append([
                vm.get("method", ""),
                vm.get("asil_a", "o"),
                vm.get("asil_b", "o"),
                vm.get("asil_c", "o"),
                vm.get("asil_d", "o"),
            ])
        elements.append(make_table(vm_data,
                                   col_widths=[2.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch]))

    elements.append(Spacer(1, 0.15*inch))
    elements.append(Paragraph(f"Work Product Verification Status (ASIL {verif_asil})", styles['SectionH2']))

    if verif_wps:
        vw_data = [["Work Product", "Type", "Methods Applied", "Cov.", "Status"]]
        for vw in verif_wps:
            methods_str = ", ".join(vw.get("methods_found", []))[:40] or "None"
            vw_data.append([
                vw.get("name", "")[:42],
                vw.get("wp_type", "").replace("_", " ").title()[:20],
                methods_str,
                f"{vw.get('coverage_pct', 0):.0f}%",
                vw.get("status", "N/A"),
            ])
        elements.append(make_table(vw_data,
                                   col_widths=[2.1*inch, 1.1*inch, 1.7*inch, 0.55*inch, 0.75*inch]))

    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("Verification Review Summary", styles['SectionH2']))

    vr_result = verif_summary.get("result", "N/A")
    vr_bg = GREEN_OK if vr_result == "PASSED" else (YELLOW_WARN if vr_result == "CONDITIONAL" else RED_CRIT)
    vr_banner_data = [[Paragraph(
        f'<b>VERIFICATION REVIEW: {vr_result}</b>',
        ParagraphStyle('VRBanner', parent=styles['VerdictBanner']))]]
    vr_banner_table = Table(vr_banner_data, colWidths=[5*inch])
    vr_banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), vr_bg),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(vr_banner_table)

    vr_stats_text = (f"Adequate: {verif_summary.get('adequate', 0)} | "
                     f"Partial: {verif_summary.get('partial', 0)} | "
                     f"Insufficient: {verif_summary.get('insufficient', 0)} | "
                     f"Adequacy Rate: {verif_summary.get('adequacy_rate', 0):.0f}%")
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph(vr_stats_text, styles['BodyText2']))

    # Verification coverage chart
    if HAS_CHARTS and verif_wps:
        verif_chart = generate_verification_coverage_chart(verif_wps)
        if verif_chart:
            _pdf_chart_files.append(verif_chart)
            elements.append(Spacer(1, 0.1*inch))
            elements.append(RLImage(verif_chart, width=5.0*inch, height=3.0*inch))

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  13. ASSESSMENT DECISION
    # ═══════════════════════════════════
    elements.append(Paragraph("13.  Assessment Decision", styles['SectionH1']))
    elements.append(make_hr())

    elements.append(Paragraph(
        "Based on the comprehensive 8-layer analysis, the following decision is rendered:",
        styles['BodyText2']))

    elements.append(Spacer(1, 0.15*inch))

    v_data2 = [[Paragraph(f"<b>ASSESSMENT VERDICT:  {verdict}</b>", styles['VerdictBanner'])]]
    v_table2 = Table(v_data2, colWidths=[5*inch])
    v_table2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), vc),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(v_table2)

    elements.append(Spacer(1, 0.15*inch))
    elements.append(Paragraph(decision.get("description", ""), styles['BodyText2']))

    if decision.get("conditions"):
        conds_text = "<br/>".join(f"&bull; {c}" for c in decision["conditions"])
        elements.append(Paragraph(
            f'<b><font color="#D46B08">Conditions:</font></b><br/>{conds_text}',
            styles['BodyText2']))

    elements.append(Spacer(1, 0.3*inch))

    # Signature block
    elements.append(Paragraph("Signatures", styles['SectionH2']))
    sig_data = [
        ["Role", "Name", "Signature / Date"],
        ["Assessor", "________________________________", "________________________________"],
        ["Safety Manager", "________________________________", "________________________________"],
        ["Project Manager", "________________________________", "________________________________"],
    ]
    elements.append(make_table(sig_data, col_widths=[1.5*inch, 2.5*inch, 2.7*inch]))

    elements.append(PageBreak())

    # ═══════════════════════════════════
    #  APPENDIX A: DETAILED FINDINGS
    # ═══════════════════════════════════
    elements.append(Paragraph("Appendix A:  Detailed Findings", styles['SectionH1']))
    elements.append(make_hr())

    all_findings = []
    for layer_name, layer_data in layers.items():
        for f in layer_data.get("findings", []):
            f_copy = dict(f)
            f_copy["_layer"] = layer_name
            all_findings.append(f_copy)

    sev_order = {"CRITICAL": 0, "MAJOR": 1, "WARNING": 2, "INFO": 3}
    all_findings.sort(key=lambda f: sev_order.get(f.get("severity", "INFO"), 4))

    if all_findings:
        app_data = [["Severity", "Layer", "Type", "Details"]]
        for f in all_findings[:80]:
            sev = f.get("severity", "INFO")
            layer = f.get("_layer", "").replace("_", " ").title()[:18]
            ftype = f.get("type", "")[:22]
            msg = f.get("message", "")[:90]
            app_data.append([sev, layer, ftype, msg])
        elements.append(make_table(app_data,
                                   col_widths=[0.7*inch, 1.2*inch, 1.4*inch, 3.4*inch]))

        if len(all_findings) > 80:
            elements.append(Paragraph(
                f"Showing 80 of {len(all_findings)} findings.",
                styles['SmallGrey']))

    # ── Final footer ──
    elements.append(Spacer(1, 0.3*inch))
    elements.append(make_hr(thickness=0.5, color=GREY_LINE))
    elements.append(Paragraph(
        f"Lion of Functional Safety Engine\u2122 — Functional Safety Compliance Assessment Report | "
        f"Document {doc_id} | Generated {check_date}",
        styles['Footer']))

    # ── Build PDF ──
    pdf_doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        topMargin=0.75*inch,
        bottomMargin=0.6*inch,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        title=f"Compliance Assessment Report — {doc_id}",
        author="Lion of Functional Safety Engine\u2122 v2.1",
    )
    pdf_doc.build(elements, canvasmaker=NumberedCanvas)

    # ── Cleanup temp chart files ──
    for cf in _pdf_chart_files:
        try:
            os.unlink(cf)
        except OSError:
            pass

    print(f"  [OK] PDF report generated: {output_path}")
    return output_path


# ═══════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python report_generator.py <compliance_report.json> [output.pdf]")
        sys.exit(1)

    report_path = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else report_path.replace(".json", ".pdf")

    with open(report_path, 'r') as f:
        report = json.load(f)

    generate_compliance_pdf(report, output)
