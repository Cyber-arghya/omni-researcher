"""Lead Synthesizer agent authoring long-form publication-grade research reports."""

import logging

from src.graph.graph_traversal import GraphTraversalEngine
from src.llm.prompts import SYNTHESIZER_SYSTEM_PROMPT
from src.llm.router import ModelRouter
from src.rag.hybrid_retriever import HybridRetriever
from src.state.schemas import ResearchReport, ResearchState

logger = logging.getLogger(__name__)


class SynthesizerAgent:
    """Composes long-form analytical research dossiers with structured tables and grounded citations."""

    def __init__(
        self,
        router: ModelRouter | None = None,
        retriever: HybridRetriever | None = None,
        graph_engine: GraphTraversalEngine | None = None,
    ) -> None:
        self.router = router or ModelRouter()
        self.retriever = retriever or HybridRetriever()
        self.graph_engine = graph_engine or GraphTraversalEngine()

    async def synthesize_report(self, state: ResearchState) -> ResearchReport:
        """Compose the full research dossier from collected documents, RAG chunks, and Knowledge Graph."""
        logger.info("Initiating report synthesis for topic: %s", state.topic)

        # 1. Retrieve holistic top chunks across the topic using Hybrid RAG
        top_evidence = self.retriever.retrieve(state.topic, top_k=8)
        evidence_texts = [
            f"[REF_ID:{idx + 1}] (Source: {item['metadata'].get('url', 'Unknown')} - {item['metadata'].get('title', '')})\n{item['text']}\n"
            for idx, item in enumerate(top_evidence)
        ]

        # 2. Extract community clusters from Knowledge Graph
        graph_clusters = self.graph_engine.summarize_communities()
        graph_context = (
            "\n".join(graph_clusters) if graph_clusters else "No relational clusters identified."
        )

        user_prompt = (
            f"Research Topic: {state.topic}\n"
            f"User Constraints: {state.user_constraints or 'None'}\n\n"
            f"=== KNOWLEDGE GRAPH ENTITY COMMUNITIES ===\n"
            f"{graph_context}\n\n"
            f"=== RETRIEVED GROUNDED EVIDENCE PASSAGES ===\n"
            f"{''.join(evidence_texts)}\n\n"
            f"Write an exhaustive, high-density scientific analytical report adhering to the required chapter structure."
        )

        messages = [
            {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        raw_report_markdown = await self.router.run_deep(
            messages=messages,
            state=state,
            temperature=0.2,
            max_tokens=8192,
        )

        state.draft_report = raw_report_markdown

        # 3. Build Citation List
        citations_list = [
            {
                "id": f"[REF_ID:{idx + 1}]",
                "url": item["metadata"].get("url", ""),
                "snippet": item["text"][:250],
                "title": item["metadata"].get("title", "Untitled Source"),
            }
            for idx, item in enumerate(top_evidence)
        ]

        # Generate BibTeX entries
        bibtex_entries = [
            f"@misc{{ref{idx + 1},\n"
            f"  title = {{{item['metadata'].get('title', 'Unknown Title')}}},\n"
            f"  url = {{{item['metadata'].get('url', '')}}},\n"
            f"  note = {{Accessed via OpenDeepResearcher in 2026}}\n"
            f"}}"
            for idx, item in enumerate(top_evidence)
            if item["metadata"].get("url")
        ]

        report = ResearchReport(
            topic=state.topic,
            title=f"Autonomous Deep Research: {state.topic}",
            executive_summary=self._extract_executive_summary(raw_report_markdown),
            chapters=[
                {
                    "chapter_title": "Full Analytical Dossier",
                    "content_markdown": raw_report_markdown,
                }
            ],
            citations=citations_list,
            bibtex_entries=bibtex_entries,
            model_used=self.router.deep_model,
            total_sources_consulted=len(state.collected_documents),
        )

        state.final_report = report
        logger.info("Successfully synthesized research report (%d citations)", len(citations_list))
        return report

    def _extract_executive_summary(self, markdown: str) -> str:
        """Extract or default the executive summary portion."""
        lines = markdown.split("\n")
        summary_lines: list[str] = []
        capturing = False

        for line in lines:
            if "executive summary" in line.lower():
                capturing = True
                continue
            if capturing and line.startswith("#"):
                break
            if capturing:
                summary_lines.append(line)

        summary = "\n".join(summary_lines).strip()
        return summary if summary else markdown[:500] + "..."
