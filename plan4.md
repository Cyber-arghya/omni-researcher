# OpenDeepResearcher: 8GB VRAM & 16GB RAM Optimization Architecture (plan4.md)

## 1. 🛡️ The Brutal Truth Filter: Hardware Constraint Reality

Running multi-agent deep research on consumer hardware (8GB GPU VRAM + 16GB System RAM) presents strict physical boundaries. Failing to respect these limits causes Windows to thrash virtual memory (pagefile), degrading token generation from 45 tok/s to < 1.5 tok/s, or throwing `CUDA out of memory` / `Process killed` crashes.

| Component / Workload | Unoptimized Memory Footprint | Risk on 8GB VRAM / 16GB RAM | Brutal Truth Verdict | Precision 8GB/16GB Optimization Strategy |
|---|---|---|---|---|
| **Tier 2 Reasoning LLM (14B-32B)** | `deepseek-r1:14b` (~9.2 GB VRAM) or `qwen2.5:14b` (~9.0 GB VRAM) | **Immediate OOM or severe RAM spillover.** 8GB GPU only has ~6.8-7.2 GB usable VRAM after OS/display overhead. | ❌ **14B+ Local Models REJECTED for 8GB VRAM** | Standardize on **`qwen2.5:7b-instruct-q4_K_M`** (~4.7 GB) or **`deepseek-r1:7b` / `deepseek-r1:8b`** (~4.9 GB). Offload larger 550B models to free NVIDIA NIM cloud (`nvapi-...`). |
| **Tier 1 Fast Extraction LLM** | `llama3.1:8b` (~5.5 GB VRAM) | Running 8B for fast query expansion consumes most of the GPU, preventing concurrent tasks. | ❌ **8B Fast Tier REJECTED** | Standardize on **`llama3.2:3b-instruct-q4_K_M`** (~2.0 GB VRAM, 65+ tok/s) or **`qwen2.5:3b`**. |
| **KV Cache Allocation at 32k Context** | 32k context at FP16 KV cache consumes **~3.8 GB VRAM** just for attention history! | 4.8 GB (Model) + 3.8 GB (KV Cache) = 8.6 GB > 8.0 GB VRAM limit. **Crash during long chapter synthesis.** | ❌ **Unbounded 32k FP16 KV Cache REJECTED** | Limit local context to **`num_ctx: 8192`**, enable FlashAttention (`OLLAMA_FLASH_ATTENTION=1`), and quantize KV cache to `q8_0` or `q4_0` (saves 50-75% KV VRAM). |
| **Dense Embeddings in GPU VRAM** | `BAAI/bge-m3` running in FP16 on `cuda:0` consumes **~2.2 GB VRAM**. | 4.8 GB (LLM) + 2.2 GB (Embedding) = 7.0 GB VRAM (leaving zero headroom for KV cache or crawler). | ❌ **GPU-Hosted Heavy Embeddings REJECTED** | Pin dense embedding generation to **CPU System RAM** (`device="cpu"`) using **`BAAI/bge-small-en-v1.5`** (~133 MB) or Ollama **`nomic-embed-text`** (~274 MB). Keeps 100% of GPU VRAM for the LLM. |
| **Playwright Chromium Memory Leakage** | Launching multiple Chromium browser instances consumes **~600-900 MB RAM per instance**. | 16GB System RAM has only ~9-10 GB free after Windows 11. 5 parallel browsers + Python + ChromaDB = RAM starvation. | ❌ **Multi-process Browser Spawning REJECTED** | Implement single-browser lifecycle pooling with ephemeral `BrowserContext` disposal, blocking media/fonts, and explicit garbage collection (`gc.collect()`). |

---

## 2. 📊 The 8GB VRAM & 16GB RAM Memory Budget

```
+---------------------------------------------------------------------------------------------------+
| 🎮 GPU VRAM BUDGET (8.0 GB Physical Limit)                                                        |
+--------------------------+-----------------------+------------------------+-----------------------+
| Windows DWM / Display    | Tier 2 LLM Weights    | 8k Quantized KV Cache  | Safety Headroom       |
| ~0.9 GB                  | ~4.7 GB (Qwen 7B Q4)  | ~1.1 GB (FlashAttn)    | ~1.3 GB (No OOM)      |
+--------------------------+-----------------------+------------------------+-----------------------+

+---------------------------------------------------------------------------------------------------+
| 💻 SYSTEM RAM BUDGET (16.0 GB Physical Limit)                                                     |
+--------------------+---------------------+--------------------+--------------------+--------------+
| Windows 11 Base    | Embedding Engine    | ChromaDB + NetworkX| Playwright Engine  | Free Buffer  |
| ~5.2 GB            | ~0.3 GB (CPU nomic) | ~1.2 GB            | ~0.6 GB (Headless) | ~8.7 GB Free |
+--------------------+---------------------+--------------------+--------------------+--------------+
```

