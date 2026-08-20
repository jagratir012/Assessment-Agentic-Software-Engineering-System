"""
Quick script to regenerate the HTML report from existing engineering_summary.json.
No API calls needed — just converts the JSON to a beautiful HTML page.

Usage:
    python generate_report.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.models.schemas import EngineeringSummary
from src.tools.report_generator import generate_html_report

# Load existing summary
summary_path = Path("output/engineering_summary.json")
if not summary_path.exists():
    print("No engineering_summary.json found. Run main.py first.")
    sys.exit(1)

data = json.loads(summary_path.read_text(encoding="utf-8"))
summary = EngineeringSummary(**data)

# Generate report
report_path = generate_html_report(summary, "output/report.html")
print(f"✓ Report generated: {report_path}")
print(f"  Open in browser to view, then Ctrl+P to save as PDF")
