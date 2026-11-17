"""Academic LaTeX (.tex) and BibTeX (.bib) exporter for scholarly publications."""

import re
from pathlib import Path

from src.config import settings
from src.state.schemas import ResearchReport


class LatexExporter:
    """Generates publication-ready academic LaTeX documents with BibTeX bibliographies."""

    def export(self, report: ResearchReport, output_dir: Path | None = None) -> tuple[Path, Path]:
        """Export report to a paired .tex and .bib file."""
        target_dir = output_dir or settings.reports_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        sanitized_topic = "".join(c if c.isalnum() else "_" for c in report.topic)[:50]
        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")

        tex_path = target_dir / f"research_{timestamp}_{sanitized_topic}.tex"
        bib_path = target_dir / f"research_{timestamp}_{sanitized_topic}.bib"

        # 1. Export BibTeX file
        bib_content = (
            "\n\n".join(report.bibtex_entries) if report.bibtex_entries else "% No BibTeX entries"
        )
        bib_path.write_text(bib_content, encoding="utf-8")

        # 2. Convert Markdown text to LaTeX body
        body_text = (
            report.chapters[0]["content_markdown"] if report.chapters else report.executive_summary
        )
        latex_body = self._convert_markdown_to_latex(body_text)

        # 3. Assemble full academic article LaTeX template
        tex_template = (
            "\\documentclass[11pt,a4paper]{article}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage{geometry}\n"
            "\\geometry{margin=1in}\n"
            "\\usepackage{hyperref}\n"
            "\\usepackage{booktabs}\n"
            "\\usepackage{amsmath}\n\n"
            f"\\title{{{report.title}}}\n"
            "\\author{Autonomous Deep Research System (OpenDeepResearcher)}\n"
            f"\\date{{{report.generated_at.strftime('%B %d, %Y')}}}\n\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            "\\begin{abstract}\n"
            f"{self._escape_latex(report.executive_summary[:800])}...\n"
            "\\end{abstract}\n\n"
            f"{latex_body}\n\n"
            f"\\bibliography{{{bib_path.stem}}}\n"
            "\\bibliographystyle{plain}\n\n"
            "\\end{document}\n"
        )

        tex_path.write_text(tex_template, encoding="utf-8")
        return tex_path, bib_path

    def _convert_markdown_to_latex(self, text: str) -> str:
        """Heuristic conversion from Markdown syntax to LaTeX tags."""
        lines = text.split("\n")
        latex_lines: list[str] = []

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("# "):
                latex_lines.append(f"\\section{{{self._escape_latex(line_str[2:])}}}")
            elif line_str.startswith("## "):
                latex_lines.append(f"\\subsection{{{self._escape_latex(line_str[3:])}}}")
            elif line_str.startswith("### "):
                latex_lines.append(f"\\subsubsection{{{self._escape_latex(line_str[4:])}}}")
            elif line_str.startswith("- "):
                latex_lines.append(f"\\item {self._escape_latex(line_str[2:])}")
            else:
                # Map markdown footnotes [^n] to LaTeX citations \cite{refn}
                converted = re.sub(r"\[\^(\d+)\]", r"\\cite{ref\1}", line)
                latex_lines.append(self._escape_latex(converted))

        return "\n".join(latex_lines)

    def _escape_latex(self, s: str) -> str:
        """Escape standard LaTeX control characters."""
        chars = {
            "&": "\\&",
            "%": "\\%",
            "$": "\\$",
            "#": "\\#",
            "_": "\\_",
        }
        for char, replacement in chars.items():
            s = s.replace(char, replacement)
        return s
