// GuardMesh Web Application Client Logic
document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const apiUrlInput = document.getElementById("apiUrlInput");
  const apiKeyInput = document.getElementById("apiKeyInput");
  const gatewayStatusPill = document.getElementById("gatewayStatusPill");
  const gatewayStatusText = document.getElementById("gatewayStatusText");

  const navTabs = document.querySelectorAll(".nav-tab");
  const tabPanels = document.querySelectorAll(".tab-panel");

  const providerChips = document.querySelectorAll(".provider-chip");
  const promptInput = document.getElementById("promptInput");
  const promptCharCounter = document.getElementById("promptCharCounter");
  const btnEvaluate = document.getElementById("btnEvaluate");
  const btnSpinner = document.getElementById("btnSpinner");
  const resultsGrid = document.getElementById("resultsGrid");
  const resultsCountBadge = document.getElementById("resultsCountBadge");

  const kpiTotalRequests = document.getElementById("kpiTotalRequests");
  const kpiAllowed = document.getElementById("kpiAllowed");
  const kpiRedacted = document.getElementById("kpiRedacted");
  const kpiBlocked = document.getElementById("kpiBlocked");
  const kpiAvgLatency = document.getElementById("kpiAvgLatency");
  const kpiPiiCount = document.getElementById("kpiPiiCount");
  const auditProviderStatusGrid = document.getElementById("auditProviderStatusGrid");
  const policyViolationsChart = document.getElementById("policyViolationsChart");
  const auditTableBody = document.getElementById("auditTableBody");
  const actionFilterSelect = document.getElementById("actionFilterSelect");
  const btnRefreshAudit = document.getElementById("btnRefreshAudit");

  const policyYamlTextarea = document.getElementById("policyYamlTextarea");
  const btnSavePolicy = document.getElementById("btnSavePolicy");
  const btnReloadPolicy = document.getElementById("btnReloadPolicy");
  const overlayGroq = document.getElementById("overlayGroq");
  const overlayGemini = document.getElementById("overlayGemini");
  const overlayOpenAI = document.getElementById("overlayOpenAI");

  // Helper: Get Base API URL dynamically
  function getApiUrl() {
    const inputVal = apiUrlInput.value.trim().replace(/\/+$/, "");
    if (inputVal) return inputVal;
    if (window.location.origin && window.location.origin !== "null" && !window.location.origin.startsWith("file://")) {
      return window.location.origin;
    }
    return "http://127.0.0.1:8000";
  }

  // Set default API input URL dynamically if served over HTTP
  if (window.location.origin && !window.location.origin.startsWith("file://") && window.location.origin !== "null") {
    apiUrlInput.value = window.location.origin;
  }

  // Helper: Get Custom Headers
  function getHeaders() {
    const headers = { "Content-Type": "application/json" };
    const key = apiKeyInput.value.trim();
    if (key) headers["X-API-Key"] = key;
    return headers;
  }

  // Toast Notification System
  function showToast(message, type = "success") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  // Check Gateway System Health
  async function checkGatewayHealth() {
    try {
      const res = await fetch(`${getApiUrl()}/health`, { headers: getHeaders() });
      if (res.ok) {
        gatewayStatusPill.className = "status-indicator-pill";
        gatewayStatusText.innerHTML = '<span class="status-dot green pulsing"></span> Gateway Online';
      } else {
        throw new Error("HTTP " + res.status);
      }
    } catch (e) {
      gatewayStatusPill.className = "status-indicator-pill";
      gatewayStatusText.innerHTML = '<span class="status-dot red"></span> Gateway Offline';
    }
  }

  // Tab Navigation Switching
  navTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const targetPanelId = tab.getAttribute("data-tab");
      navTabs.forEach((t) => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      tabPanels.forEach((p) => {
        p.classList.add("hidden");
        p.classList.remove("active");
      });

      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      
      const targetPanel = document.getElementById(targetPanelId);
      if (targetPanel) {
        targetPanel.classList.remove("hidden");
        targetPanel.classList.add("active");
      }

      if (targetPanelId === "tabAudit") loadAuditAnalytics();
      if (targetPanelId === "tabPolicy") loadPolicyEngineData();
    });
  });

  // Provider Chip Selection Fix
  document.querySelectorAll('#providerSelectionGroup input[type="checkbox"]').forEach((cb) => {
    cb.addEventListener("change", () => {
      const chip = cb.closest(".provider-chip");
      if (chip) chip.classList.toggle("active", cb.checked);
    });
  });

  // Prompt Character Counter
  promptInput.addEventListener("input", () => {
    promptCharCounter.textContent = `${promptInput.value.length} chars`;
  });

  // Quick Presets Click Handler
  document.querySelectorAll(".btn-preset").forEach((btn) => {
    btn.addEventListener("click", () => {
      promptInput.value = btn.getAttribute("data-prompt");
      promptCharCounter.textContent = `${promptInput.value.length} chars`;
    });
  });

  // Evaluation Handler
  btnEvaluate.addEventListener("click", async () => {
    const selectedProviders = Array.from(
      document.querySelectorAll('#providerSelectionGroup input[type="checkbox"]:checked')
    ).map((cb) => cb.value);

    const promptText = promptInput.value.trim();

    if (selectedProviders.length === 0) {
      showToast("Please select at least one target LLM provider.", "error");
      return;
    }

    if (!promptText) {
      showToast("Please enter an input prompt to evaluate.", "error");
      return;
    }

    // UI Loading State
    btnEvaluate.disabled = true;
    btnSpinner.classList.remove("hidden");
    resultsGrid.innerHTML = "";
    resultsCountBadge.textContent = "Evaluating...";

    const evalPromises = selectedProviders.map(async (requestedProvider) => {
      try {
        const start = performance.now();
        const res = await fetch(`${getApiUrl()}/chat`, {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify({ provider: requestedProvider, prompt: promptText }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          return { provider: requestedProvider, error: errData.detail || `HTTP ${res.status}` };
        }

        const data = await res.json();
        return { requestedProvider, ...data };
      } catch (e) {
        return { provider: requestedProvider, error: e.message };
      }
    });

    const results = await Promise.all(evalPromises);

    // Reset Button State
    btnEvaluate.disabled = false;
    btnSpinner.classList.add("hidden");
    resultsCountBadge.textContent = `${results.length} Provider(s) Evaluated`;

    // Render Cards
    renderResultsCards(results);
  });

  function renderResultsCards(results) {
    resultsGrid.innerHTML = "";

    results.forEach((item) => {
      const card = document.createElement("div");

      if (item.error) {
        card.className = "result-card blocked";
        card.innerHTML = `
          <div class="result-card-header">
            <div class="result-title">Target Provider: ${item.provider}</div>
            <span class="badge badge-blocked">🔴 ERROR</span>
          </div>
          <div class="response-content-box" style="color:#f87171;">Failed to communicate with provider gateway: ${item.error}</div>
        `;
      } else {
        const action = item.action_taken || "allowed";
        const actualProvider = item.provider || item.requestedProvider;
        const isFailover = (item.status || "").startsWith("failover_to_");

        const cardClass = isFailover ? "failover" : action;
        card.className = `result-card ${cardClass}`;

        const actionBadge = `<span class="badge badge-${action}">${action.toUpperCase()}</span>`;
        const failoverBadge = isFailover
          ? `<span class="badge badge-failover">🔄 FAILOVER: ${item.requestedProvider} → ${actualProvider}</span>`
          : "";

        let detailsHtml = "";
        if (item.explanation_details) {
          detailsHtml = `
            <div class="explanation-banner">
              <strong>⚠️ Policy Reason:</strong> ${item.explanation_details.reason}
            </div>
            <div class="remediation-box">
              <strong>💡 Remediation Suggestion:</strong> ${item.explanation_details.remediation_suggestion}
            </div>
          `;
        } else if (item.explanation) {
          detailsHtml = `<div class="explanation-banner"><strong>ℹ️ Policy Notice:</strong> ${item.explanation}</div>`;
        }

        card.innerHTML = `
          <div class="result-card-header">
            <div class="result-title">Provider: <strong>${item.requestedProvider}</strong> ${isFailover ? '(Served by ' + actualProvider + ')' : ''}</div>
            <div class="badges-group">
              ${actionBadge}
              ${failoverBadge}
            </div>
          </div>
          <div class="result-meta">
            Latency: <strong>${item.latency_ms} ms</strong>
            ${item.triggered_policy ? ' • Triggered Policy: <strong style="color:#f59e0b">' + item.triggered_policy + '</strong>' : ''}
          </div>
          ${detailsHtml}
          <div class="response-content-box">${item.response || "<em>No response text returned (Blocked by policy)</em>"}</div>
        `;
      }

      resultsGrid.appendChild(card);
    });
  }

  // Load Audit Analytics Data
  async function loadAuditAnalytics() {
    try {
      const [summaryRes, logsRes, healthRes] = await Promise.all([
        fetch(`${getApiUrl()}/audit/summary`, { headers: getHeaders() }),
        fetch(`${getApiUrl()}/audit`, { headers: getHeaders() }),
        fetch(`${getApiUrl()}/providers`, { headers: getHeaders() }),
      ]);

      if (summaryRes.ok) {
        const summary = await summaryRes.json();
        kpiTotalRequests.textContent = summary.total_requests || 0;
        kpiAllowed.textContent = (summary.by_action && summary.by_action.allowed) || 0;
        kpiRedacted.textContent = (summary.by_action && summary.by_action.redacted) || 0;
        kpiBlocked.textContent = (summary.by_action && summary.by_action.blocked) || 0;
        kpiAvgLatency.textContent = `${summary.average_latency || 0} ms`;
        kpiPiiCount.textContent = summary.pii_count || 0;

        renderPolicyViolationsChart(summary.policy_violations || {});
      }

      if (healthRes.ok) {
        const provs = await healthRes.json();
        renderProviderStatusGrid(provs);
      }

      if (logsRes.ok) {
        const logs = await logsRes.json();
        window._guardmeshLogs = logs;
        renderAuditTable(logs);
      }
    } catch (e) {
      showToast("Failed to connect to audit metrics API: " + e.message, "error");
    }
  }

  function renderProviderStatusGrid(provs) {
    auditProviderStatusGrid.innerHTML = "";
    Object.entries(provs).forEach(([name, status]) => {
      const card = document.createElement("div");
      const isHealthy = status === "healthy";
      card.className = `provider-status-card ${isHealthy ? "healthy" : "unhealthy"}`;
      card.innerHTML = `
        <div style="font-weight:700; text-transform:capitalize;">${name}</div>
        <div style="color:${isHealthy ? "#10b981" : "#ef4444"}; font-weight:700; font-size:0.85rem; margin-top:4px;">
          ${status.toUpperCase()}
        </div>
      `;
      auditProviderStatusGrid.appendChild(card);
    });
  }

  function renderPolicyViolationsChart(violations) {
    policyViolationsChart.innerHTML = "";
    const entries = Object.entries(violations);
    if (entries.length === 0) {
      policyViolationsChart.innerHTML = '<div class="empty-chart-text">No policy violation metrics recorded yet.</div>';
      return;
    }

    const maxCount = Math.max(...entries.map(([, c]) => c), 1);
    entries.forEach(([policy, count]) => {
      const pct = Math.round((count / maxCount) * 100);
      const row = document.createElement("div");
      row.className = "chart-bar-item";
      row.innerHTML = `
        <div class="chart-bar-label">${policy}</div>
        <div class="chart-bar-track">
          <div class="chart-bar-fill" style="width: ${pct}%;"></div>
        </div>
        <div style="font-weight:700; width:30px; text-align:right;">${count}</div>
      `;
      policyViolationsChart.appendChild(row);
    });
  }

  function renderAuditTable(logs) {
    const filter = actionFilterSelect.value;
    const filtered = filter === "ALL" ? logs : logs.filter((l) => l.action_taken === filter);

    auditTableBody.innerHTML = "";

    if (filtered.length === 0) {
      auditTableBody.innerHTML = '<tr><td colspan="8" class="text-center">No audit records found matching filter.</td></tr>';
      return;
    }

    filtered.forEach((log) => {
      const tr = document.createElement("tr");
      const timeStr = log.timestamp ? new Date(log.timestamp * 1000).toLocaleString() : "-";
      const action = log.action_taken || "allowed";
      const badgeClass = `badge-${action}`;

      tr.innerHTML = `
        <td>${timeStr}</td>
        <td class="hash-code">${(log.request_id || "").slice(0, 8)}...</td>
        <td style="text-transform:capitalize; font-weight:600;">${log.provider || "-"}</td>
        <td><span class="badge ${badgeClass}">${action.toUpperCase()}</span></td>
        <td>${log.triggered_policy || "-"}</td>
        <td>${log.latency_ms} ms</td>
        <td class="hash-code" title="${log.prompt_hash}">${(log.prompt_hash || "").slice(0, 12)}...</td>
        <td style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${log.explanation || ''}">
          ${log.explanation || "-"}
        </td>
      `;
      auditTableBody.appendChild(tr);
    });
  }

  actionFilterSelect.addEventListener("change", () => {
    if (window._guardmeshLogs) renderAuditTable(window._guardmeshLogs);
  });

  btnRefreshAudit.addEventListener("click", () => {
    loadAuditAnalytics();
    showToast("Audit analytics data refreshed.", "success");
  });

  // Load Policy Engine Data
  async function loadPolicyEngineData() {
    try {
      const [effGroq, effGemini, effOpenAI] = await Promise.all([
        fetch(`${getApiUrl()}/policy/effective/groq`, { headers: getHeaders() }).then((r) => r.json()).catch(() => ({})),
        fetch(`${getApiUrl()}/policy/effective/gemini`, { headers: getHeaders() }).then((r) => r.json()).catch(() => ({})),
        fetch(`${getApiUrl()}/policy/effective/openai`, { headers: getHeaders() }).then((r) => r.json()).catch(() => ({})),
      ]);

      overlayGroq.textContent = JSON.stringify(effGroq, null, 2);
      overlayGemini.textContent = JSON.stringify(effGemini, null, 2);
      overlayOpenAI.textContent = JSON.stringify(effOpenAI, null, 2);

      // Populate textarea with structured overlay policy template if missing or unpopulated
      if (!policyYamlTextarea.value.trim() || !policyYamlTextarea.value.includes("providers:")) {
        policyYamlTextarea.value = `version: "1.0.0"
description: "GuardMesh Enterprise Governance & Provider Overlay Policies"

base:
  pii:
    enabled: true
    patterns:
      - email
      - phone
      - ssn
      - credit_card
    action: redact
  toxicity:
    enabled: true
    threshold: 0.8
  blocked_topics:
    enabled: true
    keywords:
      - malware
      - fraud
    action: block

providers:
  groq:
    toxicity:
      enabled: true
      threshold: 0.4
    blocked_topics:
      enabled: true
      keywords:
        - politics

  gemini:
    pii:
      enabled: true
      action: block
    toxicity:
      enabled: true
      threshold: 0.7
    blocked_topics:
      enabled: true
      keywords:
        - medical

  openai:
    pii:
      enabled: false
      action: redact
    toxicity:
      enabled: true
      threshold: 0.5
    blocked_topics:
      enabled: true
      keywords:
        - weapons
        - drugs
`;
      }
    } catch (e) {
      showToast("Failed to load policy engine data.", "error");
    }
  }

  btnSavePolicy.addEventListener("click", async () => {
    const yamlContent = policyYamlTextarea.value;
    try {
      const res = await fetch(`${getApiUrl()}/update-policy`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ yaml_content: yamlContent }),
      });

      if (res.ok) {
        const data = await res.json();
        showToast(`Policy updated! Active base checks: ${data.base_checks}`, "success");
        loadPolicyEngineData();
      } else {
        throw new Error("HTTP " + res.status);
      }
    } catch (e) {
      showToast("Failed to save policy: " + e.message, "error");
    }
  });

  btnReloadPolicy.addEventListener("click", async () => {
    try {
      const res = await fetch(`${getApiUrl()}/reload-policy`, {
        method: "POST",
        headers: getHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        showToast(`Policy engine reloaded! Base checks: ${data.base_checks}`, "success");
        loadPolicyEngineData();
      } else {
        throw new Error("HTTP " + res.status);
      }
    } catch (e) {
      showToast("Failed to reload policy: " + e.message, "error");
    }
  });

  // Initialize System Health Check
  checkGatewayHealth();
  setInterval(checkGatewayHealth, 10000);
});
