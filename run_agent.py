"""
Run individual agents and update the existing output.

Usage:
    python run_agent.py architect                    # Run just the architect
    python run_agent.py code_generator              # Run just the code generator
    python run_agent.py test_generator              # Run just the test generator
    python run_agent.py validator                   # Run just the validator
    python run_agent.py all                         # Run all agents sequentially
    python run_agent.py architect --output DIR      # Specify which output dir to update

After running, it updates the engineering_summary.json and regenerates report.html.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from src.llm.client import LLMClient
from src.agents.architect_agent import ArchitectAgent
from src.agents.code_generator import CodeGeneratorAgent
from src.agents.test_generator import TestGeneratorAgent
from src.agents.validator_agent import ValidatorAgent
from src.models.schemas import (
    EngineeringSummary, AnalyzedRequirement, ArchitectureDesign,
    TestSuite, ValidationReport, CodeArtifact,
    TaskGraph as TaskGraphModel,
)
from src.tools.report_generator import generate_html_report
from src.tools.code_validator import CodeValidator
from src.tools.file_writer import FileWriter

console = Console()


def find_latest_output() -> Path:
    """Find the most recent output directory."""
    output_dir = Path("output")
    if not output_dir.exists():
        return None
    dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()], reverse=True)
    return dirs[0] if dirs else None


def load_summary(output_path: Path) -> dict:
    """Load existing engineering_summary.json."""
    json_file = output_path / "engineering_summary.json"
    if json_file.exists():
        return json.loads(json_file.read_text(encoding="utf-8"))
    return None


def save_summary(output_path: Path, data: dict):
    """Save updated engineering_summary.json and regenerate HTML report."""
    json_file = output_path / "engineering_summary.json"
    json_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    console.print(f"  [green]✓[/green] Updated: {json_file}")

    # Regenerate HTML report
    try:
        summary = EngineeringSummary(**data)
        report_path = generate_html_report(summary, str(output_path / "report.html"))
        console.print(f"  [green]✓[/green] Report updated: {report_path}")
    except Exception as e:
        console.print(f"  [red]✗[/red] Report generation failed: {e}")


def run_architect(llm: LLMClient, summary_data: dict, output_path: Path):
    """Run the architect agent and update the summary."""
    console.print("\n[bold cyan]Running Architect Agent...[/bold cyan]")
    start = time.time()

    agent = ArchitectAgent(llm_client=llm)
    inputs = {
        "analyzed_requirement": summary_data["requirement"],
        "requirement": summary_data["requirement"],
    }

    result = agent.run(inputs)
    arch = result.get("architecture")

    if arch:
        summary_data["architecture"] = arch.model_dump()
        console.print(f"  [green]✓[/green] Architecture: {arch.system_name}")
        console.print(f"  [green]✓[/green] Components: {len(arch.components)}")
        console.print(f"  [green]✓[/green] API Endpoints: {len(arch.api_endpoints)}")
        console.print(f"  [green]✓[/green] Data Models: {len(arch.data_models)}")
    else:
        console.print("  [red]✗[/red] No architecture produced")

    console.print(f"  [dim]⏱ {time.time() - start:.1f}s[/dim]")
    save_summary(output_path, summary_data)


def run_code_generator(llm: LLMClient, summary_data: dict, output_path: Path):
    """Run the code generator agent and update the summary."""
    console.print("\n[bold cyan]Running Code Generator Agent...[/bold cyan]")
    start = time.time()

    agent = CodeGeneratorAgent(llm_client=llm)
    inputs = {
        "analyzed_requirement": summary_data["requirement"],
        "requirement": summary_data["requirement"],
        "architecture": summary_data.get("architecture"),
    }

    result = agent.run(inputs)
    artifacts = result.get("code_artifacts", [])

    if artifacts:
        summary_data["code_artifacts"] = [a.model_dump() for a in artifacts]

        # Validate and write code files
        validator = CodeValidator()
        validation_results = validator.validate_all(artifacts)
        valid = sum(1 for r in validation_results if r["valid"])
        console.print(f"  [green]✓[/green] Generated {len(artifacts)} files ({valid} valid)")

        writer = FileWriter(output_dir=str(output_path / "code"))
        writer.write_all(artifacts)
        console.print(f"  [green]✓[/green] Code written to {output_path / 'code'}")

        for art in artifacts:
            console.print(f"    • {art.filepath} ({art.language})")
    else:
        console.print("  [red]✗[/red] No code artifacts produced")

    console.print(f"  [dim]⏱ {time.time() - start:.1f}s[/dim]")
    save_summary(output_path, summary_data)


def run_test_generator(llm: LLMClient, summary_data: dict, output_path: Path):
    """Run the test generator agent and update the summary."""
    console.print("\n[bold cyan]Running Test Generator Agent...[/bold cyan]")
    start = time.time()

    agent = TestGeneratorAgent(llm_client=llm)
    inputs = {
        "analyzed_requirement": summary_data["requirement"],
        "requirement": summary_data["requirement"],
        "architecture": summary_data.get("architecture"),
        "code_artifacts": summary_data.get("code_artifacts", []),
    }

    result = agent.run(inputs)
    test_suite = result.get("test_suite")

    if test_suite:
        summary_data["test_suite"] = test_suite.model_dump()
        unit = sum(1 for t in test_suite.test_cases if t.test_type == "unit")
        integ = sum(1 for t in test_suite.test_cases if t.test_type == "integration")
        console.print(f"  [green]✓[/green] Tests: {len(test_suite.test_cases)} (unit: {unit}, integration: {integ})")
    else:
        console.print("  [red]✗[/red] No test suite produced")

    console.print(f"  [dim]⏱ {time.time() - start:.1f}s[/dim]")
    save_summary(output_path, summary_data)


def run_validator(llm: LLMClient, summary_data: dict, output_path: Path):
    """Run the validator agent and update the summary."""
    console.print("\n[bold cyan]Running Validator Agent...[/bold cyan]")
    start = time.time()

    agent = ValidatorAgent(llm_client=llm)
    inputs = {
        "analyzed_requirement": summary_data["requirement"],
        "requirement": summary_data["requirement"],
        "architecture": summary_data.get("architecture"),
        "code_artifacts": summary_data.get("code_artifacts", []),
        "test_suite": summary_data.get("test_suite"),
    }

    result = agent.run(inputs)
    report = result.get("validation_report")

    if report:
        summary_data["validation"] = report.model_dump()
        console.print(f"  [green]✓[/green] Risks: {len(report.risks)}")
        console.print(f"  [green]✓[/green] Trade-offs: {len(report.trade_offs)}")
        console.print(f"  [green]✓[/green] Guardrails: {len(report.guardrails)}")
    else:
        console.print("  [red]✗[/red] No validation report produced")

    console.print(f"  [dim]⏱ {time.time() - start:.1f}s[/dim]")
    save_summary(output_path, summary_data)


def main():
    parser = argparse.ArgumentParser(description="Run individual agents")
    parser.add_argument(
        "agent",
        choices=["architect", "code_generator", "test_generator", "validator", "all"],
        help="Which agent to run",
    )
    parser.add_argument("--output", "-o", type=str, default=None, help="Output directory to update")

    args = parser.parse_args()

    # Find output directory
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = find_latest_output()

    if not output_path or not output_path.exists():
        console.print("[red]No output directory found. Run 'python main.py' first.[/red]")
        return 1

    # Load existing summary
    summary_data = load_summary(output_path)
    if not summary_data:
        console.print(f"[red]No engineering_summary.json in {output_path}[/red]")
        return 1

    console.print(f"[bold]Using output: {output_path}[/bold]")
    console.print(f"[bold]Requirement: {summary_data['requirement']['original_text']}[/bold]\n")

    # Initialize LLM
    llm = LLMClient(default_model="claude-sonnet-4-6")

    # Run requested agent(s)
    agent_map = {
        "architect": run_architect,
        "code_generator": run_code_generator,
        "test_generator": run_test_generator,
        "validator": run_validator,
    }

    if args.agent == "all":
        for name, func in agent_map.items():
            func(llm, summary_data, output_path)
    else:
        agent_map[args.agent](llm, summary_data, output_path)

    console.print(f"\n[bold green]Done! Open {output_path / 'report.html'} in browser.[/bold green]")
    console.print(f"[dim]💰 {llm.get_usage_report()}[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
