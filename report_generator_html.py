"""
Lion of Functional Safety Engine™ — HTML Report Generator
Clean-sheet rewrite matching compliance_report_final_test.html structure
Generates compliance assessment reports with dark navy sidebar, sections as cards,
collapsible architecture, and comprehensive visualizations.
"""
import json
import html as html_mod
import base64
import math
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

# ============================================================================
# CONSTANTS
# ============================================================================

LAYER_WEIGHTS = {
    "node_coverage": 0.20,
    "content_alignment": 0.15,
    "semantic_matching": 0.10,
    "concept_coverage": 0.10,
    "reference_integrity": 0.15,
    "method_audit": 0.10,
    "traceability_chain": 0.20,
}

LAYER_LABELS = {
    "node_coverage": "Node Coverage",
    "content_alignment": "Content Alignment",
    "semantic_matching": "Semantic Matching",
    "concept_coverage": "Concept Coverage",
    "reference_integrity": "Reference Integrity",
    "method_audit": "Method Audit",
    "traceability_chain": "Traceability Chain",
}

LAYER_TECHNIQUES = {
    "node_coverage": "Decision Tree",
    "content_alignment": "TF-IDF + Cosine",
    "semantic_matching": "Ratcliff-Obershelp",
    "concept_coverage": "Set Analysis",
    "reference_integrity": "Graph BFS",
    "method_audit": "Risk-Aware Rules",
    "traceability_chain": "Directed Graph",
}

