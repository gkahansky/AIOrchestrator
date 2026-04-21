import sys
from pathlib import Path

TEMPLATE = r'''<!DOCTYPE html>
<html class="light" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Marketing Audit Report - {{ url }}</title>
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
        .a4-container {
            margin: 0 auto;
            background: white;
            min-height: 100vh;
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
            min-height: 100vh;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
    </style>
</head>
<body class="font-body text-on-surface selection:bg-primary-fixed">
<div class="a4-container bg-surface relative">
<!-- Top Navigation Anchor -->
<header class="bg-surface/90 sticky top-0 z-50 pt-8 pb-4">
<div class="flex justify-between items-center w-full px-12 max-w-5xl mx-auto">
<div class="flex flex-row items-center">
<div class="flex items-center gap-2.5 mr-6">
<div class="relative flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-blue-900 to-primary shadow-[0_4px_12px_rgba(0,12,30,0.15)] overflow-hidden">
<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
<path d="M21 8v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
<path d="M10 12h4"></path><path d="M10 16h4"></path><path d="M10 8h4"></path>
</svg>
</div>
<span class="text-2xl font-headline font-semibold text-primary tracking-tight">EchoForge</span>
</div>
</div>
</div>
</header>

<main class="px-12 py-10 space-y-24 pb-32 max-w-5xl mx-auto">
<!-- Executive Summary Section -->
<section class="grid grid-cols-12 gap-8 items-start" id="summary">
<div class="col-span-12 space-y-4 mb-2">
<h2 class="text-5xl font-headline font-semibold text-primary leading-tight">Operational <span class="italic font-medium">Stagnation</span> Detected.</h2>
<p class="text-base text-on-surface-variant font-light max-w-3xl leading-relaxed">{{ summary_p }}</p>
</div>
<!-- Main Scorecard -->
<div class="col-span-5 bg-surface-container-lowest p-10 rounded-xl shadow-[0_8px_30px_rgba(0,0,0,0.02)] border border-surface-container relative overflow-hidden h-full flex flex-col justify-between">
<div class="absolute top-0 right-0 p-6">
<span class="text-[9px] font-label uppercase tracking-widest text-outline">Audit Status: {{ audit_status }}</span>
</div>
<div class="flex flex-col items-start gap-4 mt-6">
<div class="flex items-end gap-2">
<span class="text-8xl font-headline font-bold text-secondary leading-none">{{ overall_score }}</span>
<span class="block font-headline italic text-primary leading-none text-xl mb-2">/100</span>
</div>
<div class="mt-2">
<span class="block font-headline font-bold {{ grade_color }} text-3xl">Grade {{ grade }}</span>
</div>
</div>
<div class="mt-8 pt-6 border-t border-surface-container grid grid-cols-1 gap-4 w-full">
<div>
<span class="block text-[9px] font-label uppercase tracking-widest text-outline">Target URL</span>
<span class="text-xs font-semibold truncate block mt-1">{{ url }}</span>
</div>
<div>
<span class="block text-[9px] font-label uppercase tracking-widest text-outline">Audit Date</span>
<span class="text-xs font-semibold block mt-1">{{ audit_date }}</span>
</div>
</div>
</div>
<!-- Weighted Breakdown -->
<div class="col-span-7 bg-surface-container-low p-8 rounded-xl space-y-8 flex flex-col h-full border border-surface-container/50">
<div class="flex justify-between items-end">
<h3 class="text-2xl font-headline font-semibold text-primary">Category Weighted Performance</h3>
</div>
<div class="space-y-4 flex-grow">
{{ category_breakdown_html }}
</div>
</div>
</section>

<!-- Key Findings -->
<section class="space-y-10" id="findings">
<div class="flex justify-between items-baseline border-b border-surface-container pb-4">
<h2 class="text-4xl font-headline font-semibold text-primary">Critical <span class="italic font-medium">Audit Findings</span></h2>
<p class="font-label text-[9px] uppercase tracking-widest text-outline">Priority Matrix Identification</p>
</div>
<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
{{ findings_html }}
</div>
</section>

<!-- Strategic Action Plan -->
<section class="space-y-10" id="action-plan">
<div class="text-center space-y-4 max-w-2xl mx-auto mb-10">
<h2 class="text-4xl font-headline font-semibold text-primary">The <span class="italic font-medium">Tactical Roadmap</span></h2>
<p class="text-sm text-on-surface-variant font-light">A prioritized sequence designed to move from Grade {{ grade }} to B within 6 months.</p>
</div>
<div class="space-y-6">
{{ roadmap_html }}
</div>
</section>

<!-- Insight Callout -->
<section class="grid grid-cols-2 gap-8 items-center bg-primary text-on-primary-container p-12 rounded-xl shadow-[0_8px_30px_rgba(0,0,0,0.06)] relative overflow-hidden break-inside-avoid">
<div class="absolute inset-0 bg-gradient-to-r from-primary to-primary-container z-0"></div>
<div class="space-y-6 relative z-10 w-full pr-4">
<h2 class="text-3xl font-headline italic font-medium leading-tight text-white">Insight without action is the silent killer of growth.</h2>
<p class="text-white/80 font-light text-sm leading-relaxed">Addressing these findings within the next 30 days can unlock a substantial increase in your quarterly volume.</p>
</div>
<div class="relative aspect-[4/3] rounded-lg overflow-hidden grayscale opacity-30 shadow-inner z-10 border border-white/10 ml-auto w-full">
<div class="absolute inset-0 bg-primary mix-blend-color"></div>
<svg class="w-full h-full text-white/50" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L2 22h20L12 2z" opacity="0.3"/><path d="M12 6L4 20h16L12 6z"/></svg>
</div>
</section>

</main>
<!-- Footer -->
<footer class="py-10 px-12 mt-12 bg-surface text-center border-t border-surface-container">
<div class="flex justify-between items-center opacity-60 max-w-5xl mx-auto">
<p class="text-[9px] font-label uppercase tracking-widest text-primary font-bold">© 2026 EchoForge. Confidential.</p>
<span class="text-[9px] font-label uppercase tracking-widest text-primary font-bold">Page 01 // Marketing Audit Report</span>
</div>
</footer>
</div>
</body></html>
'''
Path("src/aiplatform/skills/media/market_audit_report_template.html").write_text(TEMPLATE, encoding="utf-8")

