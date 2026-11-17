"""Knowledge Graph storage and atomic persistence using NetworkX."""

import json
import logging
from pathlib import Path

import networkx as nx

from src.config import settings
from src.state.schemas import GraphEdge, GraphNode

logger = logging.getLogger(__name__)


class KnowledgeGraphStore:
    """Manages the in-memory NetworkX directed graph with atomic disk persistence."""

    def __init__(self, persistence_path: Path | None = None) -> None:
        self.persist_path = persistence_path or settings.knowledge_graph_path
        self.graph = nx.DiGraph()
        self.load_from_disk()

    def add_nodes(self, nodes: list[GraphNode]) -> None:
        """Insert or update entity nodes in the graph."""
        for n in nodes:
            self.graph.add_node(
                n.id,
                label=n.label,
                entity_type=n.entity_type,
                **n.attributes,
            )

    def add_edges(self, edges: list[GraphEdge]) -> None:
        """Insert or update directed relationship edges."""
        for e in edges:
            if not self.graph.has_node(e.source_id):
                self.graph.add_node(e.source_id, label=e.source_id)
            if not self.graph.has_node(e.target_id):
                self.graph.add_node(e.target_id, label=e.target_id)

            # Accumulate weight if edge already exists
            weight = e.weight
            if self.graph.has_edge(e.source_id, e.target_id):
                weight += self.graph[e.source_id][e.target_id].get("weight", 1.0)

            self.graph.add_edge(
                e.source_id,
                e.target_id,
                relation=e.relation_type,
                weight=weight,
                confidence=e.confidence,
                source_doc_id=e.source_doc_id,
            )

    def get_neighbors(self, entity_id: str, depth: int = 1) -> list[dict[str, str]]:
        """Perform multi-hop graph walk to retrieve related entities and relationships."""
        normalized_id = entity_id.lower().replace(" ", "_")
        if not self.graph.has_node(normalized_id):
            return []

        related: list[dict[str, str]] = []
        visited = {normalized_id}
        current_layer = [normalized_id]

        for _ in range(depth):
            next_layer: list[str] = []
            for node in current_layer:
                for neighbor in self.graph.neighbors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_layer.append(neighbor)
                        edge_data = self.graph.get_edge_data(node, neighbor) or {}
                        relation = edge_data.get("relation", "CONNECTED_TO")
                        node_label = self.graph.nodes[node].get("label", node)
                        neighbor_label = self.graph.nodes[neighbor].get("label", neighbor)

                        related.append(
                            {
                                "source": node_label,
                                "relation": relation,
                                "target": neighbor_label,
                            }
                        )
            current_layer = next_layer

        return related

    def save_to_disk(self) -> None:
        """Atomically persist knowledge graph to JSON on disk."""
        data = nx.node_link_data(self.graph)
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.persist_path.with_suffix(".tmp")

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        temp_path.replace(self.persist_path)
        logger.info(
            "Saved knowledge graph to disk (%d nodes, %d edges)",
            len(self.graph.nodes),
            len(self.graph.edges),
        )

    def load_from_disk(self) -> None:
        """Load graph from JSON if file exists."""
        if self.persist_path.exists():
            try:
                with open(self.persist_path, encoding="utf-8") as f:
                    data = json.load(f)
                self.graph = nx.node_link_graph(data, directed=True)
                logger.info(
                    "Loaded knowledge graph from disk (%d nodes, %d edges)",
                    len(self.graph.nodes),
                    len(self.graph.edges),
                )
            except Exception as e:
                logger.warning(
                    "Failed to load knowledge graph from %s: %s", self.persist_path, str(e)
                )
                self.graph = nx.DiGraph()
