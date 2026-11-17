"""Interactive standalone HTML exporter with dark mode and Mermaid diagram rendering."""

from pathlib import Path

from src.config import settings
from src.security.sanitizer import escape_html_entities
from src.state.schemas import ResearchReport


class HTMLExporter:
    """Exports interactive, styled standalone HTML dossiers."""

    def export(self, report: ResearchReport, output_dir: Path | None = None) -> Path:
        """Render report into a self-contained HTML file."""
        target_dir = output_dir or settings.reports_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        sanitized_topic = "".join(c if c.isalnum() else "_" for c in report.topic)[:50]
        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
        file_path = target_dir / f"research_{timestamp}_{sanitized_topic}.html"

        content = (
            report.chapters[0]["content_markdown"] if report.chapters else report.executive_summary
        )
        escaped_md = content.replace("`", "\\`").replace("$", "\\$")

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape_html_entities(report.title)}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    :root {{
      --bg-color: #0f172a;
      --card-bg: #1e293b;
      --text-color: #e2e8f0;
      --accent-color: #38bdf8;
      --border-color: #334155;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg-color);
      color: var(--text-color);
      line-height: 1.6;
      margin: 0;
      padding: 2rem;
    }}
    .container {{
      max-width: 900px;
      margin: 0 auto;
      background: var(--card-bg);
      padding: 3rem;
      border-radius: 12px;
      border: 1px solid var(--border-color);
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }}
    h1, h2, h3 {{ color: var(--accent-color); }}
    a {{ color: #60a5fa; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    pre, code {{
      background: #090d16;
      border-radius: 6px;
      padding: 0.2rem 0.4rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
    pre code {{ display: block; padding: 1rem; overflow-x: auto; }}
    blockquote {{
      border-left: 4px solid var(--accent-color);
      margin: 1.5rem 0;
      padding: 0.5rem 1rem;
      background: rgba(56, 189, 248, 0.05);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1.5rem 0;
    }}
    th, td {{
      padding: 0.75rem;
      border: 1px solid var(--border-color);
      text-align: left;
    }}
    th {{ background: #0f172a; color: var(--accent-color); }}
    .meta-badge {{
      display: inline-block;
      background: rgba(56, 189, 248, 0.1);
      color: var(--accent-color);
      padding: 0.3rem 0.8rem;
      border-radius: 9999px;
      font-size: 0.85rem;
      margin-bottom: 1.5rem;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="meta-badge">OpenDeepResearcher Dossier • Model: {escape_html_entities(report.model_used)}</div>
    <div id="content"></div>
  </div>

  <script>
    mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
    const rawMarkdown = `{escaped_md}`;
    document.getElementById('content').innerHTML = marked.parse(rawMarkdown);
  </script>
</body>
</html>"""

        file_path.write_text(html_template, encoding="utf-8")
        return file_path
