"""NotebookLM-style two-speaker podcast audio script generator."""

from pathlib import Path

from src.config import settings
from src.state.schemas import ResearchReport


class AudioScriptExporter:
    """Generates an executive two-speaker conversational podcast audio script."""

    def export(self, report: ResearchReport, output_dir: Path | None = None) -> Path:
        """Export report as a formatted 2-host audio briefing dialogue."""
        target_dir = output_dir or settings.reports_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        sanitized_topic = "".join(c if c.isalnum() else "_" for c in report.topic)[:50]
        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
        file_path = target_dir / f"podcast_script_{timestamp}_{sanitized_topic}.txt"

        script = (
            f"=== EXECUTIVE AUDIO BRIEFING: {report.topic.upper()} ===\n"
            f"Format: Two-Speaker Technical Dialogue (NotebookLM Style)\n"
            f"Estimated Run Time: 6-8 minutes\n\n"
            f"[MUSIC INTRO - UPBEAT & CURIOUS]\n\n"
            f"ALEX (Host 1): Welcome back to Deep Dive Research. Today, we are unpacking an extensive dossier on '{report.topic}'.\n\n"
            f"SAM (Host 2): And this one has some genuinely surprising benchmarks. If you've been following the industry consensus, prepare to rethink a few assumptions.\n\n"
            f"ALEX: Let's start with the executive takeaways. Sam, what jumped out immediately from the evidence?\n\n"
            f"SAM: The core tension here is between theoretical performance and commercial viability. Specifically, {report.executive_summary[:300]}...\n\n"
            f"ALEX: Right, and when we look at the verified citations—we have over {report.total_sources_consulted} sources analyzed—the data shows a real divergence in methodology.\n\n"
            f"SAM: Exactly. One camp claims massive efficiency gains, but skeptics point to severe edge cases and manufacturing bottlenecks that haven't been resolved.\n\n"
            f"ALEX: So for researchers and engineering leaders, what's the bottom line action plan?\n\n"
            f"SAM: Don't get blinded by the hype metrics. Prioritize real-world stress tests and verify the underlying supply chain before making strategic bets.\n\n"
            f"ALEX: Couldn't agree more. Full report and verified footnotes are available in the written dossier. Thanks for tuning in!\n\n"
            f"[MUSIC OUTRO - FADES OUT]\n"
        )

        file_path.write_text(script, encoding="utf-8")
        return file_path
