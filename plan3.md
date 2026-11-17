# OpenDeepResearcher: Web UI/UX Architecture & Interactive Cockpit Plan (plan3.md)

## 1. 🛡️ The Brutal Truth Filter: UI/UX Architecture Scrutiny

Before writing any frontend code, we evaluate architectural options against KISS, DRY, Zero-Friction Installation, Portability, and Industry-Leading Standards.

| Architectural Choice | Trade-offs & Engineering Reality | Brutal Truth Verdict | Clean Engineered Solution |
|---|---|---|---|
| **Streamlit or Gradio** | **Clunky & Toy-Like.** Streamlit reruns the entire Python script on every widget state change, disrupting real-time token streaming and resetting dynamic GraphRAG visualizations. Gradio enforces rigid column wrappers with poor mobile ergonomics and clunky SSE lifecycle handling. | ❌ **REJECTED (Not for Flagship Production Apps)** | Build a dedicated, modern Single-Page Application (SPA) served directly by FastAPI. Zero Python rerun lag. |
| **Separate Next.js / React Monorepo with `node_modules`** | **Developer Friction & Bloat.** Requiring Node.js + npm/pnpm + 350MB of `node_modules` just to launch a Python agent UI ruins single-command installation (`uv run`) and doubles Docker build times. | ❌ **REJECTED (High Friction for Local Users)** | Deliver a zero-build, ultra-modern HTML5/ES6+ SPA with Tailwind CSS, Lucide icons, KaTeX, and Vis-Network served directly from FastAPI static assets (`src/static/`). |
| **WebSockets vs. Server-Sent Events (SSE)** | WebSockets require bidirectional keep-alive heartbeats, custom reconnect state logic, and frequently disconnect behind Docker bridges or corporate reverse proxies. Deep research execution is fundamentally a unidirectional stream of progress events from server to client. | ❌ **WebSockets REJECTED**<br/>✅ **SSE (Server-Sent Events) APPROVED** | Use `EventSource` (SSE) via `/api/events/{session_id}`. Includes native auto-reconnect, standard HTTP/2 multiplexing, and clean typed JSON event dispatch. |
| **Static Markdown vs. Dynamic Cockpit** | Showing only a final text dump wastes the power of multi-agent execution. Users want to see the research engine think in real time. | ✅ **APPROVED (Perplexity / STORM Parity)** | Build a live 4-phase visual execution cockpit: Planning -> Autonomous Crawling -> Knowledge Graph Construction -> Critic/Fact-Checking -> Final Dossier. |
| **Adaptive Hardware Awareness** | Hiding hardware constraints leads users to select models that cause out-of-memory crashes on 8GB laptops or underutilize 24GB+ workstations. | ✅ **APPROVED (Hardware Awareness)** | Embed a dynamic Hardware Telemetry Bar in the header showing live VRAM, System RAM, active tier, and recommended model filters. |

---

## 2. 🎨 UI/UX Component Architecture & Wireframe Layout

The OpenDeepResearcher Web UI follows a sleek, dark-mode-first aesthetic inspired by Linear, Perplexity Pro, and Cursor.

```
+-------------------------------------------------------------------------------------------------------------------+
| 🔬 OpenDeepResearcher   [🎮 Tier: entry_8gb | VRAM: 7.9G | RAM: 15.9G]   [🟢 NVIDIA NIM: Active]  [⚙️ Settings] [🌙] |
+-------------------+-------------------------------------------------------------------------+---------------------+
| 📚 PAST RESEARCH  | 🎯 MAIN RESEARCH WORKSPACE                                              | 🔍 LIVE TELEMETRY   |
|                   |                                                                         |                     |
| + New Mission     | [ Search or Research Question...                                     ]  | 📊 Status: INDEXING |
|                   | Depth: (•) Quick [1]   ( ) Deep [2]   ( ) Exhaustive [3]                | ⏱️ Elapsed: 24s     |
| 🕒 Solid-State    | Hardware Mode: [✓] Auto-Scaled (3 Crawlers, CPU Embeddings, Qwen-7B)    | 🪙 Cost: $0.00      |
|    Batteries 2026 | Sources:       [✓] Academic (arXiv/PubMed)  [✓] Vision  [✓] GraphRAG    | 🔤 Tokens: 18,450   |
|                   | [ 🚀 Start Deep Research ]                                              | 🧠 VRAM: 4.8G / 8.0G|
| 🕒 GLP-1          +-------------------------------------------------------------------------+---------------------+
|    Mechanisms     | ⚡ REAL-TIME MULTI-AGENT EXECUTION TIMELINE                             | 🕸️ KNOWLEDGE GRAPH |
|                   |                                                                         | [Interactive Mesh]  |
| 🕒 Quantum ML     | [✓] 🧭 Planner: Decomposed into 6 perspective search queries            |  (Solid Electrolyte)|
|    Benchmarks     | [✓] 🔎 Academic Harvest: 14 papers found (arXiv, Crossref)              |        | (DEVELOPS) |
|                   | [▶] 🕷️ Firecrawl: Scraping nature.com (Page 4 of 8)...                  |   (QuantumScape)    |
| 🗑️ Clear History  | [ ] 🕸️ GraphRAG: 42 entities discovered, 3 communities found            |                     |
|                   | [ ] ⚖️ Critic: Adversarial gap analysis                                 | 📄 SOURCES (14)     |
|                   | [ ] 📝 Synthesizer: Authoring Academic LaTeX & Markdown                 | 1. Nature Energy    |
|                   +-------------------------------------------------------------------------+ 2. arXiv:2401.123   |
|                   | 🤝 HUMAN-IN-THE-LOOP INTERACTION BANNER (Conditional)                   | 3. PubMed:123456    |
|                   | "Critic identified contradictory conductivity claims. Pivot?"           |                     |
|                   | [ 👍 Proceed as-is ]  [ ✏️ Steer Focus ]  [ 🛑 Abort ]                   | 📥 EXPORT DOSSIER   |
|                   +-------------------------------------------------------------------------+ [ Markdown ]        |
|                   | 📑 FINAL DOSSIER PREVIEW (Tabs: Markdown | LaTeX | HTML | Pod)          | [ LaTeX + BibTeX ]  |
|                   | # Comprehensive Analysis of Solid-State Electrolytes...                 | [ HTML Standalone ] |
|                   | [REF_ID:1] Sulfide conductors achieve >25 mS/cm [1]...                  | [ 🎙️ Podcast Audio] |
+-------------------+-------------------------------------------------------------------------+---------------------+
```

