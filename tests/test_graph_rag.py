"""Comprehensive unit tests for KnowledgeGraphStore, multi-hop traversal, atomic persistence, and community detection."""

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

    # Multi-hop traversal (depth=2: toyota -> solid_state_battery -> silicon_anode)
    multi_hop = store.get_neighbors("toyota", depth=2)
    assert len(multi_hop) == 2
    targets = {n["target"] for n in multi_hop}
    assert "Solid-State Battery" in targets
    assert "Silicon Anode" in targets

    # Non-existent node query
    assert store.get_neighbors("unknown_entity") == []

    # Verify atomic disk persistence
    store.save_to_disk()
    assert save_path.exists()

    # Load in new store and verify parity
    new_store = KnowledgeGraphStore(persistence_path=save_path)
    assert len(new_store.graph.nodes) == 3
    assert len(new_store.graph.edges) == 2


def test_graph_store_duplicate_edge_accumulation() -> None:
    """Verify that adding the same edge repeatedly accumulates its weight."""
    store = KnowledgeGraphStore()
    edge1 = GraphEdge(source_id="node_a", target_id="node_b", relation_type="LINKS", weight=1.0)
    edge2 = GraphEdge(source_id="node_a", target_id="node_b", relation_type="LINKS", weight=2.5)

    store.add_edges([edge1])
    assert store.graph["node_a"]["node_b"]["weight"] == 1.0

    store.add_edges([edge2])
    # Weight should be 1.0 + 2.5 = 3.5
    assert store.graph["node_a"]["node_b"]["weight"] == 3.5


def test_graph_store_corrupted_disk_file(tmp_path: Path) -> None:
    """Verify graceful handling and clean fallback when graph file on disk is corrupted."""
    bad_file = tmp_path / "corrupted_graph.json"
    bad_file.write_text("{ not valid json content ???", encoding="utf-8")

    # Store must not crash; must log warning and initialize empty DiGraph
    store = KnowledgeGraphStore(persistence_path=bad_file)
    assert len(store.graph.nodes) == 0
    assert len(store.graph.edges) == 0


def test_community_detection_edge_cases() -> None:
    """Verify community clustering on empty graphs, small graphs (<3 nodes), and clusters."""
    detector = CommunityDetector()

    # 1. Empty graph
    empty_store = KnowledgeGraphStore()
    assert detector.detect_communities(empty_store.graph) == [[]]

    # 2. Small graph with 2 nodes
    small_store = KnowledgeGraphStore()
    small_store.add_nodes([GraphNode(id="n1", label="N1"), GraphNode(id="n2", label="N2")])
    assert len(detector.detect_communities(small_store.graph)) == 1

    # 3. Clustered graph
    clustered_store = KnowledgeGraphStore()
    nodes = [GraphNode(id=f"node_{i}", label=f"Node {i}") for i in range(6)]
    edges = [
        GraphEdge(source_id="node_0", target_id="node_1", relation_type="CONNECTS"),
        GraphEdge(source_id="node_1", target_id="node_2", relation_type="CONNECTS"),
        GraphEdge(source_id="node_3", target_id="node_4", relation_type="CONNECTS"),
        GraphEdge(source_id="node_4", target_id="node_5", relation_type="CONNECTS"),
    ]
    clustered_store.add_nodes(nodes)
    clustered_store.add_edges(edges)

    clusters = detector.detect_communities(clustered_store.graph)
    assert len(clusters) >= 2
