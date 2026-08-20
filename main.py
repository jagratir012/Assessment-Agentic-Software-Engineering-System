"""
Agentic SDLC System - Main Entry Point

Transforms any software requirement into a reviewable engineering outcome.
Produces: architecture, code, tests, validation report, and HTML report.

Usage:
    python main.py                                    # Default URL shortener
    python main.py -r "Your requirement here"         # Custom requirement
    python main.py -r "..." --interactive             # With human approval gates
"""

import argparse
import json
import logging
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel

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
from src.models.schemas import (
    EngineeringSummary,
    AnalyzedRequirement,
    ArchitectureDesign,
    TestSuite,
    ValidationReport,
    TaskGraph as TaskGraphModel,
)

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_REQUIREMENT = (
    "Build a scalable URL shortener service with APIs, persistence, and analytics."
)


def make_output_dir(requirement_text: str) -> Path:
    """Create a unique output directory based on the requirement text."""
    # Create a slug from the requirement
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', requirement_text.lower().strip())
    slug = slug[:50].strip('-')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{timestamp}_{slug}"

    output_dir = Path("output") / dir_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def run_pipeline(
    requirement_text: str,
    interactive: bool = False,
    api_key: str = None,
) -> None:
    """
    Execute the full agentic SDLC pipeline.
    Produces partial output even if a step fails.
    Each run gets its own output folder.
    """
    output_dir = make_output_dir(requirement_text)

    console.print(Panel(
        f"[bold]Agentic SDLC System[/bold]\n\n"
        f"Requirement: {requirement_text}\n"
        f"Output: {output_dir}",
        title="🚀 Pipeline Start",
        border_style="blue",
    ))

    # Initialize LLM client
    try:
        llm = LLMClient(api_key=api_key, default_model="claude-sonnet-4-6")
        console.print("  [green]✓[/green] LLM client initialized (Claude Sonnet 4)")
        console.print("  [dim]  Cache: different inputs → fresh API calls automatically[/dim]")
        console.print("  [dim]  Same input → uses cached response (free). Use --fresh to force new.[/dim]")
    except ValueError as e:
        console.print(f"  [bold red]✗ LLM Init Failed: {e}[/bold red]")
        console.print("  [yellow]Set ANTHROPIC_API_KEY in .env or pass --api-key[/yellow]")
        return

    # Track what we've produced (for partial output on failure)
    analyzed_req = None
    task_graph_model = None
    architecture = None
    code_artifacts = []
    test_suite = None
    validation_report = None
    errors = []
    pipeline_start = time.time()

    # --- Phase 1: Requirement Analysis ---
    console.print("\n[bold magenta]Phase 1: Requirement Analysis[/bold magenta]")
    phase_start = time.time()
    try:
        analyzer = RequirementAnalyzerAgent(llm_client=llm)
        analysis_result = analyzer.run({
            "raw_text": requirement_text,
            "context": "Production microservice deployment",
        })
        analyzed_req = analysis_result["analyzed_requirement"]

        console.print(f"  [green]✓[/green] Type: {analyzed_req.requirement_type.value}")
        console.print(f"  [green]✓[/green] Intent: {analyzed_req.intent}")
        console.print(f"  [green]✓[/green] Functional Reqs: {len(analyzed_req.functional_requirements)}")
        console.print(f"  [green]✓[/green] Ambiguities: {len(analyzed_req.ambiguities)}")

        if interactive and analyzed_req.ambiguities:
            console.print("\n[yellow]  Ambiguities:[/yellow]")
            for amb in analyzed_req.ambiguities:
                console.print(f"    • {amb}")
            console.print("\n[yellow]  Assumptions:[/yellow]")
            for a in analyzed_req.assumptions:
                console.print(f"    → {a}")
            input("\n  Press Enter to approve and continue...")

        console.print(f"  [dim]⏱ Phase 1: {time.time() - phase_start:.1f}s[/dim]")

    except Exception as e:
        errors.append(f"Phase 1 (Requirement Analysis): {e}")
        console.print(f"  [red]✗ Failed: {e}[/red]")
        _save_partial_output(output_dir, requirement_text, analyzed_req, task_graph_model,
                           architecture, code_artifacts, test_suite, validation_report, errors)
        return

    # --- Phase 2: Task Decomposition ---
    console.print("\n[bold magenta]Phase 2: Task Decomposition[/bold magenta]")
    phase_start = time.time()
    try:
        decomposer = TaskDecomposerAgent(llm_client=llm)
        decomp_result = decomposer.run({"analyzed_requirement": analyzed_req})
        task_graph_model = decomp_result["task_graph"]

        console.print(f"  [green]✓[/green] Tasks: {len(task_graph_model.tasks)}")
        console.print(f"  [green]✓[/green] Layers: {len(task_graph_model.execution_order)}")
        for i, layer in enumerate(task_graph_model.execution_order):
            task_names = [
                next((t.name for t in task_graph_model.tasks if t.id == tid), tid)
                for tid in layer
            ]
            console.print(f"    Layer {i+1}: {task_names}")

        if interactive:
            input("\n  Press Enter to approve task plan...")

        console.print(f"  [dim]⏱ Phase 2: {time.time() - phase_start:.1f}s[/dim]")

    except Exception as e:
        errors.append(f"Phase 2 (Task Decomposition): {e}")
        console.print(f"  [red]✗ Failed: {e}[/red]")
        console.print("  [yellow]Continuing with direct agent execution...[/yellow]")

    # --- Phase 3: Workflow Orchestration ---
    console.print("\n[bold magenta]Phase 3: Workflow Orchestration[/bold magenta]")
    phase_start = time.time()
    try:
        agents = {
            "architect": ArchitectAgent(llm_client=llm),
            "code_generator": CodeGeneratorAgent(llm_client=llm),
            "test_generator": TestGeneratorAgent(llm_client=llm),
            "validator": ValidatorAgent(llm_client=llm),
        }

        if task_graph_model and task_graph_model.tasks:
            # Use the orchestrator with the task graph
            engine = WorkflowEngine(agents)
            engine._context["analyzed_requirement"] = analyzed_req.model_dump()
            engine._context["requirement"] = analyzed_req.model_dump()
            workflow_outputs = engine.execute_workflow(task_graph_model)
        else:
            # Fallback: run agents directly if decomposition failed
            console.print("  [yellow]Running agents directly (no task graph)[/yellow]")
            workflow_outputs = _run_agents_directly(agents, analyzed_req)

        # Extract outputs
        architecture = workflow_outputs.get("architecture")
        code_artifacts = workflow_outputs.get("code_artifacts", [])
        test_suite = workflow_outputs.get("test_suite")
        validation_report = workflow_outputs.get("validation_report")

        console.print(f"  [dim]⏱ Phase 3: {time.time() - phase_start:.1f}s[/dim]")

    except Exception as e:
        errors.append(f"Phase 3 (Orchestration): {e}")
        console.print(f"  [red]✗ Orchestration error: {e}[/red]")
        console.print("  [yellow]Saving partial results...[/yellow]")

    # --- Phase 4: Output Generation ---
    console.print("\n[bold magenta]Phase 4: Output Generation[/bold magenta]")
    try:
        # Validate and write code artifacts
        if code_artifacts:
            validator_tool = CodeValidator()
            file_writer = FileWriter(output_dir=str(output_dir / "code"))

            validation_results = validator_tool.validate_all(code_artifacts)
            valid_count = sum(1 for r in validation_results if r["valid"])
            console.print(f"  [green]✓[/green] Code Validation: {valid_count}/{len(code_artifacts)} pass")

            written_paths = file_writer.write_all(code_artifacts)
            console.print(f"  [green]✓[/green] Files Written: {len(written_paths)}")
            for p in written_paths:
                console.print(f"    → {p}")
        else:
            console.print("  [yellow]⚠ No code artifacts generated[/yellow]")
    except Exception as e:
        errors.append(f"Phase 4 (Output Generation): {e}")
        console.print(f"  [red]✗ Output error: {e}[/red]")

    # --- Phase 5: Build Summary & Report ---
    console.print("\n[bold magenta]Phase 5: Engineering Summary & Report[/bold magenta]")
    try:
        # Normalize types
        if isinstance(architecture, dict):
            architecture = ArchitectureDesign(**architecture)
        if isinstance(test_suite, dict):
            test_suite = TestSuite(**test_suite)
        if isinstance(validation_report, dict):
            validation_report = ValidationReport(**validation_report)

        summary = EngineeringSummary(
            requirement=analyzed_req,
            architecture=architecture if architecture else ArchitectureDesign(
                system_name="Unknown", overview="Architecture generation failed"
            ),
            task_graph=task_graph_model if task_graph_model else TaskGraphModel(tasks=[], execution_order=[]),
            code_artifacts=code_artifacts if code_artifacts else [],
            test_suite=test_suite if test_suite else TestSuite(),
            validation=validation_report if validation_report else ValidationReport(is_valid=True),
            implementation_rationale=(
                f"System designed based on requirement analysis identifying "
                f"{len(analyzed_req.functional_requirements)} functional requirements. "
                f"Architecture uses {architecture.technology_stack if architecture else 'N/A'} "
                f"to balance performance, maintainability, and scalability."
            ),
            assumptions_and_limitations=analyzed_req.assumptions + [
                "Generated code is syntactically validated but not runtime-tested",
                "Integration tests require actual infrastructure to run",
            ],
        )

        # Save JSON
        json_path = output_dir / "engineering_summary.json"
        json_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"  [green]✓[/green] JSON: {json_path}")

        # Generate HTML report
        from src.tools.report_generator import generate_html_report
        report_path = generate_html_report(summary, str(output_dir / "report.html"))
        console.print(f"  [green]✓[/green] HTML Report: {report_path}")

    except Exception as e:
        errors.append(f"Phase 5 (Summary): {e}")
        console.print(f"  [red]✗ Summary error: {e}[/red]")
        # Still try to save what we have
        _save_partial_output(output_dir, requirement_text, analyzed_req, task_graph_model,
                           architecture, code_artifacts, test_suite, validation_report, errors)

    # --- Final Status ---
    total_time = time.time() - pipeline_start
    console.print("\n" + "=" * 60)
    if errors:
        console.print(f"[bold yellow]⚠ Pipeline completed with {len(errors)} error(s) in {total_time:.1f}s:[/bold yellow]")
        for err in errors:
            console.print(f"  [red]• {err}[/red]")
    else:
        console.print(f"[bold green]✓ Pipeline completed successfully in {total_time:.1f}s[/bold green]")

    console.print(f"\n[bold]📁 Output directory: {output_dir}[/bold]")
    console.print(f"  [dim]Open report.html in browser for a polished view[/dim]")

    # Cost report
    console.print(f"\n  [dim]💰 {llm.get_usage_report()}[/dim]")
    console.print(f"  [dim]⏱ Total execution time: {total_time:.1f}s[/dim]")