---

## 3. 🧩 Key User Interface Features & Capabilities

### Feature 1: The Research Launchpad
- **Natural Language Topic Input**: Multi-line auto-expanding textarea with smart autocomplete suggestions.
- **Depth Slider / Pills**:
  - `Level 1 - Fast Brief (1-2 mins)`: 1 search hop, 6 sources, rapid executive brief.
  - `Level 2 - Deep Dossier (3-5 mins)`: 2 search hops, 15+ sources, knowledge graph, critic refinement.
  - `Level 3 - Exhaustive Academic Review (8-12 mins)`: 3 search hops, multi-modal vision parsing, 30+ sources, LaTeX compilation.
- **Provider & Hardware Matrix Bar**:
  - Displays detected hardware tier: `entry_8gb` (Safe laptop), `enthusiast_16gb` (Turbo), `workstation_24gb_plus` (Max depth), or `cloud_hybrid`.
  - Quick-switch between Local Ollama, NVIDIA NIM (Nemotron-3 550B), and frontier cloud APIs.

### Feature 2: Real-Time Multi-Agent Cockpit (SSE Powered)
- **Live Visual Timeline**: Step-by-step progress cards that pulse during active execution and turn green upon completion.
- **Streaming Document Feed**: Cards show real-time titles, favicons, URLs, and extracted key takeaways as pages are scraped.
- **Thinking Drawer**: Collapsible pane revealing the agent's chain-of-thought / reasoning traces (e.g. Nemotron reasoning tokens).

### Feature 3: Interactive GraphRAG Knowledge Mesh Visualizer
- **Physics-Based Canvas (Vis-Network)**:
  - **Nodes**: Color-coded by Entity Type (Blue = Technology, Purple = Organization, Orange = Metric, Green = Concept).
  - **Edges**: Directed arrows labeled with predicates (`DEVELOPS`, `ACCELERATES`, `CONFLICTS_WITH`).
  - **Click-to-Inspect**: Clicking an entity node highlights connected claims and filters the source document ledger.
  - **Community Clusters**: Modularity-based cluster coloring to reveal interdisciplinary connections.

### Feature 4: Active Human-in-the-Loop (HITL) Steering Drawer
- When the agent encounters high ambiguity or critical contradictory claims, it smoothly pauses and presents a non-intrusive prompt:
  - *Option A*: Approve generated outline with 1-click.
  - *Option B*: Add custom steering notes (e.g., *"Ignore consumer vehicles; focus exclusively on commercial aviation"*).
  - *Option C*: Toggle Unattended Mode on the fly.

### Feature 5: Multi-Format Report Hub & Exporter
- **Split-View / Tabbed Dossier Viewer**:
  - 📖 **Executive Markdown**: Clean rendering with KaTeX math and footnote citations.
  - 🎓 **Academic LaTeX**: Live `.tex` code preview with syntax highlighting and `.bib` BibTeX bibliography.
  - 🌐 **Interactive HTML**: Standalone report preview with embedded Mermaid diagrams.
  - 🎙️ **NotebookLM Audio Podcast**: Built-in audio player reading the generated dialogue script using client-side speech synthesis.
- **1-Click Download Bar**: Download `.md`, `.tex`, `.bib`, `.html`, or raw `.json` bundles.

### Feature 6: Research History & Mission Archive
- Persistent research library powered by SQLite + IndexedDB.
- Search past research dossiers by keyword, date, or tags.
- Re-open past sessions instantly with full Knowledge Graph and source documents preserved.

