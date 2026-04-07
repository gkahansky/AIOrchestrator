import sys

# 1. New HTML template
TEMPLATE = r'''<!DOCTYPE html>
<html class="light" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Accessibility Report - {{ url }}</title>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600;1,700&amp;family=Manrope:wght@300;400;500;600;700;800&amp;family=Inter:wght@300;400;500;600;700&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    "colors": {
                        "secondary": "#ae2f34",
                        "on-secondary-container": "#6d0010",
                        "surface-container": "#eceef0",
                        "on-primary-fixed": "#001c38",
                        "on-secondary": "#ffffff",
                        "on-tertiary-fixed": "#002113",
                        "surface": "#f7f9fb",
                        "inverse-on-surface": "#eff1f3",
                        "tertiary-fixed": "#6ffbbe",
                        "secondary-fixed": "#ffdad8",
                        "outline-variant": "#c3c6cf",
                        "on-surface": "#191c1e",
                        "tertiary": "#000f07",
                        "surface-tint": "#456084",
                        "on-error": "#ffffff",
                        "surface-container-highest": "#e0e3e5",
                        "on-secondary-fixed-variant": "#8c1520",
                        "on-surface-variant": "#43474e",
                        "on-tertiary-container": "#009d6c",
                        "on-tertiary": "#ffffff",
                        "surface-container-lowest": "#ffffff",
                        "primary": "#000c1e",
                        "surface-variant": "#e0e3e5",
                        "on-secondary-fixed": "#410006",
                        "secondary-fixed-dim": "#ffb3b0",
                        "inverse-primary": "#adc8f2",
                        "on-background": "#191c1e",
                        "surface-container-low": "#f2f4f6",
                        "inverse-surface": "#2d3133",
                        "secondary-container": "#ff6b6b",
                        "on-primary": "#ffffff",
                        "tertiary-fixed-dim": "#4edea3",
                        "on-tertiary-fixed-variant": "#005236",
                        "primary-container": "#002344",
                        "primary-fixed-dim": "#adc8f2",
                        "on-primary-fixed-variant": "#2c486b",
                        "surface-dim": "#d8dadc",
                        "error-container": "#ffdad6",
                        "tertiary-container": "#002819",
                        "primary-fixed": "#d3e3ff",
                        "on-error-container": "#93000a",
                        "surface-container-high": "#e6e8ea",
                        "surface-bright": "#f7f9fb",
                        "background": "#f7f9fb",
                        "error": "#ba1a1a",
                        "on-primary-container": "#708bb2",
                        "outline": "#74777f"
                    },
                    "borderRadius": {
                        "DEFAULT": "0.125rem",
                        "lg": "0.25rem",
                        "xl": "0.5rem",
                        "full": "0.75rem"
                    },
                    "fontFamily": {
                        "headline": ["Newsreader", "serif"],
                        "body": ["Manrope", "sans-serif"],
                        "label": ["Inter", "sans-serif"]
                    }
                }
            }
        }
</script>
<style>
    .material-symbols-outlined {
        font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
        display: inline-block;
        vertical-align: middle;
    }
    .chart-dial {
        background: conic-gradient(from 180deg at 50% 50%, #000c1e 0deg, #000c1e {{ dial_deg }}deg, #eceef0 {{ dial_deg }}deg, #eceef0 360deg);
    }
    .a4-container {
        margin: 0 auto;
        background: white;
        min-height: 100dvh;
    }
    @media print {
        .no-print { display: none; }
        body { background: white; padding: 0; }
        .a4-container { 
            box-shadow: none; 
            width: 100%; 
            margin: 0;
        }
        header, footer { position: static !important; }
        section { break-inside: avoid; }
    }
    body {
        background-color: #f1f3f5;
        min-height: 100dvh;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
</style>
</head>
<body class="font-body text-on-surface selection:bg-primary-fixed">
<div class="a4-container bg-surface relative">

<!-- Top Navigation Anchor (No Borders) -->
<header class="bg-surface/90 sticky top-0 z-50 pt-8 pb-4">
<div class="flex justify-between items-center w-full px-12 max-w-5xl mx-auto">
    <div class="flex flex-row items-center">
        <!-- EchoForge Logo -->
        <div class="flex items-center gap-2.5 mr-6">
            <div class="relative flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-blue-900 to-primary shadow-[0_4px_12px_rgba(0,12,30,0.15)] overflow-hidden">
                <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 8v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    <path d="M10 12h4"></path><path d="M10 16h4"></path><path d="M10 8h4"></path>
                </svg>
            </div>
            <span class="text-2xl font-headline font-semibold text-primary tracking-tight">EchoForge</span>
        </div>
        <span class="ml-6 text-[10px] font-label font-bold text-outline uppercase tracking-widest">{{ title_prefix }}</span>
    </div>
    <div class="flex items-center gap-6">
        <span class="font-label text-[10px] font-bold uppercase tracking-widest text-outline">{{ formatted_date }}</span>
    </div>
</div>
</header>

<main class="px-12 py-10 space-y-24 pb-32 max-w-5xl mx-auto">

<!-- Executive Summary Section -->
<section class="grid grid-cols-12 gap-8 items-start" id="summary">
    <div class="col-span-12 space-y-4 mb-2">
        <h1 class="text-5xl font-headline font-semibold text-primary leading-tight">Accessibility <span class="italic font-medium">Audit Results</span></h1>
        <p class="text-base text-on-surface-variant font-light max-w-3xl leading-relaxed">A comprehensive analytical audit of digital infrastructure compliance evaluated against global WCAG standards for <strong class="text-primary">{{ url }}</strong>.</p>
    </div>

    <!-- Main Scorecard (Lowest Surface for Pop) -->
    <div class="col-span-5 bg-surface-container-lowest p-10 rounded-xl relative overflow-hidden h-full flex flex-col justify-between shadow-[0_8px_30px_rgba(0,0,0,0.02)]">
        <div class="absolute top-0 right-0 p-6">
            <span class="text-[9px] font-label uppercase tracking-widest text-outline">Audit Status</span>
        </div>
        
        <div class="flex flex-col items-center justify-center my-6">
            <div class="relative w-48 h-48 mb-8">
                <div class="chart-dial w-full h-full rounded-full flex items-center justify-center p-3 shadow-inner">
                    <div class="bg-surface-container-lowest w-full h-full rounded-full flex flex-col items-center justify-center shadow-[0_2px_15px_rgba(0,0,0,0.06)]">
                        <span class="text-6xl font-headline font-bold text-primary">{{ overall_score }}</span>
                        <span class="text-[9px] font-label uppercase tracking-widest text-outline mt-1 font-bold">Composite</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="mt-4 pt-6 grid grid-cols-1 gap-4">
            <div class="text-center">
                <h3 class="text-2xl font-headline font-semibold text-primary">{{ compliance_status }}</h3>
                <p class="text-on-surface-variant text-sm mt-2 font-light leading-relaxed px-4">{{ compliance_description }}</p>
            </div>
        </div>
    </div>

    <!-- Weighted Breakdown -->
    <div class="col-span-7 bg-surface-container-low p-10 rounded-xl space-y-8 flex flex-col h-full">
        <!-- Replaced borders with background contrast per DESIGN.md -->
        <div class="bg-primary p-8 rounded-xl text-on-primary">
            <span class="text-[10px] font-label font-bold uppercase tracking-widest text-primary-fixed-dim mb-4 block">Audit Overview</span>
            <p class="text-2xl font-headline italic leading-snug">
                During the automated scan, <span class="font-medium text-tertiary-fixed">{{ violation_rules_count }}</span> unique accessibility rules were flagged across <span class="font-medium text-tertiary-fixed">{{ violation_instances_count }}</span> separate instances.
            </p>
        </div>
        
        <!-- Grid using surface-container-lowest per "The Layering Principle" -->
        <div class="grid grid-cols-4 gap-4 flex-grow">
            <div class="bg-surface-container-lowest p-6 rounded-xl flex flex-col justify-center text-center shadow-[0_4px_20px_rgba(0,0,0,0.02)]">
                <span class="block text-4xl font-headline font-bold text-secondary mb-2">{{ count_critical }}</span>
                <span class="text-[9px] font-label font-bold uppercase tracking-widest text-outline block">Critical</span>
            </div>
            <div class="bg-surface-container-lowest p-6 rounded-xl flex flex-col justify-center text-center shadow-[0_4px_20px_rgba(0,0,0,0.02)]">
                <span class="block text-4xl font-headline font-bold text-secondary-container mb-2">{{ count_high }}</span>
                <span class="text-[9px] font-label font-bold uppercase tracking-widest text-outline block">High</span>
            </div>
            <div class="bg-surface-container-lowest p-6 rounded-xl flex flex-col justify-center text-center shadow-[0_4px_20px_rgba(0,0,0,0.02)]">
                <span class="block text-4xl font-headline font-bold text-primary mb-2">{{ count_medium }}</span>
                <span class="text-[9px] font-label font-bold uppercase tracking-widest text-outline block">Medium</span>
            </div>
            <div class="bg-surface-container-lowest p-6 rounded-xl flex flex-col justify-center text-center shadow-[0_4px_20px_rgba(0,0,0,0.02)]">
                <span class="block text-4xl font-headline font-bold text-surface-tint mb-2">{{ count_low }}</span>
                <span class="text-[9px] font-label font-bold uppercase tracking-widest text-outline block">Low</span>
            </div>
        </div>

        <p class="text-xs text-on-surface-variant font-body mt-2 bg-surface p-4 rounded-lg">
            Additional context: <strong class="text-primary">{{ incomplete_count }}</strong> incomplete automated checks requiring manual review, and <strong class="text-primary">{{ passes_count }}</strong> successful checks.
        </p>
    </div>
</section>

<!-- Compliance Categories -->
<section class="space-y-10" id="categories">
    <div class="flex justify-between items-baseline mb-4">
        <h2 class="text-4xl font-headline font-semibold text-primary">Compliance <span class="italic font-medium">Categories</span></h2>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-12">
        {{ checklist_html }}
    </div>
</section>

<!-- Violation Overview -->
<section class="space-y-8" id="overview">
    <div class="flex justify-between items-baseline pb-2">
        <h2 class="text-4xl font-headline font-semibold text-primary">Violation <span class="italic font-medium">Overview</span></h2>
    </div>
    <div class="bg-surface-container-low rounded-xl px-3 py-3">
        <div class="w-full text-left">
            <div class="grid grid-cols-12 gap-4 px-6 py-5 bg-surface-container-high rounded-t-lg">
                <div class="col-span-6 text-[10px] font-label font-bold uppercase tracking-widest text-on-surface-variant">Violation Description</div>
                <div class="col-span-2 text-[10px] font-label font-bold uppercase tracking-widest text-on-surface-variant text-center">Pct %</div>
                <div class="col-span-2 text-[10px] font-label font-bold uppercase tracking-widest text-on-surface-variant text-center">Total</div>
                <div class="col-span-2 text-[10px] font-label font-bold uppercase tracking-widest text-on-surface-variant text-center">Severity</div>
            </div>
            <div class="space-y-2 mb-1 mt-2">
                {{ overview_table_html }}
            </div>
        </div>
    </div>
</section>

<!-- Critical Findings -->
<section class="space-y-10" id="findings">
    <div class="flex justify-between items-baseline pb-2">
        <h2 class="text-4xl font-headline font-semibold text-primary">Critical <span class="italic font-medium">Findings</span></h2>
    </div>
    <div class="space-y-8">
        {{ deepdive_html }}
    </div>
</section>

</main>

<!-- Footer -->
<footer class="py-10 px-12 mt-12 bg-surface text-center">
    <div class="flex justify-between items-center opacity-60 max-w-5xl mx-auto">
        <p class="text-[9px] font-label font-bold uppercase tracking-widest">© 2026 EchoForge. Confidential.</p>
        <p class="text-[9px] font-label font-bold uppercase tracking-widest">Accessibility Integrity Report</p>
    </div>
</footer>
</div>
</body></html>
'''

