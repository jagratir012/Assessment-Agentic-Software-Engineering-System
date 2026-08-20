"""
Web UI for Agentic SDLC System.

Provides a simple web interface where users can:
1. Enter a requirement
2. Submit it to the pipeline
3. View progress in real-time
4. Open the generated HTML report

Usage:
    python app.py
    Then open http://localhost:5000 in your browser
"""

import json
import os
import re
import sys
import time
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template_string, request, jsonify, send_from_directory, redirect

sys.path.insert(0, str(Path(__file__).parent))

from src.llm.client import LLMClient
from src.agents import (
    RequirementAnalyzerAgent,
    TaskDecomposerAgent,
    ArchitectAgent,
    CodeGeneratorAgent,
    TestGeneratorAgent,
    ValidatorAgent,
)
from src.orchestrator.workflow_engine import WorkflowEngine
from src.tools.file_writer import FileWriter
from src.tools.code_validator import CodeValidator
from src.tools.report_generator import generate_html_report
from src.models.schemas import (
    EngineeringSummary, AnalyzedRequirement, ArchitectureDesign,
    TestSuite, ValidationReport, TaskGraph as TaskGraphModel,
)

app = Flask(__name__)

# Store pipeline status for real-time updates
pipeline_status = {
    "running": False,
    "phase": "",
    "progress": 0,
    "messages": [],
    "result_path": None,
    "error": None,
}


def make_output_dir(requirement_text: str) -> Path:
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', requirement_text.lower().strip())[:50].strip('-')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("output") / f"{timestamp}_{slug}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def run_pipeline_background(requirement_text: str):
    """Run the pipeline in a background thread."""
    global pipeline_status
    pipeline_status = {
        "running": True, "phase": "Initializing", "progress": 0,
        "messages": [], "result_path": None, "error": None,
    }

    output_dir = make_output_dir(requirement_text)
    start_time = time.time()

    def log(msg):
        pipeline_status["messages"].append(msg)

    try:
        # Init LLM
        pipeline_status["phase"] = "Connecting to Claude API..."
        pipeline_status["progress"] = 5
        llm = LLMClient(default_model="claude-sonnet-4-6")
        log("✓ LLM client initialized")

        # Phase 1
        pipeline_status["phase"] = "Phase 1: Analyzing Requirement..."
        pipeline_status["progress"] = 10
        analyzer = RequirementAnalyzerAgent(llm_client=llm)
        result = analyzer.run({"raw_text": requirement_text, "context": "Production deployment"})
        analyzed_req = result["analyzed_requirement"]
        log(f"✓ Requirement analyzed: {analyzed_req.requirement_type.value}")
        log(f"  Intent: {analyzed_req.intent[:100]}")

        # Phase 2
        pipeline_status["phase"] = "Phase 2: Decomposing Tasks..."
        pipeline_status["progress"] = 25
        decomposer = TaskDecomposerAgent(llm_client=llm)
        decomp = decomposer.run({"analyzed_requirement": analyzed_req})
        task_graph_model = decomp["task_graph"]
        log(f"✓ {len(task_graph_model.tasks)} tasks in {len(task_graph_model.execution_order)} layers")

        # Phase 3
        pipeline_status["phase"] = "Phase 3: Designing Architecture..."
        pipeline_status["progress"] = 40
        agents = {
            "architect": ArchitectAgent(llm_client=llm),
            "code_generator": CodeGeneratorAgent(llm_client=llm),
            "test_generator": TestGeneratorAgent(llm_client=llm),
            "validator": ValidatorAgent(llm_client=llm),
        }

        # Run agents directly for reliability
        outputs = {"analyzed_requirement": analyzed_req.model_dump(), "requirement": analyzed_req.model_dump()}

        arch_result = agents["architect"].run(outputs)
        outputs.update(arch_result)
        architecture = outputs.get("architecture")
        if architecture:
            log(f"✓ Architecture: {architecture.system_name} ({len(architecture.components)} components)")
        pipeline_status["progress"] = 55

        pipeline_status["phase"] = "Phase 4: Generating Code..."
        pipeline_status["progress"] = 60
        code_result = agents["code_generator"].run(outputs)
        outputs.update(code_result)
        code_artifacts = outputs.get("code_artifacts", [])
        log(f"✓ Generated {len(code_artifacts)} code files")
        pipeline_status["progress"] = 75

        pipeline_status["phase"] = "Phase 5: Generating Tests..."
        pipeline_status["progress"] = 80
        try:
            test_result = agents["test_generator"].run(outputs)
            outputs.update(test_result)
        except Exception as e:
            log(f"⚠ Test generator failed: {e}, retrying...")
            try:
                test_result = agents["test_generator"].run(outputs)
                outputs.update(test_result)
            except Exception:
                log("⚠ Test generation skipped")
        test_suite = outputs.get("test_suite")
        if test_suite:
            log(f"✓ Generated {len(test_suite.test_cases)} test cases")
        pipeline_status["progress"] = 90

        pipeline_status["phase"] = "Phase 6: Validating & Assessing Risks..."
        pipeline_status["progress"] = 92
        try:
            val_result = agents["validator"].run(outputs)
            outputs.update(val_result)
        except Exception as e:
            log(f"⚠ Validator failed: {e}, retrying...")
            try:
                val_result = agents["validator"].run(outputs)
                outputs.update(val_result)
            except Exception:
                log("⚠ Validation skipped")
        validation_report = outputs.get("validation_report")
        if validation_report:
            log(f"✓ {len(validation_report.risks)} risks, {len(validation_report.trade_offs)} trade-offs")

        # Build summary
        pipeline_status["phase"] = "Generating Report..."
        pipeline_status["progress"] = 95

        if isinstance(architecture, dict):
            architecture = ArchitectureDesign(**architecture)
        if isinstance(test_suite, dict):
            test_suite = TestSuite(**test_suite)
        if isinstance(validation_report, dict):
            validation_report = ValidationReport(**validation_report)

        # Write code files
        if code_artifacts:
            writer = FileWriter(output_dir=str(output_dir / "code"))
            writer.write_all(code_artifacts)

        summary = EngineeringSummary(
            requirement=analyzed_req,
            architecture=architecture if architecture else ArchitectureDesign(),
            task_graph=task_graph_model,
            code_artifacts=code_artifacts or [],
            test_suite=test_suite if test_suite else TestSuite(),
            validation=validation_report if validation_report else ValidationReport(is_valid=True),
            implementation_rationale=(
                f"System designed based on {len(analyzed_req.functional_requirements)} functional requirements."
            ),
            assumptions_and_limitations=analyzed_req.assumptions,
        )

        # Save JSON
        (output_dir / "engineering_summary.json").write_text(
            summary.model_dump_json(indent=2), encoding="utf-8"
        )

        # Generate HTML report
        report_path = generate_html_report(summary, str(output_dir / "report.html"))

        elapsed = time.time() - start_time
        log(f"✓ Done in {elapsed:.1f}s | Cost: {llm.get_usage_report()}")

        pipeline_status["progress"] = 100
        pipeline_status["phase"] = "Complete!"
        pipeline_status["result_path"] = str(output_dir / "report.html")

    except Exception as e:
        pipeline_status["error"] = str(e)
        pipeline_status["phase"] = f"Error: {e}"
        log(f"✗ Failed: {e}")

    pipeline_status["running"] = False