### Feature 7: Full Settings & Hardware Diagnostics Modal
- **Live Hardware Diagnostics**:
  - Physical VRAM, System RAM, and CPU core meters.
  - Current tier badge with 1-click manual tier override selector.
  - One-click "Ping Ollama" button testing local model availability (`http://localhost:11434`).
- **Model & Budget Configurations**:
  - Switch providers (Ollama, NVIDIA NIM, OpenAI, Gemini, DeepSeek).
  - Spending caps ($ USD limit, max tokens limit).
  - Search engine preferences (DuckDuckGo, SearXNG, Tavily).

---

## 4. 🏗️ Technical Architecture & Backend API Extensions

### 4.1 Backend Endpoints (`src/server.py`)
```python
# 1. Start Research Mission
POST /api/research
Payload: { "topic": str, "depth": int, "provider": str, "constraints": str, "unattended": bool }
Returns: { "session_id": str, "status": "INITIALIZED" }

# 2. Server-Sent Events (SSE) Stream
GET /api/events/{session_id}
Streams: Typed events:
  - "agent_status": { "stage": "SEARCHING", "detail": "Executing 4 arXiv queries..." }
  - "document_scraped": { "title": "...", "url": "...", "tables_count": 2 }
  - "graph_updated": { "nodes": [...], "edges": [...] }
  - "hardware_metrics": { "vram_used_gb": 4.8, "ram_used_gb": 7.2 }
  - "hitl_required": { "prompt": "Outline needs review", "proposed_outline": [...] }
  - "report_completed": { "report_paths": {...}, "final_report": {...} }

# 3. Human-in-the-Loop Steering
POST /api/sessions/{session_id}/steer
Payload: { "action": "APPROVE" | "PIVOT" | "ABORT", "feedback": str }

# 4. Session History & Retrieval
GET /api/history                     # List recent research dossiers
GET /api/sessions/{session_id}       # Full session state & reports
DELETE /api/sessions/{session_id}    # Delete dossier

# 5. Live Configuration & Hardware Connectivity
GET  /api/config                     # Read runtime config
POST /api/config                     # Update config safely
GET  /api/hardware/status            # Probe physical VRAM, RAM, CPU & active tier
POST /api/hardware/profile           # Hot-swap hardware tier profile
GET  /api/health/ollama              # Probe local Ollama service & fetch installed models
```

### 4.2 Frontend Architecture (Embedded SPA in `src/static/`)
```
src/
├── static/
│   ├── index.html           # Semantic, clean HTML5 single-page application
│   ├── css/
│   │   └── style.css        # Modern CSS variables, glassmorphism, responsive grid
│   ├── js/
│   │   ├── app.js           # Core state machine, router, tab controller
│   │   ├── sse_client.js    # Resilient EventSource client with automatic reconnect
│   │   ├── graph_view.js    # Interactive Vis-Network knowledge graph renderer
│   │   ├── history.js       # SQLite & LocalStorage session synchronizer
│   │   ├── hardware.js      # Hardware diagnostic meter and telemetry poller
│   │   └── settings.js      # Configuration and Ollama health diagnostic tester
│   └── assets/
│       └── logo.svg         # SVG vector branding
```

---

## 5. 🚀 Execution & Verification Roadmap

1. **Phase 1: Backend SSE Event Bus & Hardware REST APIs**:
   - Implement `EventBroadcaster` in `src/server.py` and mount typed event generators into the agent loop.
   - Add `/api/events/{session_id}`, `/api/sessions/{session_id}/steer`, `/api/history`, `/api/hardware/status`, and `/api/health/ollama`.

2. **Phase 2: Modern Zero-Build Single-Page Application (`src/static/`)**:
   - Build responsive semantic UI: Dark/light theme support, Linear-style dark mode variables.
   - Connect real-time SSE listener for timeline progress, live document cards, and reasoning drawer.
   - Embed Vis-Network interactive Knowledge Graph with physics clustering.
   - Embed Hardware Telemetry bar showing live VRAM/RAM metrics.

3. **Phase 3: Human-in-the-Loop & Multi-Format Exporter UI**:
   - Build interactive outline approval banner and mid-execution steering modal.
   - Add tabbed dossier viewer with KaTeX math rendering and one-click file download handlers.

4. **Phase 4: CLI Shortcut & Docker Web Service**:
   - Add `uv run opendeepresearcher --ui` (or `opendeepresearcher-ui`) to automatically boot the server and launch the default browser to `http://localhost:8000`.
   - Update `docker-compose.yml` to expose port 8000 for zero-setup browser access.

5. **Phase 5: Automated Testing & Git Release**:
   - Write tests for SSE event stream and UI API endpoints in `tests/test_server_ui.py`.
   - Run Ruff, Mypy, and Pytest verification.
   - Commit and push to GitHub repository `Cyber-arghya/omni-researcher`.
