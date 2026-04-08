"""
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
            </div>
            <h4 class="text-base font-headline font-bold text-primary">{_html_escape(str(f))}</h4>
        </div>
        """

    roadmap_html = ""
    def build_roadmap_phase(title, items, phase_color):
        if not items: return ""
        lines = "".join(f'<div class="flex gap-3 items-center"><span class="material-symbols-outlined {phase_color} text-sm">check_box_outline_blank</span><p class="text-xs font-bold text-primary">{_html_escape(str(win))}</p></div>' for win in items)
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
