/**
 * Hardware Telemetry & Adaptive Resource Profiler Client Controller.
 */

class HardwareController {
  constructor() {
    this.pollInterval = null;
    this.currentStatus = null;
  }

  async fetchStatus() {
    try {
      const resp = await fetch("/api/hardware/status");
      if (!resp.ok) return null;
      const data = await resp.json();
      this.currentStatus = data;
      this.renderHeaderBadge(data);
      this.renderDiagnosticsModal(data);
      return data;
    } catch (e) {
      console.warn("Failed to fetch hardware status:", e);
      return null;
    }
  }

  startPolling(intervalMs = 10000) {
    this.fetchStatus();
    this.pollInterval = setInterval(() => this.fetchStatus(), intervalMs);
  }

  stopPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  renderHeaderBadge(data) {
    const badge = document.getElementById("header-hardware-badge");
    if (!badge) return;

    const tierLabels = {
      entry_8gb: "8GB Entry",
      enthusiast_16gb: "16GB Enthusiast",
      workstation_24gb_plus: "24GB+ Turbo",
      cloud_hybrid: "Cloud Hybrid",
    };

    const label = tierLabels[data.active_tier] || data.active_tier;
    const vramStr = data.vram_gb > 0 ? `${data.vram_gb.toFixed(1)}G VRAM` : "CPU";
    badge.innerHTML = `
      <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-cyan-950/60 text-cyan-300 border border-cyan-800/60 cursor-pointer hover:bg-cyan-900/60 transition" title="Click to view Hardware Diagnostics">
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        ${label} • ${vramStr} • ${data.ram_gb.toFixed(0)}G RAM
      </span>
    `;
    badge.onclick = () => {
      const settingsModal = document.getElementById("settings-modal");
      if (settingsModal) {
        settingsModal.classList.remove("hidden");
        const tabBtn = document.getElementById("tab-btn-hardware");
        if (tabBtn) tabBtn.click();
      }
    };
  }

  renderDiagnosticsModal(data) {
    const tierElem = document.getElementById("diag-active-tier");
    const vramElem = document.getElementById("diag-vram-text");
    const ramElem = document.getElementById("diag-ram-text");
    const cpuElem = document.getElementById("diag-cpu-text");
    const descElem = document.getElementById("diag-tier-desc");

    if (tierElem) tierElem.innerText = data.active_tier.toUpperCase();
    if (vramElem) vramElem.innerText = `${data.vram_gb.toFixed(1)} GB`;
    if (ramElem) ramElem.innerText = `${data.ram_gb.toFixed(1)} GB`;
    if (cpuElem) cpuElem.innerText = `${data.cpu_cores} Cores`;
    if (descElem && data.preset) descElem.innerText = data.preset.description || "";
  }

  async setProfile(profile) {
    try {
      const resp = await fetch("/api/hardware/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile }),
      });
      if (resp.ok) {
        await this.fetchStatus();
      }
    } catch (e) {
      console.error("Failed to update hardware profile:", e);
    }
  }
}

window.HardwareController = HardwareController;

