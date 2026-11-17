"""Graph community detection and hierarchical cluster analysis."""

import logging

import networkx as nx
from networkx.algorithms import community

logger = logging.getLogger(__name__)


class CommunityDetector:
    """Discovers tightly coupled entity communities within the knowledge graph."""

    def detect_communities(self, graph: nx.DiGraph) -> list[list[str]]:
        """Detect entity clusters using greedy modularity maximization on undirected view."""
        if len(graph.nodes) < 3:
            return [list(graph.nodes)]

        undirected = graph.to_undirected()

        try:
            communities = community.greedy_modularity_communities(undirected)
            return [list(c) for c in communities]
        except Exception as e:
            logger.debug(
                "Greedy modularity failed, falling back to connected components: %s", str(e)
            )
            return [list(c) for c in nx.connected_components(undirected)]
