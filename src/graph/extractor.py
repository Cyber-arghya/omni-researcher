"""Entity and relation triple extractor for GraphRAG."""

import logging

from src.llm.client import LLMClient
from src.state.schemas import GraphEdge, GraphNode

logger = logging.getLogger(__name__)

GRAPH_EXTRACTION_PROMPT = """You are a Knowledge Graph Engineer.
Extract all prominent entities and semantic relationship triples from the provided research text.

Entity categories to identify:
- Technology, Organization, Person, Metric, Concept, Material, Benchmark

Output format MUST be strict JSON:
{
  "entities": [
    {"name": "string", "type": "string", "description": "brief description"}
  ],
  "relations": [
    {"source": "string", "target": "string", "relation": "UPPERCASE_VERB", "confidence": float (0.0 to 1.0)}
  ]
}
"""


class GraphExtractor:
    """Extracts structured entities and directed relation triples from text passages."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    async def extract_triples(
        self,
        text_chunk: str,
        doc_id: str = "",
        model_name: str = "llama3.2:latest",
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Extract entities and relation triples from a chunk."""
        if len(text_chunk.split()) < 30:
            return [], []

        messages = [
            {"role": "system", "content": GRAPH_EXTRACTION_PROMPT},
            {
                "role": "user",
                "content": f"Extract entities and relationships from this text:\n\n{text_chunk[:2500]}",
            },
        ]

        try:
            parsed, _, _ = await self.llm_client.chat_json(
                messages=messages,
                model=model_name,
                temperature=0.1,
            )

            nodes: list[GraphNode] = []
            edges: list[GraphEdge] = []

            for ent in parsed.get("entities", []):
                name = ent.get("name", "").strip()
                if name:
                    nodes.append(
                        GraphNode(
                            id=name.lower().replace(" ", "_"),
                            label=name,
                            entity_type=ent.get("type", "Concept"),
                            attributes={"description": ent.get("description", "")},
                        )
                    )

            for rel in parsed.get("relations", []):
                source = rel.get("source", "").strip()
                target = rel.get("target", "").strip()
                predicate = rel.get("relation", "RELATES_TO").strip().upper().replace(" ", "_")

                if source and target:
                    edges.append(
                        GraphEdge(
                            source_id=source.lower().replace(" ", "_"),
                            target_id=target.lower().replace(" ", "_"),
                            relation_type=predicate,
                            confidence=float(rel.get("confidence", 1.0)),
                            source_doc_id=doc_id,
                        )
                    )

            return nodes, edges

        except Exception as e:
            logger.debug("Graph triple extraction error: %s", str(e))
            return [], []