PDF_GENERATOR = r'''"""
Format Market Audit PDF using Playwright + HTML templates.
"""

from pathlib import Path
import re
from playwright.sync_api import sync_playwright

def _html_escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def generate_pdf_report(report_data: dict, output_path: str) -> None:
    tpl_path = Path(__file__).parent / "market_audit_report_template.html"
    with open(tpl_path, "r", encoding="utf-8") as f:
        html_str = f.read()

    score = report_data.get("overall_score", 0)
    grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
    grade_color = "text-secondary" if grade in ["D", "F"] else "text-warning" if grade == "C" else "text-tertiary-fixed-dim" if grade == "B" else "text-on-tertiary-container"
    
    categories = report_data.get("categories", {})
    cat_html = ""
    for dim, cat in categories.items():
        cat_score = cat.get("score", 0)
        cat_weight = str(cat.get("weight", "0")).replace("%", "")
        cat_color = "bg-secondary" if cat_score < 60 else "bg-primary" if cat_score < 80 else "bg-tertiary-fixed-dim"
        cat_html += f"""
        <div class="group py-2">
            <div class="flex justify-between items-center mb-2">
                <span class="text-xs font-body font-bold text-primary tracking-wide">{dim}</span>
                <span class="text-xs font-label text-primary font-bold">{cat_score}/100</span>
            </div>
            <div class="h-1.5 w-full bg-surface-container-high rounded-full overflow-hidden">
                <div class="h-full {cat_color} rounded-full" style="width: {cat_score}%"></div>
            </div>
        </div>
        """

    findings_html = ""
    for f in report_data.get("findings", [])[:4]:
        sev = f.get("severity", "Medium")
        color = "text-secondary" if sev == "Critical" else "text-secondary-container" if sev == "High" else "text-primary"
        bg_color = "bg-secondary" if sev == "Critical" else "bg-secondary-container" if sev == "High" else "bg-primary"
        findings_html += f"""
        <div class="bg-surface-container-lowest p-6 rounded-xl border border-surface-container shadow-[0_2px_15px_rgba(0,0,0,0.02)] space-y-3 break-inside-avoid">
            <div class="flex justify-between items-start">
                <span class="material-symbols-outlined {color} text-2xl">speed</span>
                <span class="text-[9px] font-label font-bold {color} px-2 py-0.5 rounded-full uppercase bg-surface-container-high">{sev}</span>
            </div>
            <h4 class="text-base font-headline font-bold text-primary">{_html_escape(f.get('finding', ''))}</h4>
        </div>
        """

    roadmap_html = ""
    def build_roadmap_phase(title, items, phase_color):
        if not items: return ""
        lines = "".join(f'<div class="flex gap-3 items-center"><span class="material-symbols-outlined {phase_color} text-sm">check_box_outline_blank</span><p class="text-xs font-bold text-primary">{_html_escape(win)}</p></div>' for win in items)
        return f"""
        <div class="bg-surface-container-lowest border border-surface-container rounded-xl overflow-hidden flex flex-col sm:flex-row break-inside-avoid shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
            <div class="p-6 {phase_color.replace('text-', 'bg-')} bg-opacity-10 text-on-surface sm:w-1/4 flex flex-col justify-center border-r border-surface-container">
                <h3 class="text-lg font-headline font-bold text-primary">{title}</h3>
            </div>
            <div class="p-6 grid grid-cols-2 gap-4 flex-grow">
                {lines}
            </div>
        </div>
        """

    roadmap_html += build_roadmap_phase("Quick Wins", report_data.get("quick_wins", []), "text-secondary")
    roadmap_html += build_roadmap_phase("Medium-Term", report_data.get("medium_term", []), "text-primary")
    roadmap_html += build_roadmap_phase("Strategic", report_data.get("strategic", []), "text-on-surface-variant")

    replacements = {
        "{{ url }}": _html_escape(report_data.get("url", "")),
        "{{ audit_date }}": _html_escape(report_data.get("date", "")),
        "{{ overall_score }}": str(score),
        "{{ grade }}": grade,
        "{{ grade_color }}": grade_color,
        "{{ audit_status }}": "Critical Action Required" if score < 70 else "Review Recommended",
        "{{ summary_p }}": _html_escape(report_data.get("executive_summary", "")),
        "{{ category_breakdown_html }}": cat_html,
        "{{ findings_html }}": findings_html,
        "{{ roadmap_html }}": roadmap_html,
    }

    for k, v in replacements.items():
        html_str = html_str.replace(k, str(v))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page()
        page.set_content(html_str, wait_until="networkidle")
        output_p = Path(output_path)
        output_p.parent.mkdir(parents=True, exist_ok=True)
        page.pdf(
            path=str(output_p),
            print_background=True,
            format="A4",
            margin={"top": "0in", "bottom": "0in", "left": "0in", "right": "0in"}
        )
        browser.close()
'''
Path("src/aiplatform/skills/media/format_marketing_audit_pdf.py").write_text(PDF_GENERATOR, encoding="utf-8")
'''