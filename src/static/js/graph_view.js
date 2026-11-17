/**
 * Interactive Knowledge Graph (GraphRAG) visualizer using Vis-Network.
 */

class KnowledgeGraphView {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.network = null;
    this.nodes = new vis.DataSet([]);
    this.edges = new vis.DataSet([]);
    this.initNetwork();
  }

  initNetwork() {
    if (!this.container || typeof vis === "undefined") return;

    const data = { nodes: this.nodes, edges: this.edges };
    const options = {
      nodes: {
        shape: "dot",
        size: 16,
        font: { size: 12, color: "#f8fafc", face: "sans-serif" },
        borderWidth: 2,
        shadow: true,
      },
      edges: {
        width: 1.5,
        color: { color: "rgba(100, 116, 139, 0.6)", highlight: "#06b6d4" },
        arrows: { to: { enabled: true, scaleFactor: 0.6 } },
        font: { size: 9, color: "#94a3b8", align: "horizontal" },
        smooth: { type: "continuous" },
      },
      physics: {
        stabilization: { iterations: 100 },
        barnesHut: {
          gravitationalConstant: -2500,
          centralGravity: 0.3,
          springLength: 95,
          springConstant: 0.04,
          damping: 0.09,
        },
      },
      interaction: {
        hover: true,
        tooltipDelay: 150,
        zoomView: true,
      },
    };

    this.network = new vis.Network(this.container, data, options);

    this.network.on("click", (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const node = this.nodes.get(nodeId);
        window.dispatchEvent(new CustomEvent("graph:node_selected", { detail: node }));
      }
    });
  }

  updateGraph(nodesData, edgesData) {
    if (!this.network) return;

    const colorMap = {
      Technology: { background: "#0ea5e9", border: "#38bdf8" },
      Organization: { background: "#a855f7", border: "#c084fc" },
      Metric: { background: "#f59e0b", border: "#fbbf24" },
      Concept: { background: "#10b981", border: "#34d399" },
    };

    const formattedNodes = nodesData.map((n) => {
      const colors = colorMap[n.entity_type] || colorMap.Concept;
      return {
        id: n.id,
        label: n.label,
        title: `Type: ${n.entity_type}<br/>ID: ${n.id}`,
        color: colors,
      };
    });

    const formattedEdges = edgesData.map((e, idx) => ({
      id: `edge_${idx}_${e.source_id}_${e.target_id}`,
      from: e.source_id,
      to: e.target_id,
      label: e.relation_type,
    }));

    this.nodes.clear();
    this.edges.clear();
    this.nodes.add(formattedNodes);
    this.edges.add(formattedEdges);

    this.network.fit();
  }

  clear() {
    this.nodes.clear();
    this.edges.clear();
  }
}

window.KnowledgeGraphView = KnowledgeGraphView;

