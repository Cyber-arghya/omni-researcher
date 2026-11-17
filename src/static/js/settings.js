/**
 * Settings and Model Management Modal Controller.
 */

class SettingsController {
  constructor() {
    this.modal = document.getElementById("settings-modal");
    this.initEventListeners();
  }

  initEventListeners() {
    const openBtn = document.getElementById("btn-open-settings");
    const closeBtn = document.getElementById("btn-close-settings");

    if (openBtn) {
      openBtn.onclick = () => {
        this.open();
        this.loadConfig();
      };
    }
    if (closeBtn) {
      closeBtn.onclick = () => this.close();
    }

    // Tab buttons
    const tabLlm = document.getElementById("tab-btn-llm");
    const tabHw = document.getElementById("tab-btn-hardware");
    const secLlm = document.getElementById("settings-tab-llm");
    const secHw = document.getElementById("settings-tab-hardware");

    if (tabLlm && tabHw && secLlm && secHw) {
      tabLlm.onclick = () => {
        tabLlm.classList.add("border-b-2", "border-cyan-400", "font-bold", "text-cyan-400");
        tabLlm.classList.remove("text-slate-400");
        tabHw.classList.remove("border-b-2", "border-cyan-400", "font-bold", "text-cyan-400");
        tabHw.classList.add("text-slate-400");
        secLlm.classList.remove("hidden");
        secHw.classList.add("hidden");
      };
      tabHw.onclick = () => {
        tabHw.classList.add("border-b-2", "border-cyan-400", "font-bold", "text-cyan-400");
        tabHw.classList.remove("text-slate-400");
        tabLlm.classList.remove("border-b-2", "border-cyan-400", "font-bold", "text-cyan-400");
        tabLlm.classList.add("text-slate-400");
        secHw.classList.remove("hidden");
        secLlm.classList.add("hidden");
      };
    }

    // Ping Ollama button
    const pingBtn = document.getElementById("btn-ping-ollama");
    if (pingBtn) {
      pingBtn.onclick = () => this.pingOllama();
    }

    // Save Settings button
    const saveBtn = document.getElementById("btn-save-settings");
    if (saveBtn) {
      saveBtn.onclick = () => this.saveConfig();
    }
  }

  open() {
    if (this.modal) this.modal.classList.remove("hidden");
  }

  close() {
    if (this.modal) this.modal.classList.add("hidden");
  }

  async loadConfig() {
    try {
      const resp = await fetch("/api/config");
      if (!resp.ok) return;
      const cfg = await resp.json();

      const providerSelect = document.getElementById("setting-llm-provider");
      const fastModelInput = document.getElementById("setting-fast-model");
      const deepModelInput = document.getElementById("setting-deep-model");
      const baseUrlInput = document.getElementById("setting-base-url");
      const maxCostInput = document.getElementById("setting-max-cost");

      if (providerSelect) providerSelect.value = cfg.llm_provider || "ollama";
      if (fastModelInput) fastModelInput.value = cfg.llm_fast_model || "";
      if (deepModelInput) deepModelInput.value = cfg.llm_deep_model || "";
      if (baseUrlInput) baseUrlInput.value = cfg.llm_base_url || "";
      if (maxCostInput) maxCostInput.value = cfg.max_cost_limit_usd || 2.0;
    } catch (e) {
      console.warn("Error loading settings:", e);
    }
  }

  async saveConfig() {
    const payload = {
      llm_provider: document.getElementById("setting-llm-provider")?.value,
      llm_fast_model: document.getElementById("setting-fast-model")?.value,
      llm_deep_model: document.getElementById("setting-deep-model")?.value,
      llm_base_url: document.getElementById("setting-base-url")?.value,
      max_cost_limit_usd: parseFloat(document.getElementById("setting-max-cost")?.value || "2.0"),
    };

    try {
      const resp = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (resp.ok) {
        this.close();
        // Update header provider badge
        const badge = document.getElementById("header-provider-badge");
        if (badge) badge.innerText = (payload.llm_provider || "OLLAMA").toUpperCase();
      }
    } catch (e) {
      console.error("Failed to save settings:", e);
    }
  }

  async pingOllama() {
    const statusText = document.getElementById("ollama-ping-result");
    if (statusText) {
      statusText.innerText = "Pinging Ollama...";
      statusText.className = "text-xs text-cyan-400";
    }

    try {
      const resp = await fetch("/api/health/ollama");
      const data = await resp.json();
      if (data.status === "online") {
        if (statusText) {
          statusText.innerText = `Online! Detected ${data.models?.length || 0} local models.`;
          statusText.className = "text-xs text-emerald-400";
        }
      } else {
        if (statusText) {
          statusText.innerText = "Ollama is unreachable. Ensure 'ollama serve' is active.";
          statusText.className = "text-xs text-rose-400";
        }
      }
    } catch {
      if (statusText) {
        statusText.innerText = "Connection failed.";
        statusText.className = "text-xs text-rose-400";
      }
    }
  }
}

window.SettingsController = SettingsController;
