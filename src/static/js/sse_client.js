/**
 * Resilient Server-Sent Events (SSE) Client for live multi-agent execution telemetry.
 */

class AgentSSEClient {
  constructor(sessionId, callbacks = {}) {
    this.sessionId = sessionId;
    this.callbacks = callbacks;
    this.eventSource = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  connect() {
    if (!this.sessionId) return;
    if (this.eventSource) {
      this.eventSource.close();
    }

    const url = `/api/events/${encodeURIComponent(this.sessionId)}`;
    this.eventSource = new EventSource(url);

    this.eventSource.onopen = () => {
      this.reconnectAttempts = 0;
      if (this.callbacks.onConnect) this.callbacks.onConnect();
    };

    this.eventSource.addEventListener("agent_status", (e) => {
      const data = JSON.parse(e.data);
      if (this.callbacks.onStatus) this.callbacks.onStatus(data);
    });

    this.eventSource.addEventListener("document_scraped", (e) => {
      const data = JSON.parse(e.data);
      if (this.callbacks.onDocument) this.callbacks.onDocument(data);
    });

    this.eventSource.addEventListener("graph_updated", (e) => {
      const data = JSON.parse(e.data);
      if (this.callbacks.onGraph) this.callbacks.onGraph(data);
    });

    this.eventSource.addEventListener("hardware_metrics", (e) => {
      const data = JSON.parse(e.data);
      if (this.callbacks.onHardware) this.callbacks.onHardware(data);
    });

    this.eventSource.addEventListener("hitl_required", (e) => {
      const data = JSON.parse(e.data);
      if (this.callbacks.onHITL) this.callbacks.onHITL(data);
    });

    this.eventSource.addEventListener("report_completed", (e) => {
      const data = JSON.parse(e.data);
      if (this.callbacks.onComplete) this.callbacks.onComplete(data);
      this.disconnect();
    });

    this.eventSource.onerror = (err) => {
      if (this.callbacks.onError) this.callbacks.onError(err);
      this.reconnectAttempts++;
      if (this.reconnectAttempts > this.maxReconnectAttempts) {
        this.disconnect();
      }
    };
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}

window.AgentSSEClient = AgentSSEClient;
