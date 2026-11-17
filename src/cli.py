"""Rich interactive terminal CLI for OpenDeepResearcher."""

import asyncio
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.agents.director import ResearchDirector
from src.config import settings
from src.exporters.audio_script import AudioScriptExporter
from src.exporters.html_export import HTMLExporter
from src.exporters.latex_export import LatexExporter
from src.exporters.markdown_export import MarkdownExporter
from src.state.schemas import ResearchState

app = typer.Typer(help="OpenDeepResearcher - Autonomous Deep Research CLI")
console = Console()


def cli_hitl_callback(title: str, prompt_text: str) -> bool:
    """Active Human-in-the-Loop prompt in terminal."""
    console.print(
        Panel(
            prompt_text,
            title=f"[bold yellow]HITL Alert: {title}[/bold yellow]",
            border_style="yellow",
        )
    )
    choice = typer.confirm("Do you wish to prioritize this direction?")
    return choice


@app.command()
def research(
    topic: str = typer.Argument(..., help="Research question or topic"),
    depth: int = typer.Option(2, "--depth", "-d", help="Recursion research depth (1-4)"),
    local: bool = typer.Option(
        False, "--local", "-l", help="Run 100% locally with Ollama ($0 budget)"
    ),
    unattended: bool = typer.Option(
        False, "--unattended", "-u", help="Run fully autonomously without interactive pauses"
    ),
) -> None:
    """Execute an autonomous deep research mission."""
    if local:
        settings.llm_provider = "ollama"

    console.print(
        Panel.fit(
            f"[bold cyan]OpenDeepResearcher[/bold cyan]\n"
            f"[dim]Topic:[/dim] [bold]{topic}[/bold]\n"
            f"[dim]Provider:[/dim] [green]{settings.llm_provider.upper()}[/green] | [dim]Depth:[/dim] {depth} | "
            f"[dim]Local Free Mode:[/dim] {'Yes' if settings.is_local_mode else 'No'}",
            title="🔬 Autonomous Research Mission",
            border_style="cyan",
        )
    )

    state = ResearchState(
        session_id=f"session_{abs(hash(topic))}",
        topic=topic,
        target_depth=depth,
    )

    director = ResearchDirector()

    async def _run() -> None:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task_id = progress.add_task(
                "[cyan]Initializing research graph & planning queries...", total=None
            )

            report = await director.run_research(
                state=state,
                hitl_callback=cli_hitl_callback if not unattended else None,
                unattended=unattended,
            )

            progress.update(
                task_id, description="[green]Synthesizing and formatting multi-format dossiers..."
            )

            # Export to all publication formats
            md_path = MarkdownExporter().export(report)
            html_path = HTMLExporter().export(report)
            tex_path, bib_path = LatexExporter().export(report)
            audio_path = AudioScriptExporter().export(report)

            state.report_paths = {
                "markdown": str(md_path),
                "html": str(html_path),
                "latex": str(tex_path),
                "bibtex": str(bib_path),
                "audio_script": str(audio_path),
            }

        # Print Research Summary Table
        table = Table(title="📑 Generated Research Dossiers", border_style="green")
        table.add_column("Format", style="cyan")
        table.add_column("Path", style="magenta")

        table.add_row("Markdown Report", str(md_path))
        table.add_row("Interactive HTML", str(html_path))
        table.add_row("Academic LaTeX", str(tex_path))
        table.add_row("BibTeX Citations", str(bib_path))
        table.add_row("Audio Briefing Script", str(audio_path))

        console.print(table)

        # Print Metric Badge
        console.print(
            Panel(
                f"[bold green]✓ Research Complete![/bold green]\n"
                f"• Sources Consulted: [bold]{len(state.collected_documents)}[/bold]\n"
                f"• Grounded Citations: [bold]{len(report.citations)}[/bold]\n"
                f"• Total Tokens Used: [bold]{state.total_tokens_used}[/bold]\n"
                f"• Estimated Cost: [bold]${state.estimated_cost_usd:.4f} USD[/bold]",
                border_style="green",
            )
        )

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("[bold red]Research interrupted by user.[/bold red]")
        sys.exit(130)


def main() -> None:
    """CLI entrypoint."""
    app()


if __name__ == "__main__":
    main()