with open('src/aiplatform/skills/audit/report_template.html', 'w', encoding='utf-8') as f:
    f.write(TEMPLATE)

# 2. Re-write the python generation
PYTHON_CODE = r'''"""
Skill: generate_accessibility_report
Render a PDF summary for an accessibility audit using Playwright and an HTML template.

Input:
    audit_data   (dict): axe scan result payload.
    output_path  (str):  Path to the PDF to create.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from datetime import datetime

from playwright.sync_api import sync_playwright

WCAG_MAP = {
    "1.1.1": ("1.1.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html"),
    "1.2.1": ("1.2.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/audio-only-and-video-only-prerecorded.html"),
    "1.2.2": ("1.2.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded.html"),
    "1.3.1": ("1.3.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships.html"),
    "1.3.5": ("1.3.5 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/identify-input-purpose.html"),
    "1.4.1": ("1.4.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html"),
    "1.4.3": ("1.4.3 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html"),
    "1.4.4": ("1.4.4 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html"),
    "1.4.11": ("1.4.11 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html"),
    "1.4.12": ("1.4.12 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html"),
    "2.1.1": ("2.1.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html"),
    "2.2.1": ("2.2.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html"),
    "2.2.2": ("2.2.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html"),
    "2.4.1": ("2.4.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/bypass-blocks.html"),
    "2.4.2": ("2.4.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/page-titled.html"),
    "2.4.4": ("2.4.4 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html"),
    "2.4.6": ("2.4.6 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/headings-and-labels.html"),
    "2.4.7": ("2.4.7 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html"),
    "3.1.1": ("3.1.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/language-of-page.html"),
    "3.1.2": ("3.1.2 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/language-of-parts.html"),
    "3.2.2": ("3.2.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/on-input.html"),
    "3.3.2": ("3.3.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html"),
    "4.1.1": ("4.1.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/parsing.html"),
    "4.1.2": ("4.1.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html"),
    "4.1.3": ("4.1.3 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html"),
}

def _html_escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def _map_impact_to_severity(impact: str) -> str:
    mapping = {"minor": "Low", "moderate": "Medium", "serious": "High", "critical": "Critical"}
    return mapping.get(impact, "Medium")

def _get_severity_order(severity: str) -> int:
    return {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}.get(severity, 5)

def _get_wcag_principle(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("wcag1"): return "1. Perceivable"
        elif tag.startswith("wcag2"): return "2. Operable"
        elif tag.startswith("wcag3"): return "3. Understandable"
        elif tag.startswith("wcag4"): return "4. Robust"
    return "Other Principles"

def _get_wcag_criteria(tags: list[str], rule_id: str) -> str:
    for tag in tags:
        if tag.startswith("wcag") and len(tag) >= 7:
            criteria = tag.replace("wcag", "")
            if len(criteria) >= 3 and criteria[:3].isdigit():
                return f"{criteria[0]}.{criteria[1]}.{criteria[2:]}"
    return rule_id

def _generate_compliant_snippet(rule_id: str, html_code: str, default_summary: str) -> tuple[str, str]:
    if "color-contrast" in rule_id:
        return None, default_summary
        
    html_lower = html_code.lower()
    if rule_id == "image-alt" and "<img" in html_lower:
        fixed = re.sub(r'<img([^>]*)>', r'<img\1 alt="Appropriate descriptive text">', html_code, flags=re.IGNORECASE)
        fixed = re.sub(r' alt=""', '', fixed, flags=re.IGNORECASE)
        if fixed != html_code: return fixed, "Provide a descriptive alt attribute for the image."
    elif rule_id == "button-name" and "<button" in html_lower:
        if ">" in html_code:
            fixed = re.sub(r'<button([^>]*)>(.*?)</button>', r'<button\1 aria-label="Descriptive action">\2</button>', html_code, flags=re.IGNORECASE)
            return fixed, "Ensure standard buttons or icon buttons have a programmatic name via aria-label or visible text."
    elif rule_id == "link-name" and "<a " in html_lower:
        fixed = re.sub(r'<a([^>]*)>(.*?)</a>', r'<a\1>Descriptive link text</a>', html_code, flags=re.IGNORECASE)
        return fixed, "Ensure links have discernible text that describes the destination."
    elif rule_id == "html-has-lang" and "<html" in html_lower:
        fixed = re.sub(r'<html([^>]*)>', r'<html\1 lang="en">', html_code, flags=re.IGNORECASE)
        return fixed, "Add a lang attribute to the root html element."
        
    return None, default_summary

# Map severity to CSS classes matching DESIGN.md with no borders layout
SEV_CLASSES = {
    "Critical": "bg-secondary text-on-secondary",
    "High": "bg-secondary-container text-on-secondary-container",
    "Medium": "bg-primary text-on-primary",
    "Low": "bg-surface-tint text-on-primary"
}

def generate_accessibility_report(audit_data: dict, output_path: str, tier: str = "standard") -> dict:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    violations = audit_data.get("violations", []) or []
    incomplete = audit_data.get("incomplete", []) or []
    passes = audit_data.get("passes", []) or []
    wcag_score = audit_data.get("wcag_score", 0)
    url = audit_data.get("url", "")
    
    raw_ts = audit_data.get("timestamp", "")
    try:
        if isinstance(raw_ts, str) and raw_ts.endswith("Z"): raw_ts = raw_ts[:-1]
        dt = datetime.fromisoformat(raw_ts)
        formatted_date = dt.strftime("%B %d, %Y")
    except Exception:
        formatted_date = raw_ts

    is_sample = tier in {"single_page", "sample"}
    flattened_violations = []
    
    checklist_map = { "1. Perceivable": {}, "2. Operable": {}, "3. Understandable": {}, "4. Robust": {} }
    
    for p in passes:
        tags = p.get("tags", [])
        principle = _get_wcag_principle(tags)
        if principle in checklist_map:
            key = _get_wcag_criteria(tags, p.get("id"))
            checklist_map[principle][key] = {"id": p.get("id"), "wcag": key, "status": "Pass"}

    for rule in violations:
        rule_id = rule.get("id", "unknown")
        rule_desc = rule.get("description", "No description")
        tags = rule.get("tags", [])
        principle = _get_wcag_principle(tags)
        wcag_criteria = _get_wcag_criteria(tags, rule_id)
        
        if principle in checklist_map:
            checklist_map[principle][wcag_criteria] = {"id": rule_id, "wcag": wcag_criteria, "status": "Fail"}

        nodes = rule.get("nodes", [])
        if not nodes:
            impact = rule.get("impact", "moderate")
            flattened_violations.append({
                "severity": _map_impact_to_severity(impact), "principle": principle,
                "rule_id": rule_id, "description": rule_desc, "wcag_criteria": wcag_criteria,
                "html": "N/A", "target": "N/A", "failureSummary": rule.get("help", "No remediation provided.")
            })
        else:
            for node in nodes:
                impact = node.get("impact") or rule.get("impact", "moderate")
                target_str = ", ".join(node.get("target", [])) if node.get("target") else "N/A"
                flattened_violations.append({
                    "severity": _map_impact_to_severity(impact), "principle": principle,
                    "rule_id": rule_id, "description": rule_desc, "wcag_criteria": wcag_criteria,
                    "html": node.get("html", "N/A"), "target": target_str,
                    "failureSummary": node.get("failureSummary", node.get("help", ""))
                })

    flattened_violations.sort(key=lambda x: (_get_severity_order(x["severity"]), x["principle"]))
    total_instances = len(flattened_violations)
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    violation_summary = {}
    
    for item in flattened_violations:
        counts[item["severity"]] += 1
        key = (item["rule_id"], item["description"])
        if key not in violation_summary: 
            violation_summary[key] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Total": 0}
        violation_summary[key][item["severity"]] += 1
        violation_summary[key]["Total"] += 1

    overview_table_html = ""
    for (rule_id, rule_desc), cnt in sorted(violation_summary.items(), key=lambda x: x[1]["Total"], reverse=True):
        pct = (cnt["Total"] / total_instances * 100) if total_instances > 0 else 0
        desc_esc = _html_escape(rule_desc)
        
        brk = f"""
        <div class="text-left inline-block text-[9px] leading-tight space-y-1 font-label uppercase tracking-widest pl-2">
            <div class="text-secondary font-bold">Crit: {cnt['Critical']}</div>
            <div class="text-secondary-container font-bold">High: {cnt['High']}</div>
            <div class="text-primary font-bold">Med: {cnt['Medium']}</div>
            <div class="text-surface-tint font-bold">Low: {cnt['Low']}</div>
        </div>
        """
        
        overview_table_html += f"""
        <div class="bg-surface-container-lowest flex w-full items-center p-4 rounded-xl shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
            <div class="grid grid-cols-12 gap-4 w-full items-center">
                <div class="col-span-6 pr-4 border-r border-surface-container">
                    <p class="text-sm font-bold text-primary">{desc_esc}</p>
                    <p class="text-[10px] text-outline mt-1 font-label uppercase tracking-widest">Rule ID: {_html_escape(rule_id)}</p>
                </div>
                <div class="col-span-2 text-center text-sm font-bold text-primary">{pct:.1f}%</div>
                <div class="col-span-2 text-center text-xl font-headline font-bold text-primary border-l border-surface-container">{cnt["Total"]}</div>
                <div class="col-span-2 text-center font-mono border-l border-surface-container flex items-center justify-center">
                    {brk}
                </div>
            </div>
        </div>
        """
        
    if not violation_summary:
        overview_table_html = '<div class="p-8 text-center text-outline">No violations found.</div>'

    active_principles = {k: v for k, v in checklist_map.items() if v}
    is_single_section = len(active_principles) == 1
    
    checklist_html = ""
    for prin, items_dict in active_principles.items():
        display_prin = prin.split(" ", 1)[1] if is_single_section and " " in prin else prin
        checklist_html += f"<div class='bg-surface-container-lowest p-8 rounded-xl shadow-[0_4px_20px_rgba(0,0,0,0.02)]'><h4 class='text-2xl font-headline font-semibold text-primary mb-6'>{display_prin}</h4><ul class='space-y-4'>"
        for wcag, info in sorted(items_dict.items()):
            label, _ = WCAG_MAP.get(wcag, (wcag, ""))
            if info["status"] == "Fail": 
                span = "<span class='flex items-center gap-2 text-[10px] font-label font-bold text-secondary uppercase tracking-widest'><span class='material-symbols-outlined text-sm'>cancel</span> Fail</span>"
            else: 
                span = "<span class='flex items-center gap-2 text-[10px] font-label font-bold text-on-tertiary-container uppercase tracking-widest'><span class='material-symbols-outlined text-sm'>check_circle</span> Pass</span>"
            # Using vertical padding instead of divide borders per DESIGN.md where possible, or very light borders
            checklist_html += f"<li class='flex items-center justify-between py-3 border-b border-surface-container last:border-0'><span class='text-sm text-on-surface-variant font-medium'>{label}</span>{span}</li>"
        checklist_html += "</ul></div>"

    visible_violations = flattened_violations[:4] if is_sample else flattened_violations
    hidden_violations = max(0, len(flattened_violations) - len(visible_violations))
    
    deepdive_html = ""
    for item in visible_violations:
        sev = item["severity"]
        rule_id = item["rule_id"]
        sev_class = SEV_CLASSES.get(sev, SEV_CLASSES["Medium"])
        wcag_raw = item["wcag_criteria"]
        wcag_label, wcag_link = WCAG_MAP.get(wcag_raw, (f"{wcag_raw} (WCAG)", "https://www.w3.org/WAI/standards-guidelines/wcag/"))
        desc = _html_escape(item["description"])
        target = _html_escape(item["target"])
        html_code = _html_escape(item["html"])
        raw_remediation = item["failureSummary"]
        remediation_text = _html_escape(raw_remediation).replace("\\n", "<br/>")

        compliant_code, updated_summary = _generate_compliant_snippet(rule_id, item["html"], raw_remediation)
        
        remediation_html = ""
        if compliant_code:
            remediation_desc = _html_escape(updated_summary)
            remediation_code_esc = _html_escape(compliant_code)
            remediation_html = f"""
                        <div class="text-sm text-on-surface-variant font-medium leading-relaxed mb-4 p-4 bg-surface rounded-lg">
                            {remediation_desc}
                        </div>
                        <div class="bg-surface p-5 rounded-lg font-mono text-xs overflow-x-auto border-l-4 border-tertiary-fixed-dim">
                            <h4 class="text-[9px] font-label font-bold uppercase tracking-widest text-primary mb-3">Compliant Example Reference</h4>
                            <div class="whitespace-pre-wrap text-primary">{remediation_code_esc}</div>
                        </div>
            """
        else:
            remediation_html = f"""
                        <div class="text-sm text-on-surface-variant font-medium leading-relaxed p-4 bg-surface rounded-lg">
                            {remediation_text}
                        </div>
            """

        deepdive_html += f"""
        <div class="bg-surface-container-lowest p-10 rounded-xl relative overflow-hidden break-inside-avoid mt-4 shadow-[0_4px_20px_rgba(0,0,0,0.03)] border border-surface-container">
            <div class="relative z-10">
                <div class="flex items-center gap-4 mb-5">
                    <span class="px-3 py-1.5 {sev_class} text-[9px] font-label font-bold uppercase tracking-widest rounded-full">{sev} Finding</span>
                    <h3 class="text-2xl font-headline font-semibold text-primary">{desc}</h3>
                </div>
                <div class="mb-10 block">
                    <a class="text-[10px] font-label font-bold text-primary uppercase tracking-widest hover:underline bg-primary-fixed/30 px-3 py-1.5 rounded-full" href="{wcag_link}">WCAG Success Criterion: {wcag_label}</a>
                </div>
                <div class="grid grid-cols-1 gap-6">
                    <div class="bg-surface-container-low p-6 rounded-xl flex flex-col gap-2">
                        <h4 class="text-[9px] font-label font-bold uppercase tracking-widest text-outline">Target Element Context</h4>
                        <div class="text-sm text-on-surface font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">{target}</div>
                    </div>
                    <!-- Using High-Contrast Block for Issue -->
                    <div class="bg-primary p-6 rounded-xl text-on-primary flex flex-col gap-2">
                        <h4 class="text-[9px] font-label font-bold uppercase tracking-widest text-primary-fixed-dim">Detected Non-Compliant Code</h4>
                        <div class="font-mono text-xs overflow-x-auto whitespace-pre-wrap text-inverse-primary leading-relaxed mt-1">{html_code}</div>
                    </div>
                    <div class="bg-surface-container-low p-6 rounded-xl flex flex-col gap-2 mt-2">
                        <h4 class="text-[9px] font-label font-bold uppercase tracking-widest text-outline">Remediation Action Plan</h4>
                        {remediation_html}
                    </div>
                </div>
            </div>
        </div>
        """

    if is_sample and hidden_violations > 0:
        deepdive_html += f"""
        <div class="bg-surface-container-lowest border border-outline-variant/10 p-12 rounded-xl text-center break-inside-avoid mt-8">
            <h3 class="text-3xl font-headline font-semibold text-primary mb-2">{hidden_violations} Additional Occurrences Detected</h3>
            <p class="text-on-surface-variant font-light max-w-2xl mx-auto">The remaining isolated instances have been identified. Review the full extended compliance audit to access all targets.</p>
        </div>
        """

    try: wcag_score_float = float(wcag_score)
    except: wcag_score_float = 0.0
    dial_deg = int((wcag_score_float / 100.0) * 360)

    tpl_path = Path(__file__).parent / "report_template.html"
    with open(tpl_path, "r", encoding="utf-8") as f:
        html_str = f.read()

    replacements = {
        "{{ url }}": str(url),
        "{{ title_prefix }}": "Sample Scan" if is_sample else "Full Audit",
        "{{ formatted_date }}": str(formatted_date),
        "{{ overall_score }}": str(wcag_score),
        "{{ dial_deg }}": str(dial_deg),
        "{{ compliance_status }}": "Requires Action" if total_instances > 0 else "Compliant",
        "{{ compliance_description }}": "Immediate systemic improvements are mandated to meet production-level accessibility criteria." if total_instances > 0 else "No violations were found during automated scanning.",
        "{{ count_critical }}": str(counts["Critical"]),
        "{{ count_high }}": str(counts["High"]),
        "{{ count_medium }}": str(counts["Medium"]),
        "{{ count_low }}": str(counts["Low"]),
        "{{ incomplete_count }}": str(len(incomplete)),
        "{{ passes_count }}": str(len(passes)),
        "{{ violation_rules_count }}": str(len(violations)),
        "{{ violation_instances_count }}": str(total_instances),
        "{{ checklist_html }}": checklist_html,
        "{{ overview_table_html }}": overview_table_html,
        "{{ deepdive_html }}": deepdive_html
    }

    for k, v in replacements.items():
        html_str = html_str.replace(k, v)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page()
        page.set_content(html_str, wait_until="networkidle")
        page.pdf(
            path=str(output),
            print_background=True,
            format="A4",
            margin={"top": "0in", "bottom": "0in", "left": "0in", "right": "0in"}
        )
        browser.close()

    return {
        "pdf_path": str(output),
        "size_bytes": output.stat().st_size,
        "violation_rules": len(violations),
        "violation_instances": len(flattened_violations),
        "is_sample": is_sample,
    }
'''

with open('src/aiplatform/skills/audit/generate_accessibility_report.py', 'w', encoding='utf-8') as f:
    f.write(PYTHON_CODE)

print("Done")