---

## 3. ⚙️ Hardware Optimization Blueprint

### 3.1 Model Tier Architecture (8GB Profile)
- **Fast / Routing Tier**: `llama3.2:3b` (~2.0 GB VRAM)
  - Tasks: Query decomposition, search relevance scoring, deduplication, HTML table filtering.
- **Deep / Synthesis Tier**: `deepseek-r1:7b` or `qwen2.5:7b-instruct-q4_K_M` (~4.7 GB VRAM)
  - Tasks: Knowledge graph synthesis, adversarial critique, chapter authoring, citation grounding.
- **Ultra / Heavy Fallback (Optional Cloud)**: NVIDIA NIM `nvidia/nemotron-3-ultra-550b-a55b` via free `nvapi-...`.
  - Tasks: When 100% local VRAM must be preserved for vision or massive documents, offloads 0 MB to local GPU.

### 3.2 Vision Model VRAM Collision Prevention
- `llama3.2-vision:11b` requires ~7.9 GB VRAM and **cannot** co-exist with a 7B text model in 8GB VRAM.
- **Sequential Swapping Mechanism**:
  - Configure Ollama `OLLAMA_MAX_LOADED_MODELS=1` and `OLLAMA_KEEP_ALIVE=1m`.
  - During scraping, images are queued. The text model is unloaded before the vision model analyzes figures, then unloaded before synthesis resumes.
  - Or fallback to text-only / cloud vision if local VRAM is constrained.

### 3.3 Dynamic CPU-Pinned Embeddings
- In `src/rag/embeddings.py`, detect available VRAM:
  - If GPU VRAM < 12 GB, force PyTorch `device="cpu"` for `SentenceTransformer`.
  - Use quantized `nomic-embed-text` via Ollama or `all-MiniLM-L6-v2` / `bge-small-en-v1.5` in CPU RAM.

### 3.4 Chromium Playwright Scraper Memory Throttling
- Force single browser instance reuse in `src/crawler/scraper.py`.
- Enforce strict abort of images, videos, audio, web fonts (`.woff`, `.woff2`, `.ttf`), and stylesheets.
- Close `context` and `page` immediately after HTML extraction.
- Trigger `gc.collect()` after batch scraping jobs.

### 3.5 Automated Hardware Preset in Configuration
- Add `hardware_profile: Literal["auto", "8gb_vram_16gb_ram", "high_end_gpu", "cpu_only"] = "auto"` in `src/config.py`.
- When set to `"8gb_vram_16gb_ram"` (or auto-detected via `psutil` and `torch.cuda`):
  - Sets default fast model: `llama3.2:3b`
  - Sets default deep model: `qwen2.5:7b` (or `deepseek-r1:7b`)
  - Caps context window to `8192` tokens.
  - Pins embedding engine to CPU.
  - Sets concurrent search batch size to 3 (instead of 6).

---

## 4. 🛠️ Execution & Implementation Roadmap

1. **Phase 1: Configuration & Auto-Detection (`src/config.py`)**:
   - Add hardware inspection via `torch.cuda.get_device_properties(0).total_memory` and `psutil.virtual_memory().total`.
   - Apply 8GB VRAM profile overrides automatically if physical VRAM <= 8.5 GB.
2. **Phase 2: CPU-Pinned Resilient Embeddings (`src/rag/embeddings.py`)**:
   - Ensure embeddings do not compete with LLM for GPU memory.
3. **Phase 3: Scraper Memory Reclamation (`src/crawler/scraper.py`)**:
   - Add explicit garbage collection and single-browser context isolation.
4. **Phase 4: Updated `.env.example` & Documentation**:
   - Document the 8GB VRAM / 16GB RAM profile in `README.md` with exact `ollama pull` commands.
5. **Phase 5: Verification & Testing**:
   - Test config auto-tuning and memory profile detection in `tests/test_config.py`.
   - Run Ruff, Mypy, and Pytest.
   - Commit and push to GitHub repository `Cyber-arghya/omni-researcher`.

