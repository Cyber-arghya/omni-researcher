"""Unit tests for the KnowledgeGraphStore, NetworkX serialization, and community detection."""

from pathlib import Path

from src.graph.community import CommunityDetector
from src.graph.graph_store import KnowledgeGraphStore
from src.state.schemas import GraphEdge, GraphNode


def test_graph_store_nodes_and_edges(tmp_path: Path) -> None:
    """Verify entity node and edge additions, neighbor queries, and disk persistence."""
    save_path = tmp_path / "knowledge_graph.json"
    store = KnowledgeGraphStore(persistence_path=save_path)

    nodes = [
        GraphNode(id="solid_state_battery", label="Solid-State Battery", entity_type="Technology"),
        GraphNode(id="silicon_anode", label="Silicon Anode", entity_type="Material"),
        GraphNode(id="toyota", label="Toyota", entity_type="Organization"),
    ]
    edges = [
        GraphEdge(
            source_id="solid_state_battery", target_id="silicon_anode", relation_type="UTILIZES"
        ),
        GraphEdge(
            source_id="toyota", target_id="solid_state_battery", relation_type="COMMERCIALIZES"
        ),
    ]

    store.add_nodes(nodes)
    store.add_edges(edges)

    assert len(store.graph.nodes) == 3
    assert len(store.graph.edges) == 2

    # Verify neighbors traversal
    neighbors = store.get_neighbors("toyota", depth=1)
    assert len(neighbors) == 1
    assert neighbors[0]["relation"] == "COMMERCIALIZES"
    assert neighbors[0]["target"] == "Solid-State Battery"

    # Verify atomic disk persistence
    store.save_to_disk()
    assert save_path.exists()

    # Load in new store and verify parity
    new_store = KnowledgeGraphStore(persistence_path=save_path)
    assert len(new_store.graph.nodes) == 3
    assert len(new_store.graph.edges) == 2


def test_community_detection() -> None:
    """Verify community clustering algorithm."""
    store = KnowledgeGraphStore()
    nodes = [GraphNode(id=f"node_{i}", label=f"Node {i}") for i in range(5)]
    edges = [
        GraphEdge(source_id="node_0", target_id="node_1", relation_type="CONNECTS"),
        GraphEdge(source_id="node_1", target_id="node_2", relation_type="CONNECTS"),
        GraphEdge(source_id="node_3", target_id="node_4", relation_type="CONNECTS"),
    ]
    store.add_nodes(nodes)
    store.add_edges(edges)

    detector = CommunityDetector()
    clusters = detector.detect_communities(store.graph)
    assert len(clusters) >= 2