# --- Routes ---

@app.route("/")
def index():
    """Main page with input form."""
    # List previous runs
    output_dir = Path("output")
    previous_runs = []
    if output_dir.exists():
        for d in sorted(output_dir.iterdir(), reverse=True):
            if d.is_dir() and (d / "report.html").exists():
                previous_runs.append({
                    "name": d.name,
                    "path": f"/report/{d.name}",
                })
    return render_template_string(INDEX_HTML, previous_runs=previous_runs)


@app.route("/run", methods=["POST"])
def run():
    """Start the pipeline with the given requirement."""
    requirement = request.form.get("requirement", "").strip()
    if not requirement:
        return redirect("/")

    if pipeline_status["running"]:
        return jsonify({"error": "Pipeline already running"}), 409

    # Start in background thread
    thread = threading.Thread(target=run_pipeline_background, args=(requirement,))
    thread.daemon = True
    thread.start()

    return redirect("/progress")


@app.route("/progress")
def progress_page():
    """Show pipeline progress."""
    return render_template_string(PROGRESS_HTML)


@app.route("/status")
def status():
    """API endpoint for pipeline status (polled by progress page)."""
    return jsonify(pipeline_status)


@app.route("/report/<path:dirname>")
def serve_report(dirname):
    """Serve a generated report."""
    report_dir = Path("output") / dirname
    if (report_dir / "report.html").exists():
        return send_from_directory(str(report_dir), "report.html")
    return "Report not found", 404


@app.route("/output/<path:filepath>")
def serve_output(filepath):
    """Serve files from output directory."""
    return send_from_directory("output", filepath)


# --- HTML Templates ---

