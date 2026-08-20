"""
Report Generator - Produces a styled HTML report from the engineering summary.

Opens in any browser, can be printed to PDF (Ctrl+P -> Save as PDF).
Professional formatting with collapsible code sections.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from ..models.schemas import EngineeringSummary


def generate_html_report(summary: EngineeringSummary, output_path: str = "output/report.html") -> str:
    """Generate a professional HTML report from the engineering summary."""

    req = summary.requirement
    arch = summary.architecture
    tg = summary.task_graph
    ts = summary.test_suite
    val = summary.validation

    # Build components table rows
    comp_rows = ""
    if arch and arch.components:
        for c in arch.components:
            comp_rows += f"<tr><td><strong>{esc(c.get('name',''))}</strong></td><td>{esc(c.get('responsibility',''))}</td><td><code>{esc(c.get('technology',''))}</code></td></tr>\n"

    # Build API table rows
    api_rows = ""
    if arch and arch.api_endpoints:
        for ep in arch.api_endpoints:
            method_class = ep.method.lower()
            api_rows += f'<tr><td><span class="method {method_class}">{ep.method}</span></td><td><code>{esc(ep.path)}</code></td><td>{esc(ep.description)}</td></tr>\n'

    # Build task layers
    task_layers_html = ""
    if tg:
        for i, layer in enumerate(tg.execution_order, 1):
            task_names = []
            for tid in layer:
                t = next((t for t in tg.tasks if t.id == tid), None)
                if t:
                    task_names.append(t.name)
            parallel = ' <span class="badge">parallel</span>' if len(task_names) > 1 else ""
            task_layers_html += f'<div class="layer"><strong>Layer {i}</strong>{parallel}: {", ".join(task_names)}</div>\n'

    # Build code artifacts
    code_html = ""
    if summary.code_artifacts:
        for art in summary.code_artifacts:
            code_html += f"""<details class="code-block">
<summary><strong>{esc(art.filepath)}</strong> — {esc(art.description)}</summary>
<pre><code>{esc(art.content)}</code></pre>
</details>\n"""

    # Build test cases
    test_html = ""
    if ts and ts.test_cases:
        for tc in ts.test_cases:
            badge = "unit" if tc.test_type == "unit" else "integration"
            test_html += f"""<details class="code-block">