CHECKSHEET_REGISTRY = {
    "part_2": {
        "title": "Safety Management",
        "checksheets": ["Safety Plan", "DIA", "Impact Analysis", "Safety Case"],
        "total_items": 64,
    },
    "part_3": {
        "title": "Concept Phase",
        "checksheets": ["Item Definition", "HARA", "Functional Safety Concept"],
        "total_items": 55,
    },
    "part_4": {
        "title": "System Level",
        "checksheets": ["Technical Safety Concept", "Integration & Test Strategy", "Safety Validation"],
        "total_items": 143,
    },
    "part_5": {
        "title": "Hardware Level",
        "checksheets": ["Hardware Development"],
        "total_items": 37,
    },
    "part_6": {
        "title": "Software Level",
        "checksheets": ["Software Development"],
        "total_items": 40,
    },
    "part_7": {
        "title": "Production/Operation/Service",
        "checksheets": ["Production Operation Service"],
        "total_items": 36,
    },
    "part_8": {
        "title": "Supporting Processes",
        "checksheets": ["Supporting Processes"],
        "total_items": 34,
    },
    "part_9": {
        "title": "Safety Analysis",
        "checksheets": ["Safety Analysis"],
        "total_items": 29,
    },
    "part_10": {
        "title": "Guidelines",
        "checksheets": [],
        "total_items": 0,
    },
    "part_11": {
        "title": "Semiconductors",
        "checksheets": ["Semiconductor Application"],
        "total_items": 30,
    },
    "part_12": {
        "title": "Motorcycles",
        "checksheets": ["Motorcycle Adaptation"],
        "total_items": 30,
    },
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def esc(text):
    """Escape HTML text safely."""
    if text is None:
        return ""
    return html_mod.escape(str(text))

def score_class(score):
    """Return CSS class for score."""
    score = float(score) if score else 0
    if score >= 85:
        return "score-pass"
    elif score >= 60:
        return "score-warn"
    return "score-fail"

def severity_class(sev):
    """Return CSS class for severity."""
    s = str(sev or "").upper()
    if s == "CRITICAL":
        return "sev-critical"
    elif s == "MAJOR":
        return "sev-major"
    elif s == "WARNING":
        return "sev-warning"
    return "sev-info"

def badge_class(status):
    """Return CSS class for badge."""
    s = str(status or "").upper()
    if s in ("PASS", "COMPLIANT", "COMPLETE", "MET"):
        return "badge-pass"
    elif s in ("PARTIAL", "WARN", "CONDITIONALLY"):
        return "badge-warn"
    elif s in ("FAIL", "MISSING", "NOT_COMPLIANT", "PENDING"):
        return "badge-fail"
    return "badge-info"

def score_color(score):
    """Return hex color for score."""
    score = float(score) if score else 0
    if score >= 85:
        return "#059669"
    elif score >= 60:
        return "#f59e0b"
    elif score >= 30:
        return "#ef4444"
    return "#ef4444"

# ============================================================================
# SVG CHART GENERATORS
# ============================================================================

def _svg_bar_chart(layer_results: Dict[str, Any]) -> str:
    """Generate horizontal bar chart for layer performance."""
    width = 680
    padding = 16
    bar_height = 22
    spacing = 14
    label_width = 150
    bar_start = label_width + 8
    weight_col = 60
    score_col = 55
    bar_area = width - bar_start - weight_col - score_col - padding

    layers = [
        "node_coverage",
        "content_alignment",
        "semantic_matching",
        "concept_coverage",
        "reference_integrity",
        "method_audit",
        "traceability_chain",
    ]

    chart_height = len(layers) * (bar_height + spacing) + padding * 2 + 30
    svg = f'<svg width="100%" viewBox="0 0 {width} {chart_height}" xmlns="http://www.w3.org/2000/svg">'

    # Column header for weight
    svg += f'<text x="{bar_start + bar_area + score_col + 8}" y="{padding}" font-family="var(--font-body)" font-size="9" font-weight="700" fill="#9ca3af" text-anchor="start">WEIGHT</text>'

    y_pos = padding + 12
    max_score = 100

    for layer_id in layers:
        label = LAYER_LABELS.get(layer_id, layer_id)
        score = layer_results.get(layer_id, {}).get("score", 0)
        weight = LAYER_WEIGHTS.get(layer_id, 0)
        weight_display = f"{weight * 10:.1f}x"

        if score >= 85:
            color = "#059669"
        elif score >= 60:
            color = "#f59e0b"
        else:
            color = "#ef4444"

        bar_width = max(2, (score / max_score) * bar_area)

        # Layer name
        svg += f'<text x="{padding}" y="{y_pos + bar_height / 2 + 4}" font-family="var(--font-body)" font-size="11" font-weight="600" fill="#1a1a2e">{esc(label)}</text>'

        # Bar background
        svg += f'<rect x="{bar_start}" y="{y_pos}" width="{bar_area}" height="{bar_height}" fill="#e5e7eb" rx="3" />'

        # Bar fill
        svg += f'<rect x="{bar_start}" y="{y_pos}" width="{bar_width}" height="{bar_height}" fill="{color}" rx="3" opacity="0.9" />'

        # Score after bar
        svg += f'<text x="{bar_start + bar_area + 8}" y="{y_pos + bar_height / 2 + 4}" font-family="var(--font-mono)" font-size="11" font-weight="700" fill="#1a1a2e">{score:.1f}%</text>'

        # Weight indicator
        svg += f'<text x="{bar_start + bar_area + score_col + 12}" y="{y_pos + bar_height / 2 + 4}" font-family="var(--font-mono)" font-size="10" font-weight="600" fill="#6b7280">{weight_display}</text>'

        y_pos += bar_height + spacing

    # Axis ticks at bottom
    y_axis = y_pos
    for pct in [0, 20, 40, 60, 80, 100]:
        x = bar_start + (pct / 100) * bar_area
        svg += f'<line x1="{x}" y1="{y_axis}" x2="{x}" y2="{y_axis + 4}" stroke="#d1d5db" stroke-width="1" />'
        svg += f'<text x="{x}" y="{y_axis + 14}" font-family="var(--font-mono)" font-size="9" fill="#9ca3af" text-anchor="middle">{pct}%</text>'

    svg += '</svg>'
    return svg

def _svg_donut(severity_counts: Dict[str, int]) -> str:
    """Generate donut chart for severity distribution."""
    size = 150
    radius = 55
    stroke_width = 14

    critical = severity_counts.get("CRITICAL", 0)
    major = severity_counts.get("MAJOR", 0)
    warning = severity_counts.get("WARNING", 0)
    info = severity_counts.get("INFO", 0)

    total = critical + major + warning + info
    if total == 0:
        total = 1

    circumference = 2 * 3.14159 * (radius - stroke_width / 2)

    critical_pct = (critical / total) * 100
    major_pct = (major / total) * 100
    warning_pct = (warning / total) * 100
    info_pct = (info / total) * 100

    critical_len = (critical_pct / 100.0) * circumference
    major_len = (major_pct / 100.0) * circumference
    warning_len = (warning_pct / 100.0) * circumference

    svg = f'<svg width="100%" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" style="max-width: 200px; margin: 0 auto;">'

    # Background circle
    svg += f'<circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none" stroke="#e5e7eb" stroke-width="{stroke_width}" />'

    # Critical (red)
    if critical > 0:
        svg += f'<circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none" stroke="#dc2626" stroke-width="{stroke_width}" stroke-dasharray="{critical_len} {circumference - critical_len}" stroke-dashoffset="0" stroke-linecap="round" />'

    # Major (amber)
    if major > 0:
        offset = -critical_len if critical > 0 else 0
        svg += f'<circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none" stroke="#d97706" stroke-width="{stroke_width}" stroke-dasharray="{major_len} {circumference - major_len}" stroke-dashoffset="{offset}" stroke-linecap="round" />'

    # Warning (orange)
    if warning > 0:
        offset = -(critical_len + major_len) if (critical > 0 or major > 0) else 0
        svg += f'<circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none" stroke="#ca8a04" stroke-width="{stroke_width}" stroke-dasharray="{warning_len} {circumference - warning_len}" stroke-dashoffset="{offset}" stroke-linecap="round" />'

    # Info (blue) - fills the rest
    if info > 0:
        info_len = circumference - critical_len - major_len - warning_len
        offset = -(critical_len + major_len + warning_len)
        svg += f'<circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none" stroke="#2563eb" stroke-width="{stroke_width}" stroke-dasharray="{info_len} {circumference - info_len}" stroke-dashoffset="{offset}" stroke-linecap="round" />'

    # Center text
    svg += f'<text x="{size/2}" y="{size/2 + 8}" text-anchor="middle" font-family="var(--font-mono)" font-size="18" font-weight="700" fill="#1a1a2e">{total}</text>'
    svg += f'<text x="{size/2}" y="{size/2 + 25}" text-anchor="middle" font-family="var(--font-body)" font-size="10" fill="#6b7280">FINDINGS</text>'

    svg += '</svg>'
    return svg

def _svg_radar(layer_results: Dict[str, Any]) -> str:
    """Generate enhanced radar/spider chart for multi-layer scores."""
    layers = [
        "node_coverage",
        "content_alignment",
        "semantic_matching",
        "concept_coverage",
        "reference_integrity",
        "method_audit",
        "traceability_chain",
    ]

    size = 420
    center = size / 2
    max_radius = 130
    levels = 5

    svg = f'<svg width="100%" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" style="max-width: 400px; margin: 0 auto;">'

    # Define gradient for polygon
    svg += '''<defs>
    <linearGradient id="radarGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#059669;stop-opacity:0.4" />
      <stop offset="100%" style="stop-color:#0f766e;stop-opacity:0.2" />
    </linearGradient>
    <style>
      @keyframes radarPulse {
        from { opacity: 0.1; }
        to { opacity: 0.4; }
      }
      .radar-polygon { animation: radarPulse 1.2s ease-out forwards; }
    </style>
  </defs>'''

    # Draw concentric circles with labels
    for level in range(1, levels + 1):
        r = (level / levels) * max_radius
        svg += f'<circle cx="{center}" cy="{center}" r="{r}" fill="none" stroke="var(--c-border)" stroke-width="0.5" stroke-dasharray="2,2" />'
        # Add percentage label
        svg += f'<text x="{center + r + 5}" y="{center - 5}" font-size="9" fill="var(--c-text-muted)">{level * 20}%</text>'

    # Draw axes and plot points
    num_layers = len(layers)
    angle_slice = (2 * math.pi) / num_layers

    points = []
    scores = []
    for i, layer_id in enumerate(layers):
        angle = angle_slice * i - (math.pi / 2)
        score = layer_results.get(layer_id, {}).get("score", 0)
        radius = (score / 100.0) * max_radius

        x = center + radius * math.cos(angle)
        y = center + radius * math.sin(angle)
        points.append((x, y))
        scores.append(score)

        # Draw axis line
        ax = center + max_radius * math.cos(angle)
        ay = center + max_radius * math.sin(angle)
        svg += f'<line x1="{center}" y1="{center}" x2="{ax}" y2="{ay}" stroke="var(--c-border)" stroke-width="0.5" />'

        # Draw score point
        svg += f'<circle cx="{x}" cy="{y}" r="3" fill="#059669" stroke="white" stroke-width="1.5" />'

        # Draw score label at vertex
        label_x = center + (max_radius + 35) * math.cos(angle)
        label_y = center + (max_radius + 35) * math.sin(angle)
        svg += f'<text x="{label_x}" y="{label_y - 5}" text-anchor="middle" font-size="10" font-weight="600" fill="var(--c-text)">{score:.0f}%</text>'

        # Draw layer label
        label_x = center + (max_radius + 60) * math.cos(angle)
        label_y = center + (max_radius + 60) * math.sin(angle)
        label = LAYER_LABELS.get(layer_id, layer_id)
        # Wrap long labels
        label_parts = label.split()
        svg += f'<text x="{label_x}" y="{label_y}" text-anchor="middle" font-size="9" font-weight="500" fill="var(--c-text-secondary)">{esc(label_parts[0])}</text>'
        if len(label_parts) > 1:
            svg += f'<text x="{label_x}" y="{label_y + 11}" text-anchor="middle" font-size="9" font-weight="500" fill="var(--c-text-secondary)">{esc(" ".join(label_parts[1:]))}</text>'

    # Draw polygon with gradient
    if points:
        path = f"M {points[0][0]} {points[0][1]} "
        for p in points[1:]:
            path += f"L {p[0]} {p[1]} "
        path += "Z"
        svg += f'<path d="{path}" fill="url(#radarGradient)" stroke="#059669" stroke-width="2.5" class="radar-polygon" />'

    svg += '</svg>'
    return svg

def _html_heatmap(gaps: List[Dict[str, Any]]) -> str:
    """Generate HTML/CSS grid-based heatmap for gap distribution."""
    parts = {}
    for gap in gaps:
        part = gap.get("group", "unknown")
        if part not in parts:
            parts[part] = {"CRITICAL": 0, "MAJOR": 0, "WARNING": 0, "INFO": 0}
        for finding in gap.get("findings", []):
            severity = finding.get("severity", "INFO")
            if severity in parts[part]:
                parts[part][severity] += 1

    if not parts:
        return '<p style="color: var(--c-text-secondary);">No gaps to display.</p>'

    part_names = sorted(parts.keys())
    severities = ["CRITICAL", "MAJOR", "WARNING", "INFO"]
    colors = {"CRITICAL": "#dc2626", "MAJOR": "#d97706", "WARNING": "#ca8a04", "INFO": "#2563eb"}
    bg_colors = {
        "CRITICAL": "rgba(220, 38, 38, 0.1)",
        "MAJOR": "rgba(217, 119, 6, 0.1)",
        "WARNING": "rgba(202, 138, 4, 0.1)",
        "INFO": "rgba(37, 99, 235, 0.1)"
    }

    svg_width = 400 + len(severities) * 60
    svg_height = len(part_names) * 40 + 60

    svg = f'<svg width="100%" viewBox="0 0 {svg_width} {svg_height}" xmlns="http://www.w3.org/2000/svg" style="max-width: 100%;">'

    # Header row
    svg += f'<rect x="0" y="0" width="150" height="40" fill="var(--c-bg)" />'
    x_offset = 150
    for i, sev in enumerate(severities):
        svg += f'<text x="{x_offset + 30}" y="25" text-anchor="middle" font-size="11" font-weight="600" fill="var(--c-text)">{sev}</text>'
        x_offset += 60

    # Data rows
    y_offset = 40
    for part in part_names:
        # Part name
        svg += f'<text x="10" y="{y_offset + 20}" font-size="11" font-weight="600" fill="var(--c-text)">{esc(part)}</text>'

        x_offset = 150
        max_count = max([parts[part].get(s, 0) for s in severities])
        if max_count == 0:
            max_count = 1

        for sev in severities:
            count = parts[part].get(sev, 0)
            intensity = count / max_count if max_count > 0 else 0
            alpha = 0.2 + (intensity * 0.8)
            color = colors[sev]
            svg += f'<rect x="{x_offset + 5}" y="{y_offset + 5}" width="50" height="30" fill="{color}" opacity="{alpha}" stroke="var(--c-border)" stroke-width="0.5" rx="2" />'
            if count > 0:
                svg += f'<text x="{x_offset + 30}" y="{y_offset + 22}" text-anchor="middle" font-size="12" font-weight="700" fill="var(--c-text)">{count}</text>'
            x_offset += 60

        y_offset += 40

    svg += '</svg>'
    return svg

def _svg_waterfall(layer_results: Dict[str, Any]) -> str:
    """Generate SVG horizontal bar chart for layer scores with color-coded bars and gradient fills."""
    layers = [
        "node_coverage",
        "content_alignment",
        "semantic_matching",
        "concept_coverage",
        "reference_integrity",
        "method_audit",
        "traceability_chain",
    ]

    width = 700
    padding = 20
    bar_height = 28
    spacing = 14
    label_width = 155
    bar_start = label_width + 10
    score_width = 60
    bar_area = width - bar_start - score_width - padding

    chart_height = len(layers) * (bar_height + spacing) + padding * 2 + 30

    svg = f'<svg width="100%" viewBox="0 0 {width} {chart_height}" xmlns="http://www.w3.org/2000/svg" style="max-width: 100%;">'

    # Gradient definitions for each color
    svg += '<defs>'
    svg += '<linearGradient id="grad-green" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#059669;stop-opacity:1" /><stop offset="100%" style="stop-color:#34d399;stop-opacity:0.8" /></linearGradient>'
    svg += '<linearGradient id="grad-amber" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#f59e0b;stop-opacity:1" /><stop offset="100%" style="stop-color:#fbbf24;stop-opacity:0.8" /></linearGradient>'
    svg += '<linearGradient id="grad-red" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#ef4444;stop-opacity:1" /><stop offset="100%" style="stop-color:#f87171;stop-opacity:0.8" /></linearGradient>'
    svg += '</defs>'

    y_pos = padding + 8
    max_score = 100

    for idx, layer_id in enumerate(layers):
        label = LAYER_LABELS.get(layer_id, layer_id)
        score = layer_results.get(layer_id, {}).get("score", 0)

        if score >= 85:
            gradient = "url(#grad-green)"
            color = "#059669"
            status = "PASS"
        elif score >= 60:
            gradient = "url(#grad-amber)"
            color = "#f59e0b"
            status = "WARN"
        else:
            gradient = "url(#grad-red)"
            color = "#ef4444"
            status = "FAIL"

        bar_width = max(2, (score / max_score) * bar_area)

        # Layer label
        svg += f'<text x="{padding}" y="{y_pos + bar_height / 2 + 5}" font-family="var(--font-body)" font-size="11" font-weight="600" fill="#1a1a2e">{esc(label)}</text>'

        # Bar background track
        svg += f'<rect x="{bar_start}" y="{y_pos}" width="{bar_area}" height="{bar_height}" fill="#e5e7eb" rx="4" />'

        # Color-filled bar with gradient
        svg += f'<rect x="{bar_start}" y="{y_pos}" width="{bar_width}" height="{bar_height}" fill="{gradient}" rx="4">'
        svg += f'<animate attributeName="width" from="0" to="{bar_width}" dur="0.6s" begin="{idx * 0.08}s" fill="freeze" calcMode="spline" keySplines="0.16 1 0.3 1" /></rect>'

        # Score + status label
        svg += f'<text x="{bar_start + bar_area + 8}" y="{y_pos + bar_height / 2 + 5}" font-family="var(--font-mono)" font-size="12" font-weight="700" fill="{color}">{score:.1f}%</text>'

        y_pos += bar_height + spacing

    # Axis reference lines
    y_axis = y_pos
    for pct in [0, 25, 50, 75, 100]:
        x = bar_start + (pct / 100) * bar_area
        svg += f'<line x1="{x}" y1="{padding + 8}" x2="{x}" y2="{y_axis - spacing + bar_height}" stroke="#e5e7eb" stroke-width="0.5" stroke-dasharray="4 4" />'
        svg += f'<text x="{x}" y="{y_axis + 12}" font-family="var(--font-mono)" font-size="9" fill="#9ca3af" text-anchor="middle">{pct}%</text>'

    svg += '</svg>'
    return svg

# ============================================================================
# MAIN GENERATOR
# ============================================================================

def generate_compliance_html(report: dict, output_path: str):
    """Generate full HTML report matching reference design."""

    # Extract report data with safe defaults
    compliance_score = float(report.get("compliance_score", 0))
    grade = esc(report.get("grade", ""))
    engine = esc(report.get("engine", "Lion of Functional Safety Engine™ — Standard-Agnostic Compliance Checker v2.1"))
    check_date = esc(report.get("check_date", datetime.now().isoformat().split("T")[0]))
    standard_source = esc(report.get("standard_source", "26262"))
    target_risk = esc(report.get("target_risk_level", "D"))

    layer_results = report.get("layer_results", {})
    gap_analysis = report.get("gap_analysis", {})
    work_products = report.get("work_product_register", [])
    traceability = report.get("traceability_matrix", {})
    assessment_decision = report.get("assessment_decision", {})
    confirmation_review = report.get("confirmation_review", {})
    verification_review = report.get("verification_review", {})
    summary = report.get("summary", {})

    total_findings = summary.get("total_findings", 0)
    risk_score = summary.get("risk_score", 0)

    # Severity counts
    gap_severity = gap_analysis.get("severity_counts", {"CRITICAL": 0, "MAJOR": 0, "WARNING": 0, "INFO": 0})

    # Generate charts
    bar_chart_svg = _svg_bar_chart(layer_results) if layer_results else ""
    donut_chart_svg = _svg_donut(gap_severity) if gap_severity else ""
    radar_chart_svg = _svg_radar(layer_results) if layer_results else ""

    # Build HTML
    html_parts = []

    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="en" data-theme="light">')
    html_parts.append('<head>')
    html_parts.append('  <meta charset="UTF-8">')
    html_parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append(f'  <title>Functional Safety Compliance Assessment Report — CIQ-FSA-{check_date.replace("-", "")}</title>')

    # CSS
    html_parts.append('  <style>')
    html_parts.append(CSS_CONTENT)
    html_parts.append('  </style>')

    html_parts.append('</head>')
    html_parts.append('<body>')

    # Sidebar
    html_parts.append('  <aside class="sidebar">')
    html_parts.append('    <div class="sidebar-logo">')
    html_parts.append('      <div class="sidebar-logo-icon">FS</div>')
    html_parts.append('      <div class="sidebar-logo-text">Functional Safety Compliance Report</div>')
    html_parts.append('    </div>')
    html_parts.append('    <div class="sidebar-search">')
    html_parts.append('      <span style="font-size: 13px; color: var(--c-text-secondary);">🔍</span>')
    html_parts.append('      <input type="text" id="globalSearch" placeholder="Search..." aria-label="Global search">')
    html_parts.append('    </div>')
    nav_items = [
        ("cover", "Cover Page"),
        ("executive-summary", "Executive Summary"),
        ("methodology", "Methodology"),
        ("work-products", "Work Products"),
        ("dashboard", "Dashboard"),
        ("compliance-matrix", "Compliance Matrix"),
        ("traceability", "Traceability"),
        ("gap-analysis", "Gap Analysis"),
        ("method-audit", "Method Audit"),
        ("risk-assessment", "Risk Assessment"),
        ("corrective-actions", "Corrective Actions"),
        ("confirmation-review", "Confirmation Review"),
        ("verification-review", "Verification Review"),
        ("assessment-decision", "Assessment Decision"),
        ("checksheet-coverage", "Checksheet Coverage"),
        ("appendix", "Appendix"),
    ]
    html_parts.append('    <nav class="sidebar-nav" id="sidebarNav">')
    for idx, (nav_id, nav_label) in enumerate(nav_items):
        active = ' active' if idx == 0 else ''
        html_parts.append(f'      <div class="sidebar-nav-item{active}" data-nav-section="{nav_id}"><span class="nav-num">{idx + 1}</span> {nav_label}</div>')
    html_parts.append('    </nav>')
    html_parts.append('    <div class="sidebar-actions">')
    html_parts.append('      <button class="sidebar-button" id="toggleTheme" title="Toggle dark mode (t)">🌙 Dark Mode</button>')
    html_parts.append('      <button class="sidebar-button" onclick="window.print()" title="Print report">🖨️ Print</button>')
    html_parts.append('    </div>')
    html_parts.append('  </aside>')

    # Main report
    html_parts.append('  <main class="report">')
    html_parts.append('    <div class="report-container">')

    # ─── SECTION 00: COVER PAGE ───
    html_parts.append(_section_cover(engine, check_date))

    # ─── SECTION 01: EXECUTIVE SUMMARY ───
    html_parts.append(_section_executive_summary(compliance_score, grade, total_findings, risk_score, target_risk))

    # ─── SECTION 02: METHODOLOGY ───
    html_parts.append(_section_methodology(layer_results))

    # ─── SECTION 03: WORK PRODUCTS ───
    html_parts.append(_section_work_products(work_products))

    # ─── SECTION 04: DASHBOARD ───
    html_parts.append(_section_dashboard(compliance_score, gap_severity, bar_chart_svg, donut_chart_svg, radar_chart_svg))

    # ─── SECTION 05: COMPLIANCE MATRIX ───
    html_parts.append(_section_compliance_matrix(layer_results))

    # ─── SECTION 06: TRACEABILITY ───
    html_parts.append(_section_traceability(traceability))

    # ─── SECTION 07: GAP ANALYSIS ───
    html_parts.append(_section_gap_analysis(gap_analysis))

    # ─── SECTION 08: METHOD AUDIT ───
    html_parts.append(_section_method_audit(layer_results))

    # ─── SECTION 09: RISK ASSESSMENT ───
    html_parts.append(_section_risk_assessment(gap_analysis, layer_results, compliance_score))

    # ─── SECTION 10: CORRECTIVE ACTIONS ───
    html_parts.append(_section_corrective_actions(gap_analysis))

    # ─── SECTION 11: CONFIRMATION REVIEW ───
    html_parts.append(_section_confirmation_review(confirmation_review))

    # ─── SECTION 12: VERIFICATION REVIEW ───
    html_parts.append(_section_verification_review(verification_review))

    # ─── SECTION 13: ASSESSMENT DECISION ───
    html_parts.append(_section_assessment_decision(assessment_decision, compliance_score))

    # ─── SECTION 14: CHECKSHEET COVERAGE ───
    html_parts.append(_section_checksheet_coverage(gap_analysis))

    # ─── SECTION 15: APPENDIX ───
    html_parts.append(_section_appendix(standard_source, engine, check_date))

    html_parts.append('    </div>')
    html_parts.append('    <div class="page-footer">')
    html_parts.append(f'      Lion of Functional Safety Engine™ | Report v1.3 | {check_date}')
    html_parts.append('    </div>')
    html_parts.append('  </main>')

    # Scroll-to-top button
    html_parts.append('  <button class="scroll-to-top" id="scrollToTop">↑</button>')

    # JavaScript
    html_parts.append('  <script>')
    html_parts.append(JS_CONTENT)
    html_parts.append('  </script>')

    html_parts.append('</body>')
    html_parts.append('</html>')

    # Write file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))

# ============================================================================
# SECTION BUILDERS
# ============================================================================

def _section_cover(engine, check_date):
    """Cover page."""
    return f'''<div class="section" data-section="cover">
  <div style="text-align: center; padding: 4rem 0;">
    <h1 style="font-size: 3.5rem; margin-bottom: 1rem; letter-spacing: 0.05em;">FUNCTIONAL SAFETY</h1>
    <h2 style="font-size: 2.5rem; margin-bottom: 3rem; letter-spacing: 0.03em; border: none; padding: 0;">COMPLIANCE REPORT</h2>
    <p style="font-size: 16px; color: var(--c-text-secondary); margin-bottom: 2rem;">Executive Summary & Score Card</p>
  </div>

  <div class="metadata" style="margin: 3rem 0;">
    <div class="metadata-item">
      <div class="metadata-label">Engine</div>
      <div class="metadata-value">{engine}</div>
    </div>
    <div class="metadata-item">
      <div class="metadata-label">Document ID</div>
      <div class="metadata-value">CIQ-FSA-{check_date.replace("-", "")}</div>
    </div>
    <div class="metadata-item">
      <div class="metadata-label">Check Date</div>
      <div class="metadata-value">{check_date}</div>
    </div>
  </div>

  <p style="text-align: center; margin-top: 3rem; color: var(--c-text-muted); font-size: 13px;">
    Lion of Functional Safety Engine™ | Report v1.3 | {check_date}
  </p>
</div>'''

def _section_executive_summary(score, grade, findings, risk, target_asil):
    """Executive summary with metrics."""
    score_cls = score_class(score)
    return f'''<div class="section" data-section="executive-summary">
  <div class="section-header">
    <span class="section-num">01</span>
    <span class="section-title">Executive Summary</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <div style="display: flex; align-items: flex-start; gap: 2rem; margin-bottom: 2rem;">
      <div style="flex: 0 0 auto;">
        <div style="font-size: 5rem; font-family: var(--font-display); font-weight: 700; line-height: 1; color: var(--c-{('red' if score < 60 else 'amber' if score < 85 else 'green')});">{score:.1f}%</div>
        <div style="font-size: 12px; color: var(--c-text-secondary); margin-top: 0.5rem; text-transform: uppercase; font-weight: 700;">{grade or 'Assessment'}</div>
      </div>
      <div style="flex: 1;">
        <p>Compliance assessment completed for functional safety standard alignment. Score reflects adherence to ISO 26262 requirements across all evaluated dimensions.</p>
      </div>
    </div>

    <h3>Key Metrics</h3>
    <div class="metrics-row">
      <div class="metric-card">
        <div class="metric-value {score_cls}">{score:.1f}%</div>
        <div class="metric-label">Compliance Score</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{findings}</div>
        <div class="metric-label">Total Findings</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{int(risk):,}</div>
        <div class="metric-label">Risk Score</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{target_asil}</div>
        <div class="metric-label">Target ASIL</div>
      </div>
    </div>
  </div>
</div>'''

def _section_methodology(layer_results):
    """Methodology section describing assessment approach."""
    layers_html = ""
    for layer_id in ["node_coverage", "content_alignment", "semantic_matching", "concept_coverage", "reference_integrity", "method_audit", "traceability_chain"]:
        if layer_id in layer_results:
            layer = layer_results[layer_id]
            label = LAYER_LABELS.get(layer_id, layer_id)
            technique = LAYER_TECHNIQUES.get(layer_id, "")
            score = layer.get("score", 0)
            color = score_color(score)

            layers_html += f'''    <div class="metadata-item">
      <div class="metadata-label">{label}</div>
      <div class="metadata-value">{technique} — {score:.1f}%</div>
    </div>
'''

    return f'''<div class="section" data-section="methodology">
  <div class="section-header">
    <span class="section-num">02</span>
    <span class="section-title">Methodology</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <p>Assessment employs a multi-layer analysis framework combining structural coverage, content alignment, semantic matching, concept validation, reference integrity, method auditing, and traceability chain analysis.</p>

    <h3>Assessment Layers</h3>
    <div class="metadata">
{layers_html}    </div>
  </div>
</div>'''

def _section_work_products(work_products):
    """Work products section."""
    rows_html = ""
    for wp in work_products:
        name = esc(wp.get("name", ""))
        status = esc(wp.get("status", ""))
        verdict = esc(wp.get("verdict", ""))
        score = float(wp.get("score", 0))
        method = esc(wp.get("method", ""))

        badge_cls = badge_class(status)

        rows_html += f'''      <tr data-status="{status.lower()}">
        <td>{name}</td>
        <td><span class="badge {badge_cls}">{status}</span></td>
        <td>{verdict}</td>
        <td>{score:.1f}%</td>
        <td>{method}</td>
      </tr>
'''

    return f'''<div class="section" data-section="work-products">
  <div class="section-header">
    <span class="section-num">03</span>
    <span class="section-title">Work Products</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <p>Inventory of assessed work products with status, verdict, and compliance score.</p>

    <div class="filter-buttons">
      <button class="filter-btn active" data-filter="all">All</button>
      <button class="filter-btn" data-filter="pass">Pass</button>
      <button class="filter-btn" data-filter="fail">Fail</button>
    </div>

    <table>
      <thead>
        <tr>
          <th class="sortable">Work Product</th>
          <th class="sortable">Status</th>
          <th class="sortable">Verdict</th>
          <th class="sortable">Score</th>
          <th class="sortable">Method</th>
        </tr>
      </thead>
      <tbody>
{rows_html}      </tbody>
    </table>
  </div>
</div>'''

def _section_dashboard(score, severity_counts, bar_svg, donut_svg, radar_svg):
    """Dashboard with charts — reference image layout."""
    score_cls = "score-pass" if score >= 85 else "score-warn" if score >= 60 else "score-fail"
    verdict = "COMPLIANT" if score >= 85 else "CONDITIONALLY COMPLIANT" if score >= 60 else "NOT COMPLIANT"
    grade_letter = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
    verdict_cls = "badge-pass" if score >= 85 else "badge-warn" if score >= 60 else "badge-fail"

    sev_boxes = ""
    for sev_name, sev_color in [("CRITICAL", "var(--c-red)"), ("MAJOR", "var(--c-amber)"), ("WARNING", "#ca8a04"), ("INFO", "var(--c-blue)")]:
        count = severity_counts.get(sev_name, 0)
        sev_boxes += f'''        <div style="background: var(--c-bg); border-radius: var(--radius-sm); padding: 0.75rem 1rem; text-align: center; border-top: 3px solid {sev_color};">
          <div style="font-family: var(--font-mono); font-size: 24px; font-weight: 700; color: {sev_color};">{count}</div>
          <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--c-text-muted); letter-spacing: 0.05em;">{sev_name}</div>
        </div>
'''

    return f'''<div class="section" data-section="dashboard">
  <div class="section-header">
    <span class="section-num">04</span>
    <span class="section-title">Dashboard</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <!-- Top row: Score left, Layer bars right -->
    <div style="display: grid; grid-template-columns: 280px 1fr; gap: 2rem; align-items: start; margin-bottom: 2rem;">
      <div style="text-align: center; padding: 1.5rem; background: var(--c-bg); border-radius: var(--radius-sm);">
        <div class="metric-value {score_cls}" style="font-size: 64px;">{score:.1f}%</div>
        <div style="font-size: 14px; font-weight: 600; color: var(--c-text-secondary); margin-top: 0.5rem;">{grade_letter} — Non-Compliant</div>
        <div style="margin-top: 0.75rem;"><span class="badge {verdict_cls}" style="font-size: 11px; padding: 0.4rem 0.8rem;">{verdict}</span></div>
      </div>
      <div class="chart-panel" style="margin: 0;">
        <div class="chart-panel-title">Layer Performance</div>
        <div class="chart-container" style="padding: 0.5rem 0;">
{bar_svg}        </div>
      </div>
    </div>

    <!-- Severity boxes row -->
    <h3>Severity</h3>
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 1rem 0 2rem 0;">
{sev_boxes}    </div>

    <!-- Bottom row: Donut left, Radar right -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;">
      <div class="chart-panel">
        <div class="chart-panel-title">Severity Distribution</div>
        <div class="chart-container">
{donut_svg}        </div>
      </div>
      <div class="chart-panel">
        <div class="chart-panel-title">Spider Chart</div>
        <div class="chart-container">
{radar_svg}        </div>
      </div>
    </div>
  </div>
</div>'''

def _section_compliance_matrix(layer_results):
    """Compliance matrix."""
    rows_html = ""
    for layer_id in ["node_coverage", "content_alignment", "semantic_matching", "concept_coverage", "reference_integrity", "method_audit", "traceability_chain"]:
        if layer_id in layer_results:
            layer = layer_results[layer_id]
            label = LAYER_LABELS.get(layer_id, layer_id)
            score = layer.get("score", 0)
            findings = len(layer.get("findings", []))

            badge_cls = "badge-pass" if score >= 85 else "badge-warn" if score >= 60 else "badge-fail"

            rows_html += f'''      <tr>
        <td>{label}</td>
        <td>{score:.1f}%</td>
        <td><span class="badge {badge_cls}">{"Pass" if score >= 85 else "Warn" if score >= 60 else "Fail"}</span></td>
        <td>{findings}</td>
      </tr>
'''

    return f'''<div class="section" data-section="compliance-matrix">
  <div class="section-header">
    <span class="section-num">05</span>
    <span class="section-title">Compliance Matrix</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <p>Assessment matrix showing layer-by-layer compliance status.</p>

    <div class="filter-buttons">
      <button class="filter-btn active" data-filter="all">All</button>
      <button class="filter-btn" data-filter="pass">Pass</button>
      <button class="filter-btn" data-filter="fail">Fail</button>
    </div>

    <table>
      <thead>
        <tr>
          <th class="sortable">Layer</th>
          <th class="sortable">Score</th>
          <th class="sortable">Status</th>
          <th class="sortable">Findings</th>
        </tr>
      </thead>
      <tbody>
{rows_html}      </tbody>
    </table>
  </div>
</div>'''

def _section_traceability(traceability):
    """Traceability section with visual fault-tree style layout."""
    coverage = traceability.get("coverage_summary", {})
    traced_requirements = coverage.get("traced_requirements", 0)
    total_requirements = coverage.get("total_requirements", 1)
    trace_coverage_pct = coverage.get("trace_coverage_pct", 0)
    orphan_requirements = coverage.get("orphan_requirements_count", 0)
    orphan_artifacts = coverage.get("orphan_artifacts_count", 0)
    total_chains = coverage.get("total_chains", 0)

    chains = traceability.get("chains", [])

    # Group chains by artifact
    artifacts_map = {}
    for chain in chains:
        artifact_name = chain.get("artifact_name", "Unknown")
        artifact_id = chain.get("artifact_id", "")
        if artifact_name not in artifacts_map:
            artifacts_map[artifact_name] = {"id": artifact_id, "requirements": []}
        artifacts_map[artifact_name]["requirements"].append(chain)

    # Build visual tree nodes
    tree_nodes = ""
    for artifact_name in sorted(artifacts_map.keys()):
        artifact_data = artifacts_map[artifact_name]
        artifact_id = esc(artifact_data["id"])
        reqs = artifact_data["requirements"]
        verified_count = sum(1 for r in reqs if r.get("has_verification"))
        total_count = len(reqs)
        pct = (verified_count / total_count * 100) if total_count > 0 else 0
        health_color = "var(--c-green)" if pct == 100 else "var(--c-amber)" if pct > 0 else "var(--c-red)"

        # Requirement child nodes
        req_nodes = ""
        for req in reqs:
            req_id = esc(req.get("requirement_id", ""))
            has_v = req.get("has_verification", False)
            v_methods = req.get("verification_methods", [])
            v_icon = "&#10003;" if has_v else "&#10007;"
            v_color = "var(--c-green)" if has_v else "var(--c-red)"
            v_bg = "var(--c-green-bg)" if has_v else "var(--c-red-bg)"
            v_border = "var(--c-green-light)" if has_v else "var(--c-red-light)"

            # Methods pills
            methods_html = ""
            for m in v_methods[:3]:
                methods_html += f'<span class="tt-method">{esc(m[:30])}</span>'
            if len(v_methods) > 3:
                methods_html += f'<span class="tt-method">+{len(v_methods)-3} more</span>'
            if not v_methods and not has_v:
                methods_html = '<span class="tt-method" style="background: var(--c-red-bg); color: var(--c-red);">No verification method</span>'

            req_nodes += f'''          <div class="tt-req">
            <div class="tt-connector-h"></div>
            <div class="tt-req-card" style="border-left: 3px solid {v_color};">
              <div class="tt-req-header">
                <span class="tt-req-icon" style="background: {v_bg}; color: {v_color}; border: 1px solid {v_border};">{v_icon}</span>
                <span class="tt-req-id">§ {req_id}</span>
                <span class="tt-req-status" style="color: {v_color};">{"Verified" if has_v else "Unverified"}</span>
              </div>
              <div class="tt-req-methods">{methods_html}</div>
            </div>
          </div>
'''

        tree_nodes += f'''    <div class="tt-artifact" data-tt-id="{artifact_id}">
      <div class="tt-artifact-header" onclick="toggleTraceArtifact(this)">
        <div class="tt-artifact-icon">{artifact_id.replace("WP-","")}</div>
        <div class="tt-artifact-info">
          <div class="tt-artifact-name">{esc(artifact_name)}</div>
          <div class="tt-artifact-meta">{artifact_id} &middot; {total_count} req(s) &middot; <span style="color: {health_color};">{verified_count}/{total_count} verified</span></div>
        </div>
        <div class="tt-artifact-bar">
          <div class="tt-artifact-bar-fill" style="width: {pct:.0f}%; background: {health_color};"></div>
        </div>
        <span class="tt-expand-arrow">&#9660;</span>
      </div>
      <div class="tt-artifact-children">
        <div class="tt-connector-v"></div>
        <div class="tt-req-list">
{req_nodes}        </div>
      </div>
    </div>
'''

    # Coverage gauge SVG
    gauge_pct = trace_coverage_pct
    gauge_color = "#059669" if gauge_pct >= 80 else "#f59e0b" if gauge_pct >= 40 else "#ef4444"

    return f'''<div class="section" data-section="traceability">
  <div class="section-header">
    <span class="section-num">06</span>
    <span class="section-title">Traceability</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <h3>Coverage Metrics</h3>
    <div style="display: grid; grid-template-columns: 160px 1fr; gap: 2rem; align-items: start; margin: 1rem 0 2rem 0;">
      <div style="text-align: center; background: var(--c-bg); border-radius: var(--radius-sm); padding: 1.25rem;">
        <svg width="100" height="100" viewBox="0 0 100 100" style="display: block; margin: 0 auto;">
          <circle cx="50" cy="50" r="42" fill="none" stroke="#e5e7eb" stroke-width="8" />
          <circle cx="50" cy="50" r="42" fill="none" stroke="{gauge_color}" stroke-width="8" stroke-dasharray="{gauge_pct * 2.639} {263.9 - gauge_pct * 2.639}" stroke-dashoffset="66" stroke-linecap="round" />
          <text x="50" y="48" text-anchor="middle" font-family="var(--font-mono)" font-size="18" font-weight="700" fill="#1a1a2e">{gauge_pct:.0f}%</text>
          <text x="50" y="62" text-anchor="middle" font-family="var(--font-body)" font-size="8" fill="#9ca3af">COVERAGE</text>
        </svg>
      </div>
      <div class="metadata" style="margin: 0;">
        <div class="metadata-item">
          <div class="metadata-label">Traced / Total</div>
          <div class="metadata-value">{traced_requirements} / {total_requirements}</div>
        </div>
        <div class="metadata-item">
          <div class="metadata-label">Total Chains</div>
          <div class="metadata-value">{total_chains}</div>
        </div>
        <div class="metadata-item">
          <div class="metadata-label">Orphan Requirements</div>
          <div class="metadata-value" style="color: {"var(--c-red)" if orphan_requirements > 0 else "var(--c-green)"};">{orphan_requirements}</div>
        </div>
        <div class="metadata-item">
          <div class="metadata-label">Orphan Artifacts</div>
          <div class="metadata-value" style="color: {"var(--c-red)" if orphan_artifacts > 0 else "var(--c-green)"};">{orphan_artifacts}</div>
        </div>
      </div>
    </div>

    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
      <h3 style="margin: 0;">Traceability Tree</h3>
      <div>
        <button class="filter-btn" onclick="expandAllTrace()" style="font-size: 10px;">Expand All</button>
        <button class="filter-btn" onclick="collapseAllTrace()" style="font-size: 10px;">Collapse All</button>
      </div>
    </div>

    <div class="tt-root">
      <div class="tt-root-node">
        <div class="tt-root-label">ISO 26262 Compliance</div>
        <div class="tt-root-meta">{len(artifacts_map)} artifacts &middot; {total_chains} chains</div>
      </div>
      <div class="tt-trunk"></div>
      <div class="tt-branches">
{tree_nodes}      </div>
    </div>
  </div>
</div>'''

def _section_gap_analysis(gap_analysis):
    """Gap analysis section."""
    gaps = gap_analysis.get("gaps", [])
    severity_counts = gap_analysis.get("severity_counts", {"CRITICAL": 0, "MAJOR": 0, "WARNING": 0, "INFO": 0})

    gaps_html = ""
    for gap in gaps[:10]:
        clause = esc(gap.get("key", ""))
        findings = gap.get("findings", [])
        # Get title from first finding
        title = esc(findings[0].get("title", "") if findings else "")
        # Get worst severity from findings
        severity_order = {"CRITICAL": 0, "MAJOR": 1, "WARNING": 2, "INFO": 3}
        worst_sev = "INFO"
        for f in findings:
            f_sev = f.get("severity", "INFO")
            if severity_order.get(f_sev, 3) < severity_order.get(worst_sev, 3):
                worst_sev = f_sev
        sev_cls = severity_class(worst_sev)
        priority = esc(gap.get("priority", ""))

        gaps_html += f'''      <tr>
        <td style="font-family: var(--font-mono);">{clause}</td>
        <td>{title}</td>
        <td><span class="badge {sev_cls}">{worst_sev}</span></td>
        <td>{len(findings)}</td>
      </tr>
'''

    sev_boxes = ""
    for sev_name in ["CRITICAL", "MAJOR", "WARNING", "INFO"]:
        count = severity_counts.get(sev_name, 0)
        sev_cls = severity_class(sev_name)
        sev_boxes += f'''    <div class="sev-box {sev_cls}">
      <div class="sev-count">{count}</div>
      <div class="sev-name">{sev_name}</div>
    </div>
'''

    heatmap_html = _html_heatmap(gaps)

    return f'''<div class="section" data-section="gap-analysis">
  <div class="section-header">
    <span class="section-num">07</span>
    <span class="section-title">Gap Analysis</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <h3>Severity Summary</h3>
    <div class="severity-grid">
{sev_boxes}    </div>

    <table style="margin-top: 2rem;">
      <thead>
        <tr>
          <th class="sortable">Clause</th>
          <th class="sortable">Title</th>
          <th class="sortable">Severity</th>
          <th class="sortable">Findings</th>
        </tr>
      </thead>
      <tbody>
{gaps_html}      </tbody>
    </table>

    <h3 style="margin-top: 2rem;">Gap Distribution Heatmap</h3>
    <div style="text-align: center; overflow-x: auto;">
{heatmap_html}    </div>
  </div>
</div>'''

def _section_method_audit(layer_results):
    """Method audit section."""
    audit_html = ""
    for layer_id in ["node_coverage", "content_alignment", "semantic_matching", "concept_coverage", "reference_integrity", "method_audit", "traceability_chain"]:
        if layer_id in layer_results:
            layer = layer_results[layer_id]
            label = LAYER_LABELS.get(layer_id, layer_id)
            algorithm = LAYER_TECHNIQUES.get(layer_id, "")
            findings = len(layer.get("findings", []))

            audit_html += f'''      <tr>
        <td>{label}</td>
        <td>{algorithm}</td>
        <td>{findings}</td>
      </tr>
'''

    return f'''<div class="section" data-section="method-audit">
  <div class="section-header">
    <span class="section-num">08</span>
    <span class="section-title">Method Audit</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <p>Audit of assessment methods and algorithms employed per layer.</p>

    <table>
      <thead>
        <tr>
          <th class="sortable">Layer</th>
          <th class="sortable">Technique</th>
          <th class="sortable">Issues Found</th>
        </tr>
      </thead>
      <tbody>
{audit_html}      </tbody>
    </table>
  </div>
</div>'''

def _section_risk_assessment(gap_analysis, layer_results, compliance_score):
    """Risk assessment section."""
    recommendations = gap_analysis.get("recommendations", [])

    # Calculate normalized risk score as inverse of compliance
    risk_pct = max(0, min(100, 100 - compliance_score))

    rec_html = ""
    for rec in recommendations[:5]:
        rec_html += f'    <li style="margin: 0.5rem 0; color: var(--c-text-secondary);">{esc(rec)}</li>\n'

    waterfall_svg = _svg_waterfall(layer_results) if layer_results else ""

    return f'''<div class="section" data-section="risk-assessment">
  <div class="section-header">
    <span class="section-num">09</span>
    <span class="section-title">Risk Assessment</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <div class="metadata">
      <div class="metadata-item">
        <div class="metadata-label">Risk Score</div>
        <div class="metadata-value">{risk_pct:.1f}%</div>
      </div>
    </div>

    <h3>Top Recommendations</h3>
    <ul style="padding-left: 1.5rem;">
{rec_html}    </ul>

    <h3 style="margin-top: 2rem;">Layer Score Waterfall</h3>
    <div style="text-align: center; overflow-x: auto;">
{waterfall_svg}    </div>
  </div>
</div>'''

def _section_corrective_actions(gap_analysis):
    """Corrective actions section with clickable cards and detail modals."""
    gaps = gap_analysis.get("gaps", [])
    recommendations = gap_analysis.get("recommendations", [])

    # Build a recommendation lookup by clause key
    rec_lookup = {}
    for rec in recommendations:
        # Format: "[HIGH] 6.3.1: Create artifact..."
        if ": " in rec:
            parts = rec.split(": ", 1)
            clause_part = parts[0].strip()
            # Extract clause from "[HIGH] 6.3.1"
            if "] " in clause_part:
                clause_key = clause_part.split("] ", 1)[1].strip()
            else:
                clause_key = clause_part
            rec_lookup[clause_key] = parts[1].strip()

    actions_html = ""
    modals_html = ""
    for i, gap in enumerate(gaps[:10], 1):
        clause = gap.get("key", "")
        findings = gap.get("findings", [])
        priority = gap.get("priority", "MEDIUM")
        risk_weighted = gap.get("risk_weighted", 0)
        count = gap.get("count", 0)

        # Get title from first finding
        title = findings[0].get("title", clause) if findings else clause

        # Severity breakdown for this gap
        sev_counts = {"CRITICAL": 0, "MAJOR": 0, "WARNING": 0, "INFO": 0}
        affected_parts = set()
        for f in findings:
            sev = f.get("severity", "INFO")
            if sev in sev_counts:
                sev_counts[sev] += 1
            grp = f.get("group", "")
            if grp:
                affected_parts.add(grp.replace("_", " ").title())

        # Priority color
        if priority == "HIGH":
            pri_color = "var(--c-red)"
            pri_border = "var(--c-red)"
            pri_badge = "badge-fail"
        elif priority == "MEDIUM":
            pri_color = "var(--c-amber)"
            pri_border = "var(--c-amber)"
            pri_badge = "badge-warn"
        else:
            pri_color = "var(--c-blue)"
            pri_border = "var(--c-blue)"
            pri_badge = "badge-info"

        # Severity mini-indicators for the card
        sev_dots = ""
        for sev_name, sev_color in [("CRITICAL", "var(--c-red)"), ("MAJOR", "var(--c-amber)"), ("WARNING", "#ca8a04")]:
            sc = sev_counts.get(sev_name, 0)
            if sc > 0:
                sev_dots += f'<span style="font-size: 10px; font-weight: 700; color: {sev_color}; margin-right: 0.5rem;">{sc} {sev_name[:4]}</span>'

        modal_id = f"action-{i}"
        recommendation = rec_lookup.get(clause, "Review and address the identified findings for this clause.")

        actions_html += f'''    <div class="action-card" onclick="openActionModal('{modal_id}')" style="background: var(--c-bg); border: 1px solid var(--c-border); border-left: 4px solid {pri_border}; border-radius: var(--radius-sm); padding: 1rem 1.25rem; margin-bottom: 0.75rem; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 1rem;" onmouseover="this.style.boxShadow='var(--shadow-md)'; this.style.transform='translateX(4px)'" onmouseout="this.style.boxShadow='none'; this.style.transform='translateX(0)'">
      <div style="flex-shrink: 0; width: 32px; height: 32px; background: var(--c-surface); border: 2px solid {pri_border}; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-family: var(--font-mono); font-size: 13px; font-weight: 700; color: {pri_color};">{i}</div>
      <div style="flex: 1; min-width: 0;">
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
          <span style="font-size: 13px; font-weight: 700; color: var(--c-navy);">§ {esc(clause)}</span>
          <span style="font-size: 11px; color: var(--c-text-secondary);">— {esc(title[:50])}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
          <span class="badge {pri_badge}" style="font-size: 9px; padding: 2px 6px;">{priority}</span>
          {sev_dots}
          <span style="font-size: 10px; color: var(--c-text-muted);">{len(findings)} finding(s)</span>
        </div>
      </div>
      <div style="flex-shrink: 0; color: var(--c-text-muted); font-size: 16px;">&#9656;</div>
    </div>
'''

        # --- Build modal for this action ---
        # Severity bars
        finding_total = sum(sev_counts.values())
        sev_bars = ""
        for sev_name, sev_count, sev_color in [("Critical", sev_counts["CRITICAL"], "var(--c-red)"), ("Major", sev_counts["MAJOR"], "var(--c-amber)"), ("Warning", sev_counts["WARNING"], "#ca8a04"), ("Info", sev_counts["INFO"], "var(--c-blue)")]:
            sev_bars += f'''          <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.2rem;">
            <span style="font-size: 10px; font-weight: 700; color: var(--c-text-muted); width: 50px; text-transform: uppercase;">{sev_name}</span>
            <div style="flex: 1; height: 6px; background: var(--c-border); border-radius: 3px; overflow: hidden;">
              <div style="width: {min(100, (sev_count / max(1, finding_total)) * 100):.0f}%; height: 100%; background: {sev_color}; border-radius: 3px;"></div>
            </div>
            <span style="font-family: var(--font-mono); font-size: 11px; font-weight: 700; min-width: 20px; text-align: right;">{sev_count}</span>
          </div>
'''

        # Affected parts chips
        parts_chips = ""
        for part in sorted(affected_parts):
            parts_chips += f'<span style="display: inline-block; background: var(--c-blue-bg); color: var(--c-blue); font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 10px; margin: 2px;">{esc(part)}</span>'
        if not parts_chips:
            parts_chips = '<span style="font-size: 11px; color: var(--c-text-muted);">—</span>'

        # Findings table
        findings_rows = ""
        for fi, f in enumerate(findings[:15]):
            f_sev = f.get("severity", "INFO")
            f_cls = severity_class(f_sev)
            f_group = esc(f.get("group", "").replace("_", " ").title())
            f_type = esc(f.get("type", ""))
            f_msg = esc(f.get("message", "")[:120]) + ("..." if len(f.get("message", "")) > 120 else "")
            findings_rows += f'''            <tr>
              <td><span class="badge {f_cls}" style="font-size: 9px;">{f_sev}</span></td>
              <td style="font-size: 11px;">{f_group}</td>
              <td style="font-size: 10px; font-family: var(--font-mono);">{f_type}</td>
              <td style="font-size: 10px; color: var(--c-text-secondary);" title="{esc(f.get('message', ''))}">{f_msg}</td>
            </tr>
'''
        remaining = len(findings) - 15
        remaining_note = f'<div style="font-size: 10px; color: var(--c-text-muted); margin-top: 0.5rem; font-style: italic;">...and {remaining} more finding(s)</div>' if remaining > 0 else ""

        modals_html += f'''<div id="modal-{modal_id}" class="checksheet-modal" style="display: none;">
  <div class="checksheet-modal-overlay" onclick="closeActionModal('{modal_id}')"></div>
  <div class="checksheet-modal-content" style="max-width: 780px;">
    <div class="checksheet-modal-header">
      <div>
        <h2 style="font-size: 18px; margin: 0;">Corrective Action #{i}</h2>
        <div style="font-size: 12px; color: var(--c-text-secondary); margin-top: 0.25rem;">§ {esc(clause)} — {esc(title[:60])}</div>
      </div>
      <button class="checksheet-modal-close" onclick="closeActionModal('{modal_id}')">&times;</button>
    </div>
    <div class="checksheet-modal-body">
      <!-- Recommendation -->
      <div style="background: var(--c-blue-bg); border: 1px solid var(--c-blue-light); border-radius: var(--radius-sm); padding: 1rem; margin-bottom: 1.25rem;">
        <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--c-blue); margin-bottom: 0.25rem;">Recommended Action</div>
        <div style="font-size: 13px; color: var(--c-text); line-height: 1.5;">{esc(recommendation)}</div>
      </div>

      <!-- Stats row -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.25rem;">
        <div style="background: var(--c-bg); border-radius: var(--radius-sm); padding: 1rem;">
          <div style="display: flex; align-items: baseline; gap: 0.5rem; margin-bottom: 0.75rem;">
            <span class="badge {pri_badge}" style="font-size: 10px;">{priority} PRIORITY</span>
            <span style="font-family: var(--font-mono); font-size: 11px; color: var(--c-text-muted);">Risk: {risk_weighted:,}</span>
          </div>
{sev_bars}        </div>
        <div style="background: var(--c-bg); border-radius: var(--radius-sm); padding: 1rem;">
          <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--c-text-muted); margin-bottom: 0.5rem;">Affected Parts</div>
          <div style="display: flex; flex-wrap: wrap; gap: 4px;">{parts_chips}</div>
        </div>
      </div>

      <!-- Findings table -->
      <h4>All Findings ({len(findings)})</h4>
      <div style="overflow-x: auto; max-height: 320px; overflow-y: auto;">
        <table style="font-size: 11px; width: 100%;">
          <thead><tr>
            <th style="font-size: 10px;">Severity</th>
            <th style="font-size: 10px;">Part</th>
            <th style="font-size: 10px;">Type</th>
            <th style="font-size: 10px;">Finding Detail</th>
          </tr></thead>
          <tbody>
{findings_rows}          </tbody>
        </table>
      </div>
      {remaining_note}
    </div>
  </div>
</div>
'''

    return f'''<div class="section" data-section="corrective-actions">
  <div class="section-header">
    <span class="section-num">10</span>
    <span class="section-title">Corrective Actions</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <p>Top corrective actions ranked by risk priority. Click any action for full detail.</p>

{actions_html}  </div>
</div>

{modals_html}'''

def _section_confirmation_review(confirmation_review):
    """Confirmation review section."""
    checklist = confirmation_review.get("checklist", [])
    summary = esc(confirmation_review.get("summary", "Review pending"))

    items_html = ""
    for item in checklist[:10]:
        item_name = esc(item.get("item", ""))
        status = esc(item.get("status", ""))
        badge_cls = badge_class(status)

        items_html += f'''      <tr>
        <td>{item_name}</td>
        <td><span class="badge {badge_cls}">{status}</span></td>
      </tr>
'''

    return f'''<div class="section" data-section="confirmation-review">
  <div class="section-header">
    <span class="section-num">11</span>
    <span class="section-title">Confirmation Review</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <p>{summary}</p>

    <table>
      <thead>
        <tr>
          <th class="sortable">Item</th>
          <th class="sortable">Status</th>
        </tr>
      </thead>
      <tbody>
{items_html}      </tbody>
    </table>
  </div>
</div>'''

def _section_verification_review(verification_review):
    """Verification review section."""
    raw_summary = verification_review.get("summary", "Verification review pending.")
    work_products = verification_review.get("work_products", [])
    methods = verification_review.get("method_recommendations", [])

    # Build summary display — handle dict or string
    if isinstance(raw_summary, dict):
        total_wp = raw_summary.get("total_work_products", 0)
        adequate = raw_summary.get("adequate", 0)
        partial = raw_summary.get("partial", 0)
        insufficient = raw_summary.get("insufficient", 0)
        adequacy_rate = raw_summary.get("adequacy_rate", 0)
        result = raw_summary.get("result", "PENDING")

        result_color = "var(--c-green)" if result == "PASSED" else "var(--c-red)"
        result_badge = "badge-pass" if result == "PASSED" else "badge-fail"

        summary = f'''<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
      <div style="background: var(--c-bg); border-radius: var(--radius-sm); padding: 1rem; text-align: center;">
        <div style="font-family: var(--font-mono); font-size: 28px; font-weight: 700; color: var(--c-navy);">{total_wp}</div>
        <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--c-text-muted);">Total Work Products</div>
      </div>
      <div style="background: var(--c-green-bg); border-radius: var(--radius-sm); padding: 1rem; text-align: center;">
        <div style="font-family: var(--font-mono); font-size: 28px; font-weight: 700; color: var(--c-green);">{adequate}</div>
        <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--c-green);">Adequate</div>
      </div>
      <div style="background: var(--c-amber-bg); border-radius: var(--radius-sm); padding: 1rem; text-align: center;">
        <div style="font-family: var(--font-mono); font-size: 28px; font-weight: 700; color: var(--c-amber);">{partial}</div>
        <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--c-amber);">Partial</div>
      </div>
      <div style="background: var(--c-red-bg); border-radius: var(--radius-sm); padding: 1rem; text-align: center;">
        <div style="font-family: var(--font-mono); font-size: 28px; font-weight: 700; color: var(--c-red);">{insufficient}</div>
        <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--c-red);">Insufficient</div>
      </div>
      <div style="background: var(--c-bg); border-radius: var(--radius-sm); padding: 1rem; text-align: center;">
        <div style="font-family: var(--font-mono); font-size: 28px; font-weight: 700; color: var(--c-navy);">{adequacy_rate:.0f}%</div>
        <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--c-text-muted);">Adequacy Rate</div>
      </div>
      <div style="background: var(--c-bg); border-radius: var(--radius-sm); padding: 1rem; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center;">
        <span class="badge {result_badge}" style="font-size: 12px; padding: 0.4rem 0.8rem;">{esc(result)}</span>
      </div>
    </div>'''
    else:
        summary = f'<p>{esc(str(raw_summary))}</p>'

    # Build work products table
    wp_html = ""
    for wp in work_products:
        if isinstance(wp, dict):
            wp_id = esc(wp.get("id", ""))
            wp_name = esc(wp.get("name", ""))
            wp_status = esc(wp.get("status", ""))
            status_badge_cls = badge_class(wp_status)
            methods_found = wp.get("methods_found", [])
            methods_missing = wp.get("methods_missing", [])
            wp_html += f'''      <tr>
        <td style="font-family: var(--font-mono); font-size: 11px;">{wp_id}</td>
        <td>{wp_name}</td>
        <td><span class="badge {status_badge_cls}">{wp_status}</span></td>
        <td style="font-size: 12px; color: var(--c-text-secondary);">{", ".join([esc(m) for m in methods_found]) or "—"}</td>
        <td style="font-size: 12px; color: var(--c-text-secondary);">{", ".join([esc(m) for m in methods_missing]) or "—"}</td>
      </tr>
'''
        else:
            wp_html += f'      <tr><td colspan="5" style="color: var(--c-text-secondary);">{esc(str(wp))}</td></tr>\n'

    # Build method recommendations table
    method_html = ""
    for method in methods:
        if isinstance(method, dict):
            method_name = esc(method.get("method", ""))
            asil_a = esc(method.get("asil_a", ""))
            asil_b = esc(method.get("asil_b", ""))
            asil_c = esc(method.get("asil_c", ""))
            asil_d = esc(method.get("asil_d", ""))
            applicable = esc(method.get("applicable", ""))
            method_html += f'''      <tr>
        <td>{method_name}</td>
        <td style="text-align: center;">{asil_a}</td>
        <td style="text-align: center;">{asil_b}</td>
        <td style="text-align: center;">{asil_c}</td>
        <td style="text-align: center;">{asil_d}</td>
        <td style="text-align: center;">{applicable}</td>
      </tr>
'''
        else:
            method_html += f'      <tr><td colspan="6" style="color: var(--c-text-secondary);">{esc(str(method))}</td></tr>\n'

    return f'''<div class="section" data-section="verification-review">
  <div class="section-header">
    <span class="section-num">12</span>
    <span class="section-title">Verification Review</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    {summary}

    <h3>Work Products Reviewed</h3>
    <table style="font-size: 12px;">
      <thead>
        <tr>
          <th class="sortable">ID</th>
          <th class="sortable">Name</th>
          <th class="sortable">Status</th>
          <th class="sortable">Methods Found</th>
          <th class="sortable">Methods Missing</th>
        </tr>
      </thead>
      <tbody>
{wp_html}      </tbody>
    </table>

    <h3 style="margin-top: 2rem;">Method Recommendations</h3>
    <table style="font-size: 12px;">
      <thead>
        <tr>
          <th class="sortable">Method</th>
          <th class="sortable">ASIL A</th>
          <th class="sortable">ASIL B</th>
          <th class="sortable">ASIL C</th>
          <th class="sortable">ASIL D</th>
          <th class="sortable">Applicable</th>
        </tr>
      </thead>
      <tbody>
{method_html}      </tbody>
    </table>
  </div>
</div>'''

def _section_assessment_decision(assessment_decision, compliance_score):
    """Assessment decision section."""
    verdict = esc(assessment_decision.get("verdict", "Assessment Complete"))
    description = esc(assessment_decision.get("description", ""))
    conditions = assessment_decision.get("conditions", [])

    badge_cls = badge_class(verdict)

    cond_html = ""
    for cond in conditions[:5]:
        cond_html += f'    <li style="color: var(--c-text-secondary);">{esc(cond)}</li>\n'

    return f'''<div class="section" data-section="assessment-decision">
  <div class="section-header">
    <span class="section-num">13</span>
    <span class="section-title">Assessment Decision</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 2rem;">
      <span class="badge {badge_cls}" style="font-size: 14px; padding: 0.5rem 1rem;">{verdict}</span>
      <div>
        <div style="font-size: 24px; font-family: var(--font-display); font-weight: 700; color: var(--c-navy);">{compliance_score:.1f}%</div>
        <div style="font-size: 11px; color: var(--c-text-secondary); text-transform: uppercase;">Compliance Score</div>
      </div>
    </div>

    <p>{description}</p>

    <h3>Conditions</h3>
    <ul style="padding-left: 1.5rem;">
{cond_html}    </ul>
  </div>
</div>'''

def _section_checksheet_coverage(gap_analysis):
    """Checksheet coverage section with clickable cards and rich detail modals."""

    # Aggregate findings per part from gap_analysis
    from collections import defaultdict
    part_findings = defaultdict(lambda: {"CRITICAL": 0, "MAJOR": 0, "WARNING": 0, "INFO": 0, "clauses": [], "details": []})
    for gap in gap_analysis.get("gaps", []):
        for finding in gap.get("findings", []):
            group = finding.get("group", "unknown")
            sev = finding.get("severity", "INFO")
            if sev in part_findings[group]:
                part_findings[group][sev] += 1
            clause_id = finding.get("node_id", "")
            title = finding.get("title", "")
            msg = finding.get("message", "")
            part_findings[group]["clauses"].append(clause_id)
            part_findings[group]["details"].append({
                "clause": clause_id, "title": title, "severity": sev, "message": msg
            })

    cards_html = ""
    part_descriptions = {
        "part_2": "Safety management during concept and development — establishes safety plan, DIA, impact analysis, and safety case.",
        "part_3": "Concept phase — item definition, HARA (hazard analysis and risk assessment), functional safety concept, and ASIL determination.",
        "part_4": "Product development at the system level — technical safety concept, system design, integration testing, and safety validation.",
        "part_5": "Product development at the hardware level — hardware safety requirements, design, SPFM/LFM/PMHF metrics, integration and verification.",
        "part_6": "Product development at the software level — software safety requirements, architecture, unit design, implementation, and verification.",
        "part_7": "Production, operation, service and decommissioning — manufacturing controls, maintenance procedures, field monitoring.",
        "part_8": "Supporting processes — interfaces within distributed development, requirements management, change management, documentation, tool confidence, SW component qualification.",
        "part_9": "ASIL-oriented and safety-oriented analyses — qualitative/quantitative safety analysis methods, fault tree, FMEA, dependent failure analysis.",
        "part_10": "Guidelines on ISO 26262 — informative guidance on applying the standard, ASIL decomposition rationale, and safety element out of context.",
        "part_11": "Guidelines on application of ISO 26262 to semiconductors — digital/analog/mixed-signal IC safety mechanisms, fault models, and metrics.",
        "part_12": "Adaptation of ISO 26262 for motorcycles — ASIL adaptation factors, rider behavior considerations, and reduced complexity allowances.",
    }

    modals_html = ""
    for part_id in ["part_2", "part_3", "part_4", "part_5", "part_6", "part_7", "part_8", "part_9", "part_10", "part_11", "part_12"]:
        if part_id in CHECKSHEET_REGISTRY:
            part = CHECKSHEET_REGISTRY[part_id]
            title = esc(part["title"])
            checksheets = part["checksheets"]
            total = part["total_items"]
            description = part_descriptions.get(part_id, "")

            # Part-specific finding stats
            pf = part_findings.get(part_id, {"CRITICAL": 0, "MAJOR": 0, "WARNING": 0, "INFO": 0, "clauses": [], "details": []})
            crit_count = pf["CRITICAL"]
            major_count = pf["MAJOR"]
            warn_count = pf["WARNING"]
            info_count = pf["INFO"]
            finding_total = crit_count + major_count + warn_count + info_count
            unique_clauses = len(set(pf["clauses"]))

            # Card health indicator
            if finding_total == 0:
                health_color = "var(--c-green)"
                health_icon = "&#10003;"
                health_label = "No Findings"
                border_color = "var(--c-green)"
            elif crit_count > 0:
                health_color = "var(--c-red)"
                health_icon = "&#9888;"
                health_label = f"{finding_total} Findings"
                border_color = "var(--c-red)"
            else:
                health_color = "var(--c-amber)"
                health_icon = "&#9888;"
                health_label = f"{finding_total} Findings"
                border_color = "var(--c-amber)"

            cs_list = ", ".join([esc(cs) for cs in checksheets]) if checksheets else "No checksheets"

            cards_html += f'''    <div class="checksheet-card" onclick="openPartModal('{part_id}')" style="background: var(--c-bg); border: 1px solid var(--c-border); border-top: 3px solid {border_color}; border-radius: var(--radius-sm); padding: 1.25rem; text-align: center; cursor: pointer; transition: all 0.2s;" onmouseover="this.style.boxShadow='var(--shadow-md)'; this.style.transform='translateY(-2px)'" onmouseout="this.style.boxShadow='none'; this.style.transform='translateY(0)'">
      <div style="font-size: 13px; font-weight: 700; color: var(--c-navy); text-transform: uppercase; margin-bottom: 0.25rem;">{part_id.replace('_', ' ')}</div>
      <div style="font-size: 12px; color: var(--c-text); font-weight: 600; margin-bottom: 0.5rem;">{title}</div>
      <div style="font-size: 10px; color: var(--c-text-muted); margin-bottom: 0.5rem;">{cs_list}</div>
      <div style="display: flex; justify-content: center; gap: 0.5rem; align-items: center; margin-bottom: 0.5rem;">
        <span style="color: {health_color}; font-size: 14px;">{health_icon}</span>
        <span style="font-size: 10px; font-weight: 700; color: {health_color}; text-transform: uppercase;">{health_label}</span>
      </div>
      <div style="font-family: var(--font-mono); font-size: 11px; color: var(--c-text-muted);">{total} checksheet items &middot; {unique_clauses} clauses</div>
    </div>
'''

            # --- Build rich modal content ---
            # Severity mini-bars
            sev_bar_html = ""
            for sev_name, sev_count, sev_color in [("Critical", crit_count, "var(--c-red)"), ("Major", major_count, "var(--c-amber)"), ("Warning", warn_count, "#ca8a04"), ("Info", info_count, "var(--c-blue)")]:
                sev_bar_html += f'''        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
          <span style="font-size: 10px; font-weight: 700; color: var(--c-text-muted); width: 55px; text-transform: uppercase;">{sev_name}</span>
          <div style="flex: 1; height: 8px; background: var(--c-border); border-radius: 4px; overflow: hidden;">
            <div style="width: {min(100, (sev_count / max(1, finding_total)) * 100):.0f}%; height: 100%; background: {sev_color}; border-radius: 4px;"></div>
          </div>
          <span style="font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--c-text); min-width: 24px; text-align: right;">{sev_count}</span>
        </div>
'''

            # Checksheet items list
            cs_items_html = ""
            for cs in checksheets:
                cs_items_html += f'        <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0; border-bottom: 1px solid var(--c-border-light);"><span style="color: var(--c-blue); font-size: 12px;">&#9679;</span><span style="font-size: 12px; color: var(--c-text);">{esc(cs)}</span></div>\n'
            if not checksheets:
                cs_items_html = '        <div style="font-size: 12px; color: var(--c-text-muted); font-style: italic;">No checksheets defined for this part</div>\n'

            # Top findings table (up to 10)
            details = pf["details"]
            findings_table_html = ""
            if details:
                findings_rows = ""
                seen_clauses = set()
                for d in details:
                    cl = d["clause"]
                    if cl in seen_clauses:
                        continue
                    seen_clauses.add(cl)
                    sev = d["severity"]
                    sev_cls = severity_class(sev)
                    short_msg = esc(d["message"][:100]) + ("..." if len(d["message"]) > 100 else "")
                    findings_rows += f'''          <tr>
            <td style="font-family: var(--font-mono); font-size: 11px; white-space: nowrap;">{esc(cl)}</td>
            <td style="font-size: 11px;">{esc(d["title"][:40])}</td>
            <td><span class="badge {sev_cls}" style="font-size: 9px;">{sev}</span></td>
            <td style="font-size: 10px; color: var(--c-text-secondary);" title="{esc(d["message"])}">{short_msg}</td>
          </tr>
'''
                    if len(seen_clauses) >= 10:
                        break

                remaining = len(set(d2["clause"] for d2 in details)) - len(seen_clauses)
                remaining_note = f'<div style="font-size: 10px; color: var(--c-text-muted); margin-top: 0.5rem; font-style: italic;">...and {remaining} more clause(s)</div>' if remaining > 0 else ""

                findings_table_html = f'''      <h4 style="margin-top: 1.25rem;">Clause-Level Findings</h4>
        <div style="overflow-x: auto; max-height: 300px; overflow-y: auto;">
        <table style="font-size: 11px; width: 100%;">
          <thead><tr>
            <th style="font-size: 10px;">Clause</th>
            <th style="font-size: 10px;">Title</th>
            <th style="font-size: 10px;">Severity</th>
            <th style="font-size: 10px;">Finding</th>
          </tr></thead>
          <tbody>
{findings_rows}          </tbody>
        </table>
        </div>
        {remaining_note}
'''
            else:
                findings_table_html = '      <div style="text-align: center; padding: 1rem; color: var(--c-green); font-weight: 600; font-size: 13px;">&#10003; No findings — all clauses satisfied</div>'

            modals_html += f'''<div id="modal-{part_id}" class="checksheet-modal" style="display: none;">
  <div class="checksheet-modal-overlay" onclick="closePartModal('{part_id}')"></div>
  <div class="checksheet-modal-content" style="max-width: 720px;">
    <div class="checksheet-modal-header">
      <h2 style="font-size: 18px;">{part_id.replace('_', ' ').upper()} — {title}</h2>
      <button class="checksheet-modal-close" onclick="closePartModal('{part_id}')">&times;</button>
    </div>
    <div class="checksheet-modal-body">
      <p style="color: var(--c-text-secondary); font-size: 12px; line-height: 1.6; margin-bottom: 1rem;">{description}</p>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.25rem;">
        <div style="background: var(--c-bg); border-radius: var(--radius-sm); padding: 1rem;">
          <h4 style="margin: 0 0 0.75rem 0;">Finding Summary</h4>
          <div style="display: flex; align-items: baseline; gap: 0.5rem; margin-bottom: 0.75rem;">
            <span style="font-family: var(--font-mono); font-size: 28px; font-weight: 700; color: {health_color};">{finding_total}</span>
            <span style="font-size: 11px; color: var(--c-text-muted);">total findings across {unique_clauses} clauses</span>
          </div>
{sev_bar_html}        </div>
        <div style="background: var(--c-bg); border-radius: var(--radius-sm); padding: 1rem;">
          <h4 style="margin: 0 0 0.75rem 0;">Checksheets ({len(checksheets)})</h4>
{cs_items_html}          <div style="margin-top: 0.75rem; font-family: var(--font-mono); font-size: 11px; color: var(--c-text-muted);">{total} total assessment items</div>
        </div>
      </div>

{findings_table_html}    </div>
  </div>
</div>
'''

    return f'''<div class="section" data-section="checksheet-coverage">
  <div class="section-header">
    <span class="section-num">14</span>
    <span class="section-title">Checksheet Coverage</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <p>ISO 26262 parts 2–12 checksheet coverage summary. Click any card for details.</p>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin-top: 1.5rem;">
{cards_html}    </div>
  </div>
</div>

{modals_html}

<script>
function openPartModal(partId) {{
  const modal = document.getElementById('modal-' + partId);
  if (modal) {{
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }}
}}

function closePartModal(partId) {{
  const modal = document.getElementById('modal-' + partId);
  if (modal) {{
    modal.style.display = 'none';
    document.body.style.overflow = 'auto';
  }}
}}

function openActionModal(actionId) {{
  const modal = document.getElementById('modal-' + actionId);
  if (modal) {{
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }}
}}

function closeActionModal(actionId) {{
  const modal = document.getElementById('modal-' + actionId);
  if (modal) {{
    modal.style.display = 'none';
    document.body.style.overflow = 'auto';
  }}
}}

// Close modal on escape key
document.addEventListener('keydown', (e) => {{
  if (e.key === 'Escape') {{
    document.querySelectorAll('.checksheet-modal').forEach(m => m.style.display = 'none');
    document.body.style.overflow = 'auto';
  }}
}});
</script>'''

def _section_appendix(standard, engine, check_date):
    """Appendix section."""
    return f'''<div class="section" data-section="appendix">
  <div class="section-header">
    <span class="section-num">15</span>
    <span class="section-title">Appendix</span>
    <button class="section-collapse-btn"></button>
  </div>
  <div class="section-content">
    <h3>Report Metadata</h3>
    <div class="metadata">
      <div class="metadata-item">
        <div class="metadata-label">Standard</div>
        <div class="metadata-value">ISO {standard}</div>
      </div>
      <div class="metadata-item">
        <div class="metadata-label">Engine</div>
        <div class="metadata-value">{engine}</div>
      </div>
      <div class="metadata-item">
        <div class="metadata-label">Generated</div>
        <div class="metadata-value">{check_date}</div>
      </div>
    </div>

    <h3>Assessment Layers</h3>
    <ul style="padding-left: 1.5rem; color: var(--c-text-secondary);">
      <li>Node Coverage — Decision Tree algorithm</li>
      <li>Content Alignment — TF-IDF + Cosine similarity</li>
      <li>Semantic Matching — Ratcliff-Obershelp matching</li>
      <li>Concept Coverage — Set analysis</li>
      <li>Reference Integrity — Graph BFS traversal</li>
      <li>Method Audit — Risk-aware rule set</li>
      <li>Traceability Chain — Directed graph analysis</li>
    </ul>
  </div>
</div>'''

# ============================================================================
# EMBEDDED CSS AND JAVASCRIPT
# ============================================================================

CSS_CONTENT = r'''@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
  color-scheme: light;
  --c-bg: #f5f5f0;
  --c-surface: #ffffff;
  --c-navy: #0a1628;
  --c-text: #1a1a2e;
  --c-text-secondary: #6b7280;
  --c-text-muted: #9ca3af;
  --c-border: #e5e7eb;
  --c-border-light: #f3f4f6;
  --c-red: #dc2626;
  --c-red-light: #fecaca;
  --c-red-bg: #fef2f2;
  --c-amber: #d97706;
  --c-amber-light: #fcd34d;
  --c-amber-bg: #fffbeb;
  --c-green: #059669;
  --c-green-light: #86efac;
  --c-green-bg: #ecfdf5;
  --c-blue: #2563eb;
  --c-blue-light: #bfdbfe;
  --c-blue-bg: #eff6ff;
  --font-display: 'Fraunces', Georgia, serif;
  --font-body: 'Plus Jakarta Sans', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Cascadia Code', monospace;
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2.5rem;
  --space-2xl: 4rem;
  --radius-sm: 2px;
  --radius-md: 4px;
  --radius-lg: 8px;
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 10px 25px rgba(0, 0, 0, 0.1);
  --ease-expo: cubic-bezier(0.16, 1, 0.3, 1);
}

[data-theme="dark"] {
  color-scheme: dark;
  --c-bg: #0f172a;
  --c-surface: #1a2744;
  --c-border: #334155;
  --c-border-light: #475569;
  --c-text: #e2e8f0;
  --c-text-secondary: #cbd5e1;
  --c-text-muted: #94a3b8;
}

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  font-size: 15px;
  scroll-behavior: smooth;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

body {
  font-family: var(--font-body);
  color: var(--c-text);
  background: var(--c-bg);
  line-height: 1.65;
  display: flex;
  min-height: 100vh;
}

::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

::-webkit-scrollbar-track {
  background: var(--c-bg);
}

::-webkit-scrollbar-thumb {
  background: var(--c-border);
  border-radius: 5px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--c-text-secondary);
}

.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  width: 240px;
  height: 100vh;
  background: var(--c-navy);
  border-right: 1px solid rgba(0,0,0,0.1);
  padding: var(--space-lg);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  z-index: 1000;
  color: white;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding-bottom: var(--space-lg);
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.sidebar-logo-icon {
  width: 36px;
  height: 36px;
  background: rgba(255,255,255,0.15);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: #fff;
  font-size: 14px;
}

.sidebar-logo-text {
  font-size: 11px;
  font-weight: 600;
  color: rgba(255,255,255,0.8);
  line-height: 1.4;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sidebar-search {
  display: flex;
  align-items: center;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: var(--radius-md);
  padding: var(--space-sm) var(--space-md);
  gap: var(--space-sm);
}

.sidebar-search input {
  flex: 1;
  border: none;
  background: none;
  font-family: var(--font-body);
  font-size: 13px;
  color: white;
}

.sidebar-search input::placeholder {
  color: rgba(255,255,255,0.5);
}

.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow-y: auto;
}

.sidebar-nav-item {
  padding: 0.5rem var(--space-md);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  color: rgba(255,255,255,0.65);
  transition: all 0.2s;
  border-left: 3px solid transparent;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.nav-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  font-family: var(--font-mono);
  background: rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.4);
  flex-shrink: 0;
}

.sidebar-nav-item:hover {
  background: rgba(255,255,255,0.08);
  color: white;
}

.sidebar-nav-item:hover .nav-num {
  background: rgba(255,255,255,0.15);
  color: rgba(255,255,255,0.8);
}

.sidebar-nav-item.active {
  background: rgba(255,255,255,0.1);
  color: white;
  border-left-color: var(--c-amber);
  font-weight: 600;
}

.sidebar-nav-item.active .nav-num {
  background: var(--c-amber);
  color: var(--c-navy);
}

.sidebar-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  border-top: 1px solid rgba(255,255,255,0.1);
  padding-top: var(--space-md);
}

.sidebar-button {
  padding: var(--space-sm) var(--space-md);
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 600;
  color: white;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
}

.sidebar-button:hover {
  background: rgba(255,255,255,0.15);
}

.report {
  margin-left: 240px;
  flex: 1;
  background: var(--c-bg);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.report-container {
  max-width: 1000px;
  margin: 0 auto;
  width: 100%;
  padding: var(--space-2xl) var(--space-xl);
}

.page-footer {
  text-align: center;
  padding: var(--space-xl);
  font-size: 11px;
  color: var(--c-text-muted);
  border-top: 1px solid var(--c-border);
  margin-top: auto;
  background: var(--c-surface);
  font-family: var(--font-mono);
}

.section {
  background: var(--c-surface);
  max-width: 1000px;
  margin: 0 auto var(--space-xl);
  padding: 3rem 3.5rem;
  border: 1px solid #e5e7eb;
  border-radius: var(--radius-sm);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  position: relative;
  transition: all 0.3s;
  opacity: 0;
  animation: reveal 0.6s var(--ease-expo) forwards;
}

.section:nth-child(1) { animation-delay: 0ms; }
.section:nth-child(2) { animation-delay: 50ms; }
.section:nth-child(3) { animation-delay: 100ms; }
.section:nth-child(4) { animation-delay: 150ms; }
.section:nth-child(5) { animation-delay: 200ms; }
.section:nth-child(n+6) { animation-delay: 250ms; }

@keyframes reveal {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .section {
    animation: none;
    opacity: 1;
  }
}

.section-header {
  display: flex;
  align-items: baseline;
  gap: var(--space-md);
  margin-bottom: var(--space-xl);
  cursor: pointer;
  user-select: none;
  position: relative;
}

.section-num {
  font-family: var(--font-display);
  font-size: 48px;
  font-weight: 700;
  color: #e5e7eb;
  line-height: 0.9;
}

.section-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--c-navy);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  line-height: 1.2;
}

.section-collapse-btn {
  margin-left: auto;
  cursor: pointer;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  transition: all 0.2s;
}

.section-collapse-btn:hover {
  background: var(--c-border);
}

.section-collapse-btn::after {
  content: '▼';
  font-size: 10px;
  color: var(--c-text-secondary);
  transition: transform 0.3s;
}

.section.collapsed .section-collapse-btn::after {
  transform: rotate(-180deg);
}

.section-content {
  display: grid;
  grid-template-rows: 1fr;
  transition: all 0.3s;
  overflow: hidden;
}

.section.collapsed .section-content {
  grid-template-rows: 0fr;
}

h1, h2, h3, h4 {
  font-family: var(--font-display);
  font-weight: 700;
  margin-top: var(--space-lg);
  margin-bottom: var(--space-md);
  color: var(--c-navy);
}

h1 {
  font-size: 36px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

h2 {
  font-size: 24px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding-bottom: var(--space-md);
  margin-bottom: var(--space-lg);
}

h3 {
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--c-text);
}

p {
  margin-bottom: var(--space-md);
  color: var(--c-text-secondary);
  line-height: 1.7;
}

.metric-card {
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  padding: var(--space-lg);
  text-align: center;
  transition: all 0.3s;
}

.metric-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--c-blue);
}

.metric-value {
  font-family: var(--font-display);
  font-size: 52px;
  font-weight: 700;
  margin-bottom: var(--space-sm);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.metric-value.score-pass {
  color: var(--c-green);
}

.metric-value.score-warn {
  color: var(--c-amber);
}

.metric-value.score-fail {
  color: var(--c-red);
}

.metric-label {
  font-size: 11px;
  color: var(--c-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--space-lg);
  margin-bottom: var(--space-xl);
}

.layer-indicators {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--space-md);
  margin-bottom: var(--space-xl);
  padding: var(--space-lg);
  background: var(--c-bg);
  border-radius: var(--radius-sm);
}

.layer-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: 12px;
  font-weight: 500;
}

.layer-indicator-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.severity-summary {
  margin: var(--space-xl) 0;
}

.severity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--space-lg);
  margin-top: var(--space-lg);
}

.sev-box {
  padding: var(--space-lg);
  border-radius: var(--radius-sm);
  text-align: center;
  transition: all 0.2s;
  border: 1px solid;
}

.sev-box:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.sev-critical {
  background: var(--c-red-bg);
  border-color: var(--c-red);
}

.sev-major {
  background: var(--c-amber-bg);
  border-color: var(--c-amber);
}

.sev-warning {
  background: var(--c-amber-bg);
  border-color: var(--c-amber);
}

.sev-info {
  background: var(--c-blue-bg);
  border-color: var(--c-blue);
}

.sev-count {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  margin-bottom: var(--space-xs);
  font-variant-numeric: tabular-nums;
}

.sev-critical .sev-count { color: var(--c-red); }
.sev-major .sev-count { color: var(--c-amber); }
.sev-warning .sev-count { color: var(--c-amber); }
.sev-info .sev-count { color: var(--c-blue); }

.sev-name {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--c-text-secondary);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-xl);
  margin-top: var(--space-xl);
}

.chart-panel {
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  padding: var(--space-lg);
}

.chart-panel-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--c-navy);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: var(--space-lg);
  text-align: center;
}

.chart-container {
  display: flex;
  justify-content: center;
  align-items: center;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: var(--space-lg) 0;
  font-size: 13px;
}

thead {
  background: var(--c-navy);
  color: white;
}

th {
  padding: 12px 16px;
  text-align: left;
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  cursor: pointer;
  user-select: none;
  transition: all 0.2s;
  position: relative;
}

th:hover {
  background: rgba(10, 22, 40, 0.85);
}

th.sortable::after {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-left: var(--space-sm);
  opacity: 0.3;
  background: white;
  clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
}

th.sort-asc::after {
  opacity: 1;
  transform: rotate(180deg);
}

th.sort-desc::after {
  opacity: 1;
}

td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--c-border-light);
  font-family: var(--font-mono);
  font-size: 12px;
}

tbody tr {
  transition: all 0.2s;
  background: white;
}

tbody tr:nth-child(even) {
  background: #fafafa;
}

tbody tr:hover {
  background: var(--c-bg);
  box-shadow: var(--shadow-sm);
}

.badge {
  display: inline-block;
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-md);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  transition: all 0.2s;
}

.badge-pass {
  background: var(--c-green-bg);
  color: var(--c-green);
  border: 1px solid var(--c-green-light);
}

.badge-warn {
  background: var(--c-amber-bg);
  color: var(--c-amber);
  border: 1px solid var(--c-amber-light);
}

.badge-fail {
  background: var(--c-red-bg);
  color: var(--c-red);
  border: 1px solid var(--c-red-light);
}

.badge-info {
  background: var(--c-blue-bg);
  color: var(--c-blue);
  border: 1px solid var(--c-blue-light);
}

.badge:hover {
  transform: scale(1.05);
  box-shadow: var(--shadow-sm);
}

.scroll-to-top {
  position: fixed;
  bottom: 30px;
  right: 30px;
  width: 44px;
  height: 44px;
  background: var(--c-navy);
  color: white;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: none;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  z-index: 999;
  box-shadow: var(--shadow-lg);
  transition: all 0.3s;
}

.scroll-to-top.visible {
  display: flex;
}

.scroll-to-top:hover {
  transform: translateY(-4px);
  background: var(--c-blue);
}

.filter-buttons {
  display: flex;
  gap: var(--space-sm);
  margin-bottom: var(--space-lg);
  flex-wrap: wrap;
}

.filter-btn {
  padding: var(--space-sm) var(--space-md);
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  transition: all 0.2s;
  color: var(--c-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.filter-btn:hover {
  background: var(--c-border);
  color: var(--c-text);
}

.filter-btn.active {
  background: var(--c-navy);
  border-color: var(--c-navy);
  color: white;
}

.hidden-row {
  display: none;
}

.search-highlight {
  background: var(--c-amber-bg);
  color: var(--c-text);
  font-weight: 600;
  padding: 1px 3px;
  border-radius: 2px;
}

.match-count {
  font-size: 11px;
  color: var(--c-text-secondary);
  margin-top: var(--space-sm);
}

@media (max-width: 1024px) {
  .sidebar {
    width: 0;
    padding: 0;
    border-right: none;
    transform: translateX(-100%);
    transition: transform 0.3s;
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .report {
    margin-left: 0;
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .sidebar {
    width: 100%;
  }

  .report-container {
    padding: var(--space-lg);
  }

  .section {
    padding: var(--space-lg);
    margin-bottom: var(--space-lg);
  }

  .section-num {
    font-size: 32px;
  }

  .section-title {
    font-size: 18px;
  }

  th, td {
    padding: var(--space-sm);
    font-size: 11px;
  }

  .scroll-to-top {
    bottom: 20px;
    right: 20px;
    width: 40px;
    height: 40px;
    font-size: 16px;
  }
}

@media print {
  .sidebar,
  .scroll-to-top,
  .sidebar-button {
    display: none !important;
  }

  body {
    display: block;
  }

  .report {
    margin-left: 0;
    background: white;
  }

  .section {
    page-break-inside: avoid;
    box-shadow: none;
    margin-bottom: 0.5in;
  }

  .section-collapse-btn {
    display: none;
  }

  table {
    width: 100%;
  }

  @page {
    margin: 1in;
    size: letter;
  }

  @page :first {
    margin-top: 0.5in;
  }
}

.metadata {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-lg);
  margin: var(--space-xl) 0;
}

.metadata-item {
  padding: var(--space-md);
  background: var(--c-bg);
  border-radius: var(--radius-sm);
}

.metadata-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--c-text-secondary);
  font-weight: 700;
  margin-bottom: var(--space-xs);
}

.metadata-value {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--c-navy);
}

.subsection-title {
  margin-top: var(--space-xl);
  margin-bottom: var(--space-lg);
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--c-navy);
}

/* Modal styles for checksheet coverage */
.checksheet-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  animation: modalFadeIn 0.2s ease-out;
}

@keyframes modalFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.checksheet-modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  cursor: pointer;
}

.checksheet-modal-content {
  background: var(--c-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
  z-index: 2001;
  animation: modalSlideUp 0.3s ease-out;
}

@keyframes modalSlideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.checksheet-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-lg);
  border-bottom: 1px solid var(--c-border);
}

.checksheet-modal-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--c-navy);
}

.checksheet-modal-close {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: var(--c-text-secondary);
  transition: color 0.2s;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.checksheet-modal-close:hover {
  color: var(--c-text);
}

.checksheet-modal-body {
  padding: var(--space-lg);
}

.checksheet-modal-body h4 {
  margin: var(--space-lg) 0 var(--space-md) 0;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--c-navy);
}

/* Waterfall bar animation */
@keyframes waterfall-expand {
  from {
    width: 0;
  }
  to {
    width: var(--final-width);
  }
}

.waterfall-bar {
  transform-origin: left;
}

/* ── Visual Traceability Tree ── */
.tt-root {
  position: relative;
  padding: 0;
}

.tt-root-node {
  text-align: center;
  background: var(--c-navy);
  color: white;
  border-radius: var(--radius-sm);
  padding: 0.75rem 1.5rem;
  display: inline-block;
  margin: 0 auto;
  position: relative;
  left: 50%;
  transform: translateX(-50%);
}

.tt-root-label {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.tt-root-meta {
  font-size: 10px;
  opacity: 0.7;
  margin-top: 2px;
}

.tt-trunk {
  width: 2px;
  height: 24px;
  background: var(--c-border);
  margin: 0 auto;
}

.tt-branches {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.tt-artifact {
  position: relative;
  margin-bottom: 2px;
}

.tt-artifact-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 1rem;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.tt-artifact-header:hover {
  border-color: var(--c-blue);
  box-shadow: var(--shadow-sm);
}

.tt-artifact-icon {
  width: 32px;
  height: 32px;
  background: var(--c-navy);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
}

.tt-artifact-info {
  flex: 1;
  min-width: 0;
}

.tt-artifact-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-navy);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tt-artifact-meta {
  font-size: 10px;
  color: var(--c-text-muted);
  margin-top: 1px;
}

.tt-artifact-bar {
  width: 60px;
  height: 6px;
  background: var(--c-border);
  border-radius: 3px;
  overflow: hidden;
  flex-shrink: 0;
}

.tt-artifact-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s ease;
}

.tt-expand-arrow {
  font-size: 10px;
  color: var(--c-text-muted);
  transition: transform 0.25s ease;
  flex-shrink: 0;
}

.tt-artifact.open .tt-expand-arrow {
  transform: rotate(180deg);
}

.tt-artifact-children {
  display: none;
  position: relative;
  padding: 0 0 0 2.5rem;
  overflow: hidden;
}

.tt-artifact.open .tt-artifact-children {
  display: block;
  animation: ttSlideDown 0.3s ease forwards;
}

@keyframes ttSlideDown {
  from { opacity: 0; max-height: 0; }
  to { opacity: 1; max-height: 2000px; }
}

.tt-connector-v {
  position: absolute;
  left: 2.5rem;
  top: 0;
  bottom: 0.5rem;
  width: 2px;
  background: var(--c-border);
}

.tt-req-list {
  position: relative;
}

.tt-req {
  display: flex;
  align-items: flex-start;
  position: relative;
  padding: 4px 0;
}

.tt-connector-h {
  width: 20px;
  height: 2px;
  background: var(--c-border);
  margin-top: 16px;
  flex-shrink: 0;
}

.tt-req-card {
  flex: 1;
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  padding: 0.5rem 0.75rem;
  transition: all 0.2s;
}

.tt-req-card:hover {
  box-shadow: var(--shadow-sm);
  border-color: var(--c-blue-light);
}

.tt-req-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.tt-req-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.tt-req-id {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  color: var(--c-navy);
}

.tt-req-status {
  font-size: 10px;
  font-weight: 600;
  margin-left: auto;
}

.tt-req-methods {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tt-method {
  font-size: 9px;
  padding: 1px 6px;
  background: var(--c-blue-bg);
  color: var(--c-blue);
  border-radius: 8px;
  font-weight: 500;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .tt-root-node { left: 0; transform: none; }
  .tt-artifact-header { flex-wrap: wrap; }
  .tt-artifact-bar { width: 100%; margin-top: 4px; }
}
'''

JS_CONTENT = r'''
(function() {
  'use strict';

  const themeToggle = document.getElementById('toggleTheme');
  const htmlElement = document.documentElement;

  function setTheme(theme) {
    htmlElement.setAttribute('data-theme', theme);
    sessionStorage.setItem('theme', theme);
    themeToggle.textContent = theme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode';
  }

  function initTheme() {
    const savedTheme = sessionStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
  }

  themeToggle.addEventListener('click', () => {
    const current = htmlElement.getAttribute('data-theme') || 'light';
    const newTheme = current === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
  });

  document.querySelectorAll('.section-collapse-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const section = btn.closest('.section');
      if (section) {
        section.classList.toggle('collapsed');
        sessionStorage.setItem(`section-${section.dataset.section}`, section.classList.contains('collapsed'));
      }
    });
  });

  document.querySelectorAll('.section').forEach(section => {
    const key = `section-${section.dataset.section}`;
    if (sessionStorage.getItem(key) === 'true') {
      section.classList.add('collapsed');
    }
  });

  const navItems = document.querySelectorAll('.sidebar-nav-item');
  const sections = document.querySelectorAll('.section[data-section]');

  const observerOptions = {
    threshold: 0.15,
    rootMargin: '-80px 0px -40% 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const sectionId = entry.target.dataset.section;
        navItems.forEach(item => item.classList.remove('active'));
        const activeItem = document.querySelector(`.sidebar-nav-item[data-nav-section="${sectionId}"]`);
        if (activeItem) {
          activeItem.classList.add('active');
          activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    });
  }, observerOptions);

  sections.forEach(section => observer.observe(section));

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const sectionId = item.dataset.navSection;
      const targetSection = document.querySelector(`.section[data-section="${sectionId}"]`);
      if (targetSection) {
        targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        navItems.forEach(i => i.classList.remove('active'));
        item.classList.add('active');
      }
    });
  });

  const scrollToTopBtn = document.getElementById('scrollToTop');
  window.addEventListener('scroll', () => {
    if (window.pageYOffset > 300) {
      scrollToTopBtn.classList.add('visible');
    } else {
      scrollToTopBtn.classList.remove('visible');
    }
  });

  scrollToTopBtn.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  const searchInput = document.getElementById('globalSearch');
  let currentMatchIndex = 0;
  let allMatches = [];

  function performSearch(query) {
    allMatches = [];
    currentMatchIndex = 0;

    if (!query.trim()) {
      document.querySelectorAll('.search-highlight').forEach(el => {
        el.classList.remove('search-highlight');
        el.textContent = el.textContent;
      });
      return;
    }

    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      null,
      false
    );

    let node;
    const nodesToReplace = [];

    while (node = walker.nextNode()) {
      if (regex.test(node.textContent)) {
        nodesToReplace.push(node);
        regex.lastIndex = 0;
      }
    }

    nodesToReplace.forEach(node => {
      const span = document.createElement('span');
      span.innerHTML = node.textContent.replace(regex, '<mark class="search-highlight">$1</mark>');
      node.parentNode.replaceChild(span, node);
      const marks = span.querySelectorAll('.search-highlight');
      allMatches.push(...marks);
    });

    if (allMatches.length > 0) {
      allMatches[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
      allMatches[0].style.backgroundColor = '#fef08a';
    }

    const matchInfo = document.querySelector('.match-count');
    if (matchInfo) {
      matchInfo.textContent = allMatches.length > 0 ? `${allMatches.length} matches found` : 'No matches';
    }
  }

  searchInput.addEventListener('input', (e) => {
    performSearch(e.target.value);
  });

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && allMatches.length > 0) {
      currentMatchIndex = (currentMatchIndex + 1) % allMatches.length;
      allMatches[currentMatchIndex].scrollIntoView({ behavior: 'smooth', block: 'center' });
      allMatches.forEach(m => m.style.backgroundColor = '');
      allMatches[currentMatchIndex].style.backgroundColor = '#fef08a';
    }
    if (e.key === 'Escape') {
      searchInput.value = '';
      performSearch('');
    }
  });

  document.querySelectorAll('table').forEach(table => {
    const headers = table.querySelectorAll('thead th');
    headers.forEach((header, index) => {
      if (!header.classList.contains('sortable')) {
        header.classList.add('sortable');
      }

      header.addEventListener('click', () => {
        const isAsc = header.classList.contains('sort-asc');
        headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
        header.classList.add(isAsc ? 'sort-desc' : 'sort-asc');

        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));

        rows.sort((a, b) => {
          const aVal = a.children[index].textContent.trim();
          const bVal = b.children[index].textContent.trim();
          const aNum = parseFloat(aVal);
          const bNum = parseFloat(bVal);

          if (!isNaN(aNum) && !isNaN(bNum)) {
            return isAsc ? bNum - aNum : aNum - bNum;
          }
          return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
        });

        rows.forEach(row => tbody.appendChild(row));
      });
    });
  });

  const filterBtns = document.querySelectorAll('.filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const filter = btn.dataset.filter;
      const table = btn.closest('.section')?.querySelector('table');

      if (!table) return;

      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const rows = table.querySelectorAll('tbody tr');
      rows.forEach(row => {
        row.classList.remove('hidden-row');
        if (filter !== 'all') {
          const status = row.dataset.status;
          if (!status || !status.includes(filter)) {
            row.classList.add('hidden-row');
          }
        }
      });
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 't' && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      themeToggle.click();
    }
    if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      searchInput.focus();
    }
    if (e.key === 'Escape') {
      searchInput.blur();
    }
    if (e.key === 'j') {
      e.preventDefault();
      const current = document.querySelector('.sidebar-nav-item.active');
      const next = current?.nextElementSibling || navItems[0];
      if (next) next.click();
    }
    if (e.key === 'k') {
      e.preventDefault();
      const current = document.querySelector('.sidebar-nav-item.active');
      const prev = current?.previousElementSibling || navItems[navItems.length - 1];
      if (prev) prev.click();
    }
  });

  // ── Traceability tree toggle ──
  window.toggleTraceArtifact = function(headerEl) {
    const artifact = headerEl.closest('.tt-artifact');
    if (artifact) {
      artifact.classList.toggle('open');
    }
  };

  window.expandAllTrace = function() {
    document.querySelectorAll('.tt-artifact').forEach(a => a.classList.add('open'));
  };

  window.collapseAllTrace = function() {
    document.querySelectorAll('.tt-artifact').forEach(a => a.classList.remove('open'));
  };

  initTheme();
})();
'''

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            report = json.load(f)
        output = sys.argv[2] if len(sys.argv) > 2 else 'report.html'
        generate_compliance_html(report, output)
        print(f'Report generated: {output}')