INDEX_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Agentic SDLC System</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 2rem; }
  .container { max-width: 700px; width: 100%; }
  h1 { font-size: 2.5rem; text-align: center; margin-bottom: 0.5rem; background: linear-gradient(135deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .subtitle { text-align: center; color: #94a3b8; margin-bottom: 2rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 2rem; margin-bottom: 1.5rem; border: 1px solid #334155; }
  textarea { width: 100%; padding: 1rem; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #e2e8f0; font-size: 1rem; resize: vertical; min-height: 100px; font-family: inherit; }
  textarea:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.2); }
  .btn { display: block; width: 100%; padding: 1rem; border: none; border-radius: 8px; font-size: 1.1rem; font-weight: 600; cursor: pointer; margin-top: 1rem; transition: all 0.2s; }
  .btn-primary { background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; }
  .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(59,130,246,0.4); }
  .examples { margin-top: 1rem; }
  .examples h3 { color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 0.5rem; }
  .example-btn { display: block; width: 100%; text-align: left; padding: 0.75rem 1rem; background: #0f172a; border: 1px solid #334155; border-radius: 6px; color: #cbd5e1; cursor: pointer; margin-bottom: 0.5rem; font-size: 0.9rem; transition: border-color 0.2s; }
  .example-btn:hover { border-color: #3b82f6; color: #f1f5f9; }
  .history { margin-top: 2rem; }
  .history h3 { color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 0.75rem; }
  .history a { display: block; padding: 0.6rem 1rem; color: #93c5fd; text-decoration: none; border-radius: 6px; margin-bottom: 0.25rem; font-size: 0.88rem; }
  .history a:hover { background: #1e293b; }
</style>
</head><body>
<div class="container">
  <h1>🏗️ Agentic SDLC</h1>
  <p class="subtitle">Transform any requirement into production-ready engineering output</p>

  <div class="card">
    <form action="/run" method="POST">
      <textarea name="requirement" placeholder="Enter your software requirement here...&#10;&#10;Example: Build a scalable URL shortener service with APIs, persistence, and analytics." rows="4"></textarea>
      <button type="submit" class="btn btn-primary">🚀 Generate Engineering Output</button>
    </form>

    <div class="examples">
      <h3>Quick Examples</h3>
      <button class="example-btn" onclick="document.querySelector('textarea').value=this.textContent">Build a scalable URL shortener service with APIs, persistence, and analytics.</button>
      <button class="example-btn" onclick="document.querySelector('textarea').value=this.textContent">Create a secure CI/CD pipeline with automated testing and deployment gates</button>
      <button class="example-btn" onclick="document.querySelector('textarea').value=this.textContent">Build a real-time notification service with WebSocket support and message persistence</button>
      <button class="example-btn" onclick="document.querySelector('textarea').value=this.textContent">Implement an LRU cache with distributed invalidation for microservices</button>
    </div>
  </div>

  {% if previous_runs %}
  <div class="history">
    <h3>📂 Previous Runs</h3>
    {% for run in previous_runs %}
    <a href="{{ run.path }}">📄 {{ run.name }}</a>
    {% endfor %}
  </div>
  {% endif %}
</div>
</body></html>"""


PROGRESS_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Pipeline Running...</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 2rem; }
  .container { max-width: 600px; width: 100%; }
  h2 { text-align: center; margin-bottom: 1.5rem; color: #93c5fd; }
  .progress-bar { width: 100%; height: 8px; background: #334155; border-radius: 4px; overflow: hidden; margin-bottom: 1rem; }
  .progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); transition: width 0.5s ease; border-radius: 4px; }
  .phase { text-align: center; color: #94a3b8; margin-bottom: 1.5rem; font-size: 1.1rem; }
  .log { background: #1e293b; border-radius: 8px; padding: 1rem; max-height: 300px; overflow-y: auto; border: 1px solid #334155; }
  .log-line { padding: 0.3rem 0; font-size: 0.85rem; color: #cbd5e1; font-family: monospace; }
  .log-line.success { color: #4ade80; }
  .log-line.error { color: #f87171; }
  .result-link { display: block; text-align: center; margin-top: 1.5rem; padding: 1rem; background: linear-gradient(135deg, #059669, #10b981); color: white; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 1.1rem; }
  .result-link:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(16,185,129,0.4); }
  .back-link { display: block; text-align: center; margin-top: 1rem; color: #94a3b8; text-decoration: none; }
</style>
</head><body>
<div class="container">
  <h2 id="title">⚙️ Pipeline Running...</h2>
  <div class="progress-bar"><div class="progress-fill" id="progress" style="width: 0%"></div></div>
  <div class="phase" id="phase">Initializing...</div>
  <div class="log" id="log"></div>
  <div id="result"></div>
  <a href="/" class="back-link">← Back to home</a>
</div>
<script>
function poll() {
  fetch('/status').then(r => r.json()).then(data => {
    document.getElementById('progress').style.width = data.progress + '%';
    document.getElementById('phase').textContent = data.phase;

    const log = document.getElementById('log');
    log.innerHTML = data.messages.map(m => {
      let cls = m.startsWith('✓') ? 'success' : m.startsWith('✗') ? 'error' : '';
      return `<div class="log-line ${cls}">${m}</div>`;
    }).join('');
    log.scrollTop = log.scrollHeight;

    if (data.result_path && !data.running) {
      document.getElementById('title').textContent = '✅ Pipeline Complete!';
      const parts = data.result_path.replace(/\\\\/g, '/').split('/');
      const dirName = parts[parts.length - 2];
      document.getElementById('result').innerHTML =
        `<a href="/report/${dirName}" class="result-link" target="_blank">📄 Open Engineering Report</a>`;
    } else if (data.error && !data.running) {
      document.getElementById('title').textContent = '❌ Pipeline Failed';
    }

    if (data.running) {
      setTimeout(poll, 1500);
    }
  });
}
poll();
</script>
</body></html>"""


# --- Entry Point ---

if __name__ == "__main__":
    print("\\n  🏗️  Agentic SDLC System - Web UI")
    print("  ─────────────────────────────────")
    print("  Opening http://localhost:5000 in your browser...\\n")

    # Open browser automatically
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()

    app.run(host="0.0.0.0", port=5000, debug=False)
