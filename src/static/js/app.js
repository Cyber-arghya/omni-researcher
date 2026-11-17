/**
 * Main Web UI Orchestrator and Cockpit State Controller.
 */

document.addEventListener("DOMContentLoaded", () => {
  // 1. Initialize Sub-controllers
  const graphView = new KnowledgeGraphView("graph-canvas");
  const hardwareCtrl = new HardwareController();
  const settingsCtrl = new SettingsController();
  hardwareCtrl.startPolling();

  let activeSessionId = null;
  let activeSSEClient = null;
  let timerInterval = null;
  let secondsElapsed = 0;
  let currentReportData = null;

  // DOM Elements
  const formResearch = document.getElementById("form-start-research");
  const inputTopic = document.getElementById("input-topic");
  const btnStart = document.getElementById("btn-start-research");
  const telemetryStatus = document.getElementById("telemetry-status");
  const telemetryElapsed = document.getElementById("telemetry-elapsed");
  const telemetryCost = document.getElementById("telemetry-cost");
  const telemetryTokens = document.getElementById("telemetry-tokens");
  const telemetryVRAM = document.getElementById("telemetry-vram");
  const hitlBanner = document.getElementById("hitl-banner");
  const hitlPrompt = document.getElementById("hitl-prompt");
  const dossierContainer = document.getElementById("dossier-container");
  const dossierContent = document.getElementById("dossier-content");
  const historyList = document.getElementById("history-list");
  const docFeed = document.getElementById("document-feed");

  // 2. Load Session History
  loadHistory();

  // 3. Form Submit Handler
  if (formResearch) {
    formResearch.addEventListener("submit", async (e) => {
      e.preventDefault();
      const topic = inputTopic.value.trim();
      if (!topic) return;

      const depth = parseInt(document.querySelector('input[name="depth"]:checked')?.value || "2");
      startResearchSession(topic, depth);
    });
  }

  async function startResearchSession(topic, depth) {
    btnStart.disabled = true;
    btnStart.innerText = "Initiating Mission...";
    resetExecutionUI();

    try {
      const resp = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, depth }),
      });

      if (!resp.ok) throw new Error("Failed to start research mission");
      const data = await resp.json();
      activeSessionId = data.session_id;

      // Start elapsed timer
      secondsElapsed = 0;
      clearInterval(timerInterval);
      timerInterval = setInterval(() => {
        secondsElapsed++;
        const mins = Math.floor(secondsElapsed / 60);
        const secs = secondsElapsed % 60;
        telemetryElapsed.innerText = `${mins}:${secs < 10 ? "0" : ""}${secs}`;
      }, 1000);

      // Connect SSE Telemetry
      connectSSE(activeSessionId);
      loadHistory();
    } catch (err) {
      alert("Error starting mission: " + err.message);
      btnStart.disabled = false;
      btnStart.innerText = "Start Deep Research";
    }
  }

  function connectSSE(sessionId) {
    activeSSEClient = new AgentSSEClient(sessionId, {
      onConnect: () => {
        telemetryStatus.innerText = "CONNECTED";
        telemetryStatus.className = "text-emerald-400 font-bold";
      },
      onStatus: (data) => {
        updateStageUI(data.stage, data.detail);
        if (data.tokens) telemetryTokens.innerText = data.tokens.toLocaleString();
        if (data.cost_usd !== undefined) telemetryCost.innerText = `$${data.cost_usd.toFixed(4)}`;
      },
      onDocument: (data) => {
        appendDocumentCard(data);
      },
      onGraph: (data) => {
        if (data.nodes && data.edges) {
          graphView.updateGraph(data.nodes, data.edges);
        }
      },
      onHardware: (data) => {
        if (telemetryVRAM) {
          telemetryVRAM.innerText = `${data.vram_used_gb?.toFixed(1) || 0}G / ${data.vram_total_gb?.toFixed(1) || 8}G`;
        }
      },
      onHITL: (data) => {
        showHITLBanner(data);
      },
      onComplete: (data) => {
        clearInterval(timerInterval);
        btnStart.disabled = false;
        btnStart.innerText = "Start Deep Research";
        telemetryStatus.innerText = "COMPLETED";
        telemetryStatus.className = "text-cyan-400 font-bold";
        renderFinalDossier(data);
        loadHistory();
      },
      onError: () => {
        telemetryStatus.innerText = "DISCONNECTED";
      },
    });

    activeSSEClient.connect();
  }

  function updateStageUI(stage, detail) {
    telemetryStatus.innerText = stage;
    const stages = ["PLANNING", "SEARCHING", "CRAWLING", "INDEXING", "CRITIQUING", "SYNTHESIZING"];
    stages.forEach((s) => {
      const card = document.getElementById(`stage-${s.toLowerCase()}`);
      if (!card) return;
      if (s === stage) {
        card.classList.add("agent-active-pulse");
        const statusSpan = card.querySelector(".stage-status");
        if (statusSpan) statusSpan.innerText = detail || "Executing...";
      } else if (stages.indexOf(s) < stages.indexOf(stage)) {
        card.classList.remove("agent-active-pulse");
        card.classList.add("border-emerald-600/50");
        const statusSpan = card.querySelector(".stage-status");
        if (statusSpan) statusSpan.innerText = "Completed";
      }
    });
  }

  function appendDocumentCard(doc) {
    if (!docFeed) return;
    const card = document.createElement("div");
    card.className = "p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-xs flex flex-col gap-1 transition hover:border-cyan-700/60";
    card.innerHTML = `
      <div class="font-semibold text-slate-200 truncate">${doc.title || "Web Document"}</div>
      <a href="${doc.url}" target="_blank" class="text-cyan-400 hover:underline truncate">${doc.url}</a>
      <div class="text-slate-400 text-[11px]">${doc.snippet || (doc.clean_text ? doc.clean_text.substring(0, 120) + "..." : "")}</div>
    `;
    docFeed.prepend(card);
  }

  function showHITLBanner(data) {
    if (!hitlBanner) return;
    hitlBanner.classList.remove("hidden");
    if (hitlPrompt) hitlPrompt.innerText = data.prompt || "The agent requests your feedback before proceeding.";

    document.getElementById("btn-hitl-approve").onclick = () => sendSteerAction("APPROVE");
    document.getElementById("btn-hitl-pivot").onclick = () => {
      const note = prompt("Enter steering guidance for the research agent:");
      if (note) sendSteerAction("PIVOT", note);
    };
    document.getElementById("btn-hitl-abort").onclick = () => sendSteerAction("ABORT");
  }

  async function sendSteerAction(action, feedback = "") {
    if (!activeSessionId) return;
    hitlBanner.classList.add("hidden");
    await fetch(`/api/sessions/${activeSessionId}/steer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, feedback }),
    });
  }

  function renderFinalDossier(data) {
    currentReportData = data;
    if (!dossierContainer) return;
    dossierContainer.classList.remove("hidden");

    const markdownText = data.markdown_content || data.final_report?.chapters?.[0]?.content_markdown || "";
    if (typeof marked !== "undefined") {
      dossierContent.innerHTML = marked.parse(markdownText);
    } else {
      dossierContent.innerText = markdownText;
    }

    // Scroll smoothly to dossier
    dossierContainer.scrollIntoView({ behavior: "smooth" });
  }

  // 4. Dossier Tab Controls
  document.querySelectorAll(".dossier-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".dossier-tab").forEach((t) => t.classList.remove("border-cyan-400", "text-cyan-400"));
      tab.classList.add("border-cyan-400", "text-cyan-400");
      const mode = tab.dataset.mode;
      if (!currentReportData) return;

      if (mode === "markdown") {
        dossierContent.innerHTML = marked.parse(currentReportData.markdown_content || "");
      } else if (mode === "latex") {
        dossierContent.innerHTML = `<pre class="text-xs font-mono text-cyan-300 p-4 bg-slate-950 rounded-lg overflow-x-auto"><code>${escapeHtml(currentReportData.latex_content || "% Academic LaTeX Output\n\\documentclass{article}...")}</code></pre>`;
      } else if (mode === "audio") {
        renderAudioPlayer(currentReportData.audio_script || "Host: Welcome to the deep research podcast...");
      }
    });
  });

  function renderAudioPlayer(script) {
    dossierContent.innerHTML = `
      <div class="p-6 rounded-lg bg-slate-900 border border-slate-800 flex flex-col gap-4">
        <h3 class="text-lg font-bold text-cyan-400">🎙️ NotebookLM-Style Audio Podcast</h3>
        <p class="text-xs text-slate-400">Client-side speech synthesis summarizing the core discoveries.</p>
        <div class="flex gap-3">
          <button id="btn-play-podcast" class="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 rounded-lg text-sm font-semibold text-slate-950">▶ Play Podcast</button>
          <button id="btn-stop-podcast" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm text-slate-200">⏹ Stop</button>
        </div>
        <div class="p-4 bg-slate-950 rounded text-xs text-slate-300 whitespace-pre-wrap max-h-60 overflow-y-auto">${escapeHtml(script)}</div>
      </div>
    `;

    document.getElementById("btn-play-podcast").onclick = () => {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(script);
      utterance.rate = 1.05;
      window.speechSynthesis.speak(utterance);
    };
    document.getElementById("btn-stop-podcast").onclick = () => {
      window.speechSynthesis.cancel();
    };
  }

  // 5. Download Dossier Handlers
  document.getElementById("btn-download-md")?.addEventListener("click", () => {
    if (!currentReportData) return;
    downloadFile("research_report.md", currentReportData.markdown_content || "");
  });

  document.getElementById("btn-download-tex")?.addEventListener("click", () => {
    if (!currentReportData) return;
    downloadFile("research_paper.tex", currentReportData.latex_content || "% LaTeX");
  });

  function downloadFile(filename, text) {
    const el = document.createElement("a");
    el.setAttribute("href", "data:text/plain;charset=utf-8," + encodeURIComponent(text));
    el.setAttribute("download", filename);
    el.style.display = "none";
    document.body.appendChild(el);
    el.click();
    document.body.removeChild(el);
  }

  async function loadHistory() {
    if (!historyList) return;
    try {
      const resp = await fetch("/api/history");
      if (!resp.ok) return;
      const items = await resp.json();

      historyList.innerHTML = "";
      items.forEach((item) => {
        const div = document.createElement("div");
        div.className = "p-2.5 rounded-lg text-xs hover:bg-slate-800/60 cursor-pointer flex justify-between items-center group transition";
        div.innerHTML = `
          <div class="truncate font-medium text-slate-300">${item.topic}</div>
          <span class="text-[10px] text-slate-500">${item.status}</span>
        `;
        div.onclick = () => loadPastSession(item.session_id);
        historyList.appendChild(div);
      });
    } catch (e) {
      console.warn("Could not load history:", e);
    }
  }

  async function loadPastSession(sessionId) {
    try {
      const resp = await fetch(`/api/sessions/${sessionId}`);
      if (!resp.ok) return;
      const data = await resp.json();
      activeSessionId = sessionId;
      inputTopic.value = data.topic;
      if (data.final_report) {
        renderFinalDossier({
          markdown_content: data.final_report.chapters?.[0]?.content_markdown || "",
          latex_content: data.final_report.bibtex_entries?.join("\n\n") || "",
        });
      }
      if (data.graph_nodes && data.graph_edges) {
        graphView.updateGraph(data.graph_nodes, data.graph_edges);
      }
    } catch (e) {
      console.error("Failed to load past session:", e);
    }
  }

  function resetExecutionUI() {
    if (docFeed) docFeed.innerHTML = "";
    if (dossierContainer) dossierContainer.classList.add("hidden");
    if (hitlBanner) hitlBanner.classList.add("hidden");
    graphView.clear();
    const stages = ["planning", "searching", "crawling", "indexing", "critiquing", "synthesizing"];
    stages.forEach((s) => {
      const card = document.getElementById(`stage-${s}`);
      if (card) {
        card.classList.remove("agent-active-pulse", "border-emerald-600/50");
        const statusSpan = card.querySelector(".stage-status");
        if (statusSpan) statusSpan.innerText = "Pending";
      }
    });
  }

  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
});
