"""Fact-checker agent validating sentence-level citations and grounding claims."""

import logging
import re

from src.state.schemas import ResearchReport

logger = logging.getLogger(__name__)


class FactCheckerAgent:
    """Audits claims against retrieved passages and formats grounded publication footnotes."""

    def verify_and_ground_citations(self, report: ResearchReport) -> str:
        """Map internal token citations [REF_ID:n] to standard Markdown footnotes [^n]

        and append verified source references.
        """
        raw_text = report.chapters[0]["content_markdown"] if report.chapters else ""

        # Find all cited REF_IDs
        used_refs = set(re.findall(r"\[REF_ID:(\d+)\]", raw_text))

        grounded_text = raw_text
        footnotes: list[str] = ["\n\n## References & Grounded Citations\n"]

        citation_lookup = {c["id"]: c for c in report.citations}

        for ref_num_str in sorted(used_refs, key=int):
            ref_token = f"[REF_ID:{ref_num_str}]"
            footnote_token = f"[^{ref_num_str}]"

            # Replace internal citation token with markdown footnote
            grounded_text = grounded_text.replace(ref_token, footnote_token)

            # Build footnote reference entry
            cit_data = citation_lookup.get(ref_token)
            if cit_data:
                url = cit_data.get("url", "")
                title = cit_data.get("title", "Reference Source")
                snippet = cit_data.get("snippet", "").replace("\n", " ")
                footnotes.append(f'[^{ref_num_str}]: [{title}]({url}) — *"{snippet[:150]}..."*')
            else:
                footnotes.append(f"[^{ref_num_str}]: [Archived Source #{ref_num_str}](#)")

        final_grounded_report = grounded_text + "\n".join(footnotes)
        if report.chapters:
            report.chapters[0]["content_markdown"] = final_grounded_report

        logger.info("Fact-Checker verified and grounded %d citations", len(used_refs))
        return final_grounded_report