<summary><code>{esc(tc.name)}</code> <span class="badge {badge}">{tc.test_type}</span> — {esc(tc.description)}</summary>
<pre><code>{esc(tc.code)}</code></pre>
</details>\n"""

    # Build risks table
    risk_rows = ""
    if val and val.risks:
        for r in val.risks:
            sev_class = r.severity.value
            risk_rows += f'<tr><td><span class="severity {sev_class}">{r.severity.value.upper()}</span></td><td>{esc(r.category)}</td><td>{esc(r.description)}</td><td>{esc(r.mitigation)}</td></tr>\n'

    # Build trade-offs
    tradeoffs_html = ""
    if val and val.trade_offs:
        for t in val.trade_offs:
            tradeoffs_html += f"<li>{esc(t)}</li>\n"

    # Tech stack
    tech_html = ""
    if arch and arch.technology_stack:
        for k, v in arch.technology_stack.items():
            tech_html += f"<li><strong>{esc(k)}:</strong> {esc(v)}</li>\n"

    # Ambiguities
    amb_html = ""
    for a in req.ambiguities:
        amb_html += f"<li>⚠️ {esc(a)}</li>\n"

    # Assumptions
    assume_html = ""
    for a in req.assumptions:
        assume_html += f"<li>✅ {esc(a)}</li>\n"

    # FR list
    fr_html = ""
    for i, fr in enumerate(req.functional_requirements, 1):
        fr_html += f"<li>{esc(fr)}</li>\n"

    # NFR list
    nfr_html = ""
    for nfr in req.non_functional_requirements:
        nfr_html += f"<li>{esc(nfr)}</li>\n"

    unit_count = sum(1 for t in ts.test_cases if t.test_type == "unit") if ts else 0
    int_count = sum(1 for t in ts.test_cases if t.test_type == "integration") if ts else 0

    # Build architecture diagram from components
    diagram_html = ""
    if arch and arch.components:
        diagram_html = '<div class="arch-flow">\n'
        for i, comp in enumerate(arch.components):
            name = comp.get('name', '')
            tech = comp.get('technology', '')
            diagram_html += f'  <div class="arch-node"><div class="arch-name">{esc(name)}</div><div class="arch-tech">{esc(tech)}</div></div>\n'
            if i < len(arch.components) - 1:
                diagram_html += '  <div class="arch-arrow">→</div>\n'
        diagram_html += '</div>\n'

        # Add connections if diagram_description has them
        if arch.diagram_description:
            diagram_html += '<div class="arch-connections"><h4>Data Flow</h4><ul>\n'
            for line in arch.diagram_description.replace("\\n", "\n").split("\n"):
                line = line.strip()
                if line and "->" in line:
                    diagram_html += f'<li class="flow-line">⟶ {esc(line)}</li>\n'
                elif line:
                    diagram_html += f'<li class="flow-line">⟶ {esc(line)}</li>\n'
            diagram_html += '</ul></div>\n'

    report_html = HTML_TEMPLATE.format(
        system_name=esc(arch.system_name) if arch else "System",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        original_req=esc(req.original_text),
        req_type=req.requirement_type.value.title(),
        intent=esc(req.intent),
        fr_list=fr_html,
        nfr_list=nfr_html,
        amb_list=amb_html,
        assume_list=assume_html,
        overview=esc(arch.overview) if arch else "",
        diagram_html=diagram_html,
        comp_rows=comp_rows,
        api_rows=api_rows,
        tech_stack=tech_html,
        task_count=len(tg.tasks) if tg else 0,
        layer_count=len(tg.execution_order) if tg else 0,
        task_layers=task_layers_html,
        code_count=len(summary.code_artifacts),
        code_artifacts=code_html,
        test_count=len(ts.test_cases) if ts else 0,
        unit_count=unit_count,
        int_count=int_count,
        test_strategy=esc(ts.testing_strategy) if ts else "",
        test_cases=test_html,
        risk_rows=risk_rows,
        tradeoffs=tradeoffs_html,
        rationale=esc(summary.implementation_rationale),
    )

    # Write to file
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report_html, encoding="utf-8")

    return str(out)


def esc(text: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Engineering Report: {system_name}</title>
<style>
  :root {{
    --primary: #2563eb;
    --success: #16a34a;
    --warning: #d97706;
    --danger: #dc2626;
    --bg: #f8fafc;
    --card: #ffffff;
    --text: #1e293b;
    --muted: #64748b;
    --border: #e2e8f0;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem;
    max-width: 1100px;
    margin: 0 auto;
  }}
  h1 {{ color: var(--primary); margin-bottom: 0.5rem; font-size: 2rem; }}
  h2 {{
    color: var(--primary);
    border-bottom: 2px solid var(--primary);
    padding-bottom: 0.5rem;
    margin: 2.5rem 0 1rem;
    font-size: 1.5rem;
  }}
  h3 {{ color: var(--text); margin: 1.5rem 0 0.75rem; font-size: 1.1rem; }}
  .meta {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 2rem; }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem;
    margin: 1rem 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }}
  .highlight {{ background: #eff6ff; border-left: 4px solid var(--primary); padding: 1rem 1.5rem; border-radius: 4px; margin: 1rem 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }}
  th {{ background: #f1f5f9; text-align: left; padding: 0.75rem; border: 1px solid var(--border); font-weight: 600; }}
  td {{ padding: 0.75rem; border: 1px solid var(--border); vertical-align: top; }}
  tr:hover {{ background: #f8fafc; }}
  code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 3px; font-size: 0.85rem; }}
  pre {{ background: #1e293b; color: #e2e8f0; padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.8rem; line-height: 1.5; }}
  pre code {{ background: none; padding: 0; color: inherit; }}
  ul, ol {{ padding-left: 1.5rem; margin: 0.5rem 0; }}
  li {{ margin: 0.3rem 0; }}
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
  }}
  .badge.parallel {{ background: #dbeafe; color: #1d4ed8; }}
  .badge.unit {{ background: #dcfce7; color: #166534; }}
  .badge.integration {{ background: #fef3c7; color: #92400e; }}
  .method {{ font-weight: 700; font-size: 0.8rem; padding: 2px 6px; border-radius: 3px; }}
  .method.get {{ background: #dcfce7; color: #166534; }}
  .method.post {{ background: #dbeafe; color: #1d4ed8; }}
  .method.put {{ background: #fef3c7; color: #92400e; }}
  .method.delete {{ background: #fee2e2; color: #991b1b; }}
  .severity {{ padding: 2px 8px; border-radius: 3px; font-size: 0.75rem; font-weight: 700; }}
  .severity.low {{ background: #dcfce7; color: #166534; }}
  .severity.medium {{ background: #fef3c7; color: #92400e; }}
  .severity.high {{ background: #fee2e2; color: #991b1b; }}
  .severity.critical {{ background: #991b1b; color: white; }}
  details {{ margin: 0.5rem 0; }}
  details summary {{ cursor: pointer; padding: 0.5rem; background: #f8fafc; border: 1px solid var(--border); border-radius: 4px; }}
  details summary:hover {{ background: #f1f5f9; }}
  details[open] summary {{ border-bottom-left-radius: 0; border-bottom-right-radius: 0; }}
  details pre {{ border-top-left-radius: 0; border-top-right-radius: 0; margin-top: 0; }}
  .stats {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }}
  .stat {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1rem 1.5rem; text-align: center; min-width: 120px; }}
  .stat .number {{ font-size: 2rem; font-weight: 700; color: var(--primary); }}
  .stat .label {{ font-size: 0.8rem; color: var(--muted); text-transform: uppercase; }}
  .layer {{ padding: 0.5rem 0; border-left: 3px solid var(--primary); padding-left: 1rem; margin: 0.5rem 0; }}
  .arch-flow {{ display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 0.5rem; padding: 2rem 1.5rem; background: var(--card); border: 1px solid var(--border); border-radius: 8px; margin: 1rem 0; }}
  .arch-node {{ background: linear-gradient(135deg, #dbeafe, #eff6ff); border: 2px solid var(--primary); border-radius: 10px; padding: 1rem 1.25rem; text-align: center; min-width: 140px; max-width: 180px; box-shadow: 0 2px 6px rgba(37,99,235,0.1); }}
  .arch-name {{ font-weight: 700; font-size: 0.9rem; color: var(--primary); }}
  .arch-tech {{ font-size: 0.72rem; color: var(--muted); margin-top: 4px; font-style: italic; }}
  .arch-arrow {{ font-size: 1.8rem; color: var(--primary); font-weight: bold; padding: 0 0.25rem; }}
  .arch-connections {{ margin: 1.5rem auto; padding: 1.25rem; background: #f8fafc; border-radius: 8px; border: 1px solid var(--border); max-width: 700px; }}
  .arch-connections h4 {{ margin-bottom: 0.75rem; color: var(--primary); text-align: center; }}
  .flow-line {{ padding: 0.4rem 0.5rem; font-size: 0.88rem; border-bottom: 1px dashed var(--border); }}
  .flow-line:last-child {{ border-bottom: none; }}
  .diagram-container {{ margin: 1.5rem 0; text-align: center; }}
  @media print {{
    body {{ padding: 1rem; }}
    details {{ open: true; }}
    .card {{ box-shadow: none; }}
  }}
</style>
</head>
<body>

<h1>🏗️ {system_name}</h1>
<p class="meta">Generated by Agentic SDLC System — {timestamp}</p>

<div class="highlight">
<strong>Requirement:</strong> {original_req}
</div>

<div class="stats">
  <div class="stat"><div class="number">{code_count}</div><div class="label">Code Files</div></div>
  <div class="stat"><div class="number">{test_count}</div><div class="label">Test Cases</div></div>
  <div class="stat"><div class="number">{task_count}</div><div class="label">Tasks</div></div>
  <div class="stat"><div class="number">{layer_count}</div><div class="label">Exec Layers</div></div>
</div>

<h2>1. Requirement Analysis</h2>
<div class="card">
  <p><strong>Type:</strong> {req_type} &nbsp;|&nbsp; <strong>Intent:</strong> {intent}</p>
</div>

<h3>Functional Requirements</h3>
<ol>{fr_list}</ol>

<h3>Non-Functional Requirements</h3>
<ul>{nfr_list}</ul>

<h3>Ambiguities Identified</h3>
<ul>{amb_list}</ul>

<h3>Assumptions Made</h3>
<ul>{assume_list}</ul>

<h2>2. Architecture Design</h2>
<div class="card">
  <p>{overview}</p>
</div>

<h3>System Diagram</h3>
<div class="diagram-container">
{diagram_html}
</div>

<h3>Components</h3>
<table>
<thead><tr><th>Component</th><th>Responsibility</th><th>Technology</th></tr></thead>
<tbody>{comp_rows}</tbody>
</table>

<h3>API Endpoints</h3>
<table>
<thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
<tbody>{api_rows}</tbody>
</table>

<h3>Technology Stack</h3>
<ul>{tech_stack}</ul>

<h2>3. Task Decomposition & Orchestration</h2>
<p><strong>{task_count} tasks</strong> across <strong>{layer_count} execution layers</strong> (tasks in same layer run in parallel):</p>
<div class="card">
{task_layers}
</div>

<h2>4. Generated Code</h2>
<p><strong>{code_count} files</strong> generated and syntax-validated:</p>
{code_artifacts}

<h2>5. Test Suite</h2>
<p><strong>{test_count} test cases</strong> (Unit: {unit_count}, Integration: {int_count})</p>
<p><em>{test_strategy}</em></p>
{test_cases}

<h2>6. Risk Assessment & Validation</h2>
<h3>Identified Risks</h3>
<table>
<thead><tr><th>Severity</th><th>Category</th><th>Description</th><th>Mitigation</th></tr></thead>
<tbody>{risk_rows}</tbody>
</table>

<h3>Trade-offs</h3>
<ul>{tradeoffs}</ul>

<h2>7. Implementation Rationale</h2>
<div class="card">
<p>{rationale}</p>
</div>

</body>
</html>"""