def _run_agents_directly(agents: dict, analyzed_req: AnalyzedRequirement) -> dict:
    """Fallback: run agents directly. Architect first, then code+test in parallel, then validator."""
    import concurrent.futures

    outputs = {"analyzed_requirement": analyzed_req.model_dump(), "requirement": analyzed_req.model_dump()}

    # Step 1: Architecture (required by others)
    console.print("  [yellow]▶[/yellow] Running architect...")
    try:
        arch_result = agents["architect"].run(outputs)
        outputs.update(arch_result)
        console.print("  [green]✓[/green] Architecture done")
    except Exception as e:
        console.print(f"  [red]✗[/red] Architect failed: {e}")

    # Step 2: Code + Tests in PARALLEL (they both depend on architecture, not each other)
    console.print("  [yellow]▶[/yellow] Running code_generator + test_generator in parallel...")

    def run_code():
        try:
            return agents["code_generator"].run(outputs)
        except Exception as e:
            logger.warning(f"Code generator failed: {e}")
            return {}

    def run_tests():
        try:
            return agents["test_generator"].run(outputs)
        except Exception as e:
            logger.warning(f"Test generator failed: {e}")
            return {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        code_future = executor.submit(run_code)
        test_future = executor.submit(run_tests)

        code_result = code_future.result()
        test_result = test_future.result()

    if code_result:
        outputs.update(code_result)
        console.print("  [green]✓[/green] Code generation done")
    if test_result:
        outputs.update(test_result)
        console.print("  [green]✓[/green] Test generation done")

    # Step 3: Validation (needs everything above)
    console.print("  [yellow]▶[/yellow] Running validator...")
    try:
        val_result = agents["validator"].run(outputs)
        outputs.update(val_result)
        console.print("  [green]✓[/green] Validation done")
    except Exception as e:
        console.print(f"  [red]✗[/red] Validator failed: {e}")

    return outputs


def _save_partial_output(
    output_dir: Path, requirement_text: str,
    analyzed_req, task_graph, architecture,
    code_artifacts, test_suite, validation_report, errors
):
    """Save whatever we have so far, even if the pipeline failed midway."""
    output_dir.mkdir(parents=True, exist_ok=True)

    partial = {
        "status": "partial_failure",
        "requirement": requirement_text,
        "errors": errors,
        "timestamp": datetime.now().isoformat(),
    }

    if analyzed_req:
        partial["analyzed_requirement"] = analyzed_req.model_dump()
    if task_graph:
        partial["task_graph"] = task_graph.model_dump()
    if architecture:
        if isinstance(architecture, dict):
            partial["architecture"] = architecture
        else:
            partial["architecture"] = architecture.model_dump()
    if code_artifacts:
        partial["code_artifacts_count"] = len(code_artifacts)
    if test_suite:
        if isinstance(test_suite, dict):
            partial["test_suite"] = test_suite
        else:
            partial["test_suite"] = test_suite.model_dump()

    partial_path = output_dir / "partial_output.json"
    partial_path.write_text(json.dumps(partial, indent=2, default=str), encoding="utf-8")
    console.print(f"  [yellow]Partial output saved: {partial_path}[/yellow]")


def _print_final_report(summary: EngineeringSummary) -> None:
    """Print brief final report to console."""
    if summary.architecture:
        console.print(f"\n[cyan]System:[/cyan] {summary.architecture.system_name}")
    console.print(f"[cyan]Code Files:[/cyan] {len(summary.code_artifacts)}")
    if summary.test_suite:
        console.print(f"[cyan]Tests:[/cyan] {len(summary.test_suite.test_cases)}")
    if summary.validation:
        console.print(f"[cyan]Risks:[/cyan] {len(summary.validation.risks)}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Agentic SDLC System - Transform requirements into engineering outcomes"
    )
    parser.add_argument(
        "--requirement", "-r",
        type=str,
        default=DEFAULT_REQUIREMENT,
        help="The requirement to process (any software requirement)",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode with human approval checkpoints",
    )
    parser.add_argument(
        "--api-key", "-k",
        type=str,
        default=None,
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        "--fresh", "-f",
        action="store_true",
        help="Clear cache before running (forces new API calls even for same requirement)",
    )

    args = parser.parse_args()

    try:
        # Clear cache if --fresh flag is used
        if args.fresh:
            cache_dir = Path(".cache")
            if cache_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    console.print("[yellow]Cache cleared (--fresh mode)[/yellow]\n")
                except Exception:
                    # On Windows, just delete the files inside
                    for f in cache_dir.glob("*.json"):
                        try:
                            f.unlink()
                        except Exception:
                            pass
                    console.print("[yellow]Cache files cleared (--fresh mode)[/yellow]\n")

        run_pipeline(
            args.requirement,
            interactive=args.interactive,
            api_key=args.api_key,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user.[/yellow]")
        return 1
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error: {e}[/bold red]")
        logger.exception("Unexpected pipeline failure")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
