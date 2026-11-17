# OpenDeepResearcher: Architecture & Integration Plan 2.0 (plan2.md)

## 1. 🛡️ The Brutal Truth Filter: First-Principles Architecture Audit

Every proposed change must undergo strict first-principles scrutiny against KISS, DRY, Idempotency, and Security Boundaries before code execution.

| Proposed Feature / Request | First-Principles Analysis & Risk Assessment | Brutal Truth Verdict | Clean Engineered Solution |
|---|---|---|---|
| **Hardcoding API Keys directly in code** | **Critical Security Vulnerability.** Pushing hardcoded private keys (e.g. `nvapi-...`) to a public GitHub repository (`Cyber-arghya/omni-researcher`) triggers automatic GitHub Secret Scanning revocation within seconds, leaks developer quota to automated scrapers, and violates Rule 1 of `security-boundaries.md` and Rule 5 of `docker-multi-stage.md`. | ❌ **REJECTED (Strict Security Invariant)** | Zero hardcoded credentials in git. Provide pre-populated `.env.example`, automated `.env` loading, Docker `--env-file` injection, and clear documentation. |
| **Installing `langchain-nvidia-ai-endpoints`** | **Framework Bloat & Dependency Hell.** NVIDIA's NIM API (`https://integrate.api.nvidia.com/v1`) adheres to the standard OpenAI API specification. Installing LangChain introduces 45+ redundant transitive dependencies, Pydantic v1/v2 schema friction, and increased container build times. | ❌ **REJECTED (Anti-Bloat / KISS)** | Implement native NVIDIA NIM support inside our existing `UniversalLLMClient` via `AsyncOpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvidia_api_key)`. |
| **Support for Deep Reasoning Models (`enable_thinking` & `reasoning_content`)** | Frontier models like `nvidia/nemotron-3-ultra-550b-a55b`, DeepSeek-R1, and Qwen-2.5-Coder output `reasoning_content` inside `choice.message.additional_kwargs` or delta chunks before final answers. | ✅ **APPROVED (High Value for Deep Research)** | Add reasoning parser in `src/llm/client.py` and `src/llm/prompts.py` to extract chain-of-thought traces into `ResearchState.critic_notes`. |
| **Complete API Key & Docker Local/Cloud Setup in `README.md`** | Users and contributors need exact copy-paste guides for zero-cost local execution (Ollama), NVIDIA NIM setup, and Docker container networking. | ✅ **APPROVED (Crucial DX & User Onboarding)** | Add dedicated "🔑 Complete API Key Setup Guide" and "🐳 Production Docker & Local Model Guide" in `README.md` with explicit commands. |
| **Zero-Key Default Mode** | Academic APIs (arXiv, Crossref, PubMed) and search (DuckDuckGo) do not require paid API keys. The system must work out-of-the-box with $0 budget. | ✅ **APPROVED (Core Architecture Invariant)** | Ensure graceful execution when zero cloud keys are configured. |

---

## 2. 🔑 Comprehensive API Key Matrix & Default Fallbacks

| Service / Provider | Environment Variable | Cost / Tier | Is Key Mandatory? | Default Behavior if Missing |
|---|---|---|---|---|
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Free 1,000 API credits for developers | No | Falls back to local Ollama or OpenAI/Gemini if configured. |
| **Local Ollama** | `OLLAMA_BASE_URL` | 100% Free / Offline | **No** (Localhost) | Default local provider (`http://localhost:11434/v1`). |
| **arXiv API** | None | 100% Free / Open Access | **No** | Active by default for physics/CS pre-prints. |
| **Crossref Open DOI** | None | 100% Free / Open Access | **No** | Active by default for peer-reviewed journal verification. |
| **PubMed NCBI** | `NCBI_PUBMED_API_KEY` | 100% Free (Higher rate limit with key) | **No** | Queries public NCBI Entrez API with standard rate limits. |
| **DuckDuckGo Search** | None | 100% Free | **No** | Default zero-config primary search engine. |
| **Semantic Scholar** | `SEMANTIC_SCHOLAR_API_KEY` | Free Tier Available | **No** | Queries public graph API with standard rate limits. |
| **Tavily Search** | `TAVILY_API_KEY` | 1,000 free queries/mo | No | Falls back to DuckDuckGo and SearXNG. |
| **OpenAI / Claude / Gemini** | `OPENAI_API_KEY`, etc. | Pay-per-token | No | Optional cloud providers. |

---

## 3. 🛠️ Step-by-Step Implementation Architecture

### Step 1: Extend Configuration (`src/config.py`)
Add NVIDIA NIM configuration settings with validation:
- `nvidia_api_key: str | None = None`
- `nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"`
- `nvidia_model: str = "nvidia/nemotron-3-ultra-550b-a55b"`
- Update `llm_provider` literal choices to include `"nvidia"`.

### Step 2: Universal LLM Client Upgrade (`src/llm/client.py`)
- Support `llm_provider == "nvidia"`:
  ```python
  AsyncOpenAI(
      base_url=settings.nvidia_base_url,
      api_key=settings.nvidia_api_key,
  )
  ```
- Support `enable_thinking` and extraction of `reasoning_content` from streaming chunks and completion objects for models supporting reasoning tokens.

### Step 3: Synchronize `.env.example`
Provide a turnkey `.env.example` with clear sections:
- `Section 1: Local Offline Models (Ollama, LM Studio)`
- `Section 2: NVIDIA NIM & Enterprise Reasoning Models`
- `Section 3: Frontier Cloud APIs (Gemini, OpenAI, Anthropic)`
- `Section 4: Web Search & Academic APIs`

### Step 4: Comprehensive Setup Documentation in `README.md`
- Detailed setup instructions for:
  1. Local environment with `.env`.
  2. Running with NVIDIA NIM (`--provider nvidia` or `LLM_PROVIDER=nvidia`).
  3. Running with local Ollama (`--local`).
  4. Docker run with local Ollama on host (`host.docker.internal`).
  5. Docker Compose with `.env` file passing.

### Step 5: Verification & Testing
- Unit test for NVIDIA configuration in `tests/test_config.py`.
- Unit test for reasoning content parsing in `tests/test_llm_client.py`.
- Re-run Ruff, Mypy, and Pytest.
- Commit and push changes to GitHub repository `Cyber-arghya/omni-researcher`.

