"""Multi-hop knowledge graph traversal and relational reasoning."""

from src.graph.community import CommunityDetector
from src.graph.graph_store import KnowledgeGraphStore


class GraphTraversalEngine:
    """Extracts relational reasoning paths and summaries across the knowledge graph."""

    def __init__(self, store: KnowledgeGraphStore | None = None) -> None:
        self.store = store or KnowledgeGraphStore()
        self.detector = CommunityDetector()

    def get_context_for_entity(self, entity_name: str, depth: int = 1) -> str:
        """Generate a concise textual representation of all relations involving an entity."""
        neighbors = self.store.get_neighbors(entity_name, depth=depth)
        if not neighbors:
            return ""

        lines = [
            f"- **{rel['source']}** {rel['relation']} **{rel['target']}**" for rel in neighbors
        ]
        return "\n".join(lines)

    def summarize_communities(self) -> list[str]:
        """Produce high-level community cluster outlines for global synthesis."""
        clusters = self.detector.detect_communities(self.store.graph)
        summaries: list[str] = []

        for idx, cluster in enumerate(clusters[:5]):  # top 5 largest communities
            if len(cluster) >= 2:
                labels = [self.store.graph.nodes[n].get("label", n) for n in cluster[:8]]
                summaries.append(
                    f"Cluster {idx + 1} ({len(cluster)} entities): {', '.join(labels)}"
                )

        return summaries
