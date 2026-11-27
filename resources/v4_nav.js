/* resources/v4_nav.js — KanbanBoard v4.0 Menu Navigation, Version History, Cases, Docs & Boss Config (strict-CSP safe) */
(function () {
  "use strict";

  let activeView = "board";
  let activeProject = "";
  let projectsList = [];
  let docViewerHandle = null;

  function csrfToken() {
    const m = document.querySelector('meta[name="kb-csrf"]');
    return m ? m.getAttribute("content") || "" : "";
  }

  async function api(url, opts) {
    const o = opts || {};
    const headers = Object.assign({ "Content-Type": "application/json" }, o.headers || {});
    if (o.method && o.method !== "GET") headers["X-Kanban-CSRF"] = csrfToken();
    const res = await fetch(url, Object.assign({}, o, { headers }));
    const data = await res.json().catch(() => ({ ok: false, error: "Invalid JSON" }));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function ensureShellMounted() {
    if (document.getElementById("v4-nav-bar")) return;
    const header = document.querySelector("header.topbar");
    const main = document.querySelector("main.workspace");
    if (!header || !main) return;

    const nav = document.createElement("nav");
    nav.id = "v4-nav-bar";
    nav.className = "v4-nav";
    nav.setAttribute("aria-label", "Primary Navigation");
    nav.innerHTML = `
      <button type="button" class="v4-nav-btn active" data-view="board">Board</button>
      <button type="button" class="v4-nav-btn" data-view="cases">Cases</button>
      <button type="button" class="v4-nav-btn" data-view="docs">Docs</button>
      <button type="button" class="v4-nav-btn" data-view="versions">Versions</button>
      <button type="button" class="v4-nav-btn" data-view="config">Config</button>
      <span class="v4-nav-spacer"></span>
      <select id="v4-project-select" class="v4-project-select" aria-label="Active project"></select>
      <span id="v4-project-version-pill" class="v4-version-pill" title="Current project version">V0.0.0</span>
    `;
    header.insertAdjacentElement("afterend", nav);

    const viewsHost = document.createElement("div");
    viewsHost.id = "v4-views-host";
    viewsHost.innerHTML = `
      <section id="v4-view-cases" class="v4-view hidden"></section>
      <section id="v4-view-docs" class="v4-view hidden"></section>
      <section id="v4-view-versions" class="v4-view hidden"></section>
      <section id="v4-view-config" class="v4-view hidden"></section>
    `;
    main.insertAdjacentElement("afterend", viewsHost);

    nav.querySelectorAll(".v4-nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => switchView(btn.getAttribute("data-view")));
    });

    const sel = document.getElementById("v4-project-select");
    sel.addEventListener("change", () => {
      activeProject = sel.value;
      refreshVersionPill();
      renderActiveView();
    });
  }

  async function loadProjects() {
    try {
      const board = await api("/api/board?summary=1");
      const set = new Set();
      (board.tickets || []).forEach((t) => { if (t.project) set.add(t.project); });
      const rawProjects = (board.board && board.board.projects) || board.projects || [];
      rawProjects.forEach((p) => { set.add(typeof p === "string" ? p : (p.slug || p.name)); });
      projectsList = Array.from(set).filter(Boolean).sort();
      const sel = document.getElementById("v4-project-select");
      if (sel) {
        if (!activeProject && projectsList.length) activeProject = projectsList[0];
        sel.innerHTML = projectsList.length
          ? projectsList.map((p) => `<option value="${esc(p)}" ${p === activeProject ? "selected" : ""}>${esc(p)}</option>`).join("")
          : `<option value="">No projects</option>`;
      }
      await refreshVersionPill();
    } catch (_) {}
  }

  async function refreshVersionPill() {
    const pill = document.getElementById("v4-project-version-pill");
    if (!pill || !activeProject) return;
    try {
      const vh = await api(`/api/version/history?project=${encodeURIComponent(activeProject)}`);
      pill.textContent = vh.version || "V0.0.0";
    } catch (_) {
      pill.textContent = "V0.0.0";
    }
  }

  function switchView(view) {
    activeView = view;
    document.querySelectorAll(".v4-nav-btn").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-view") === view);
    });
    const main = document.querySelector("main.workspace");
    const quickbar = document.querySelector(".quickbar");
    if (main) main.classList.toggle("hidden", view !== "board");
    if (quickbar) quickbar.classList.toggle("hidden", view !== "board");

    ["cases", "docs", "versions", "config"].forEach((v) => {
      const el = document.getElementById(`v4-view-${v}`);
      if (el) el.classList.toggle("hidden", view !== v);
    });

    if (view !== "docs" && docViewerHandle) {
      try { docViewerHandle.destroy(); } catch (_) {}
      docViewerHandle = null;
    }
    renderActiveView();
  }

  function renderActiveView() {
    if (activeView === "cases") renderCasesView();
    else if (activeView === "docs") renderDocsView();
    else if (activeView === "versions") renderVersionsView();
    else if (activeView === "config") renderConfigView();
  }

  async function renderCasesView() {
    const el = document.getElementById("v4-view-cases");
    if (!el) return;
    el.innerHTML = `<div class="v4-card">Loading Cases...</div>`;
    try {
      const url = activeProject ? `/api/cases?project=${encodeURIComponent(activeProject)}` : "/api/cases";
      const data = await api(url);
      const cases = data.cases || data.items || [];
      el.innerHTML = `
        <div class="v4-card">
          <h3>Cases (${cases.length})</h3>
          ${cases.length ? cases.map((c) => {
            const cid = c.id || c.case_id || "";
            return `
            <div class="v4-row-item">
              <button type="button" class="v4-case-btn" data-case-id="${esc(cid)}">
                <strong>${esc(cid)}</strong> — ${esc(c.title || "")}
                <div class="v4-meta-line">
                  Kind: ${esc(c.kind || "note")} · Tickets: ${(c.tickets || []).map((t) => `<span class="v4-ticket-chip">${esc(t)}</span>`).join("")}
                </div>
              </button>
              <div id="v4-case-detail-${esc(cid)}" class="v4-case-detail hidden"></div>
            </div>`;
          }).join("") : '<p class="v4-muted">No cases recorded yet.</p>'}
        </div>`;

      el.querySelectorAll(".v4-case-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const cid = btn.getAttribute("data-case-id");
          const detailEl = document.getElementById(`v4-case-detail-${cid}`);
          if (!detailEl) return;
          if (!detailEl.classList.contains("hidden")) {
            detailEl.classList.add("hidden");
            return;
          }
          detailEl.classList.remove("hidden");
          detailEl.textContent = "Loading case details...";
          try {
            const detail = await api(`/api/case?id=${encodeURIComponent(cid)}`);
            const linked = (detail.linked_tickets || []).map((lt) => lt.deleted ? lt.tombstone : `${lt.ref} (${lt.status})`).join("\n");
            const atts = (detail.attachments || []).length ? `\n\nAttachments:\n${detail.attachments.join("\n")}` : "";
            detailEl.textContent = `Author: ${detail.author || "—"} · Updated: ${detail.updated_at || "—"}\nLinked:\n${linked || "—"}\n\n${detail.body || ""}${atts}`;
          } catch (err) {
            detailEl.textContent = `Failed to load Case ${cid}: ${err.message}`;
          }
        });
      });
    } catch (err) {
      el.innerHTML = `<div class="v4-card v4-status-msg err">Failed to load Cases: ${esc(err.message)}</div>`;
    }
  }

  function renderDocsView() {
    const el = document.getElementById("v4-view-docs");
    if (!el) return;
    if (!activeProject) {
      el.innerHTML = `<div class="v4-card">Select a project to view its Living Docs.</div>`;
      return;
    }
    el.innerHTML = `<div id="v4-doc-mount"></div>`;
    if (window.KanbanDocShell) {
      docViewerHandle = window.KanbanDocShell.mountDocViewer(
        document.getElementById("v4-doc-mount"),
        activeProject
      );
    } else {
      el.innerHTML = `<div class="v4-card v4-status-msg err">Doc shell runtime (/doc-shared/shell.js) not loaded.</div>`;
    }
  }

  async function renderVersionsView() {
    const el = document.getElementById("v4-view-versions");
    if (!el) return;
    if (!activeProject) {
      el.innerHTML = `<div class="v4-card">Select a project to inspect Version History.</div>`;
      return;
    }
    el.innerHTML = `<div class="v4-card">Loading version history...</div>`;
    try {
      const vh = await api(`/api/version/history?project=${encodeURIComponent(activeProject)}`);
      const pending = vh.pending_next || { ticket_count: 0, tickets: [], clusters: [], largest_cluster_size: 0, cluster_threshold: 7, total_threshold: 12 };
      const history = vh.history || [];

      el.innerHTML = `
        <div class="v4-grid-2">
          <div class="v4-card">
            <h3>Current Version: <span class="v4-version-pill">${esc(vh.version)}</span></h3>
            <p class="v4-meta-line">
              n − 1 accounting: tickets completed now belong to the <strong>next</strong> version.
              Bumping stamps all pending done tickets and triggers <code>kb-doc</code> (TELL).
            </p>
            <div class="v4-field">
              <label for="v4-bump-ver">New Version (must strictly increase, e.g. V1.0.0)</label>
              <input id="v4-bump-ver" type="text" placeholder="V1.0.0" />
            </div>
            <div class="v4-field">
              <label for="v4-bump-note">Release Note (optional)</label>
              <input id="v4-bump-note" type="text" placeholder="Shipped feature cluster..." />
            </div>
            <button type="button" id="v4-btn-bump" class="v4-btn">Bump Version &amp; Run kb-doc TELL</button>
            <div id="v4-bump-status" class="v4-status-msg"></div>
          </div>

          <div class="v4-card">
            <h3>Pending for Next Version (V_next)</h3>
            <div class="v4-summary-line">
              Largest cluster: <strong>${pending.largest_cluster_size} / ${pending.cluster_threshold}</strong> ·
              Total pending done: <strong>${pending.ticket_count} / ${pending.total_threshold}</strong>
            </div>
            ${(pending.clusters || []).map((c) => `
              <div class="v4-cluster-box">
                <div><strong>${esc(c.label)}</strong> (${c.size} tickets · avg weight ${c.avg_weight})</div>
                <div class="v4-chips-row">${(c.tickets || []).map((t) => `<span class="v4-ticket-chip">${esc(t)}</span>`).join("")}</div>
              </div>`).join("") || '<p class="v4-muted-sm">No pending done tickets yet.</p>'}
          </div>
        </div>

        <div class="v4-card">
          <h3>Version History (${history.length})</h3>
          ${history.length ? history.map((h) => `
            <div class="v4-row-item">
              <div class="v4-history-head">
                <span class="v4-version-pill">${esc(h.version)}</span>
                <span class="v4-muted-sm">from ${esc(h.previous_version)} · by ${esc(h.bumped_by)} · ${esc((h.bumped_at || "").slice(0, 10))}</span>
              </div>
              ${h.note ? `<div class="v4-note-line">${esc(h.note)}</div>` : ""}
              <div class="v4-chips-row">
                ${(h.tickets || []).map((t) => `<span class="v4-ticket-chip">${esc(t)}</span>`).join("") || '<span class="v4-muted-sm">No tickets attached</span>'}
              </div>
            </div>`).join("") : '<p class="v4-muted">No versions released yet.</p>'}
        </div>`;

      document.getElementById("v4-btn-bump").addEventListener("click", async () => {
        const ver = (document.getElementById("v4-bump-ver").value || "").trim();
        const note = (document.getElementById("v4-bump-note").value || "").trim();
        const st = document.getElementById("v4-bump-status");
        st.className = "v4-status-msg";
        st.textContent = "Bumping version...";
        try {
          const res = await api("/api/version/bump", {
            method: "POST",
            body: JSON.stringify({ project: activeProject, version: ver, bumped_by: "Boss", note }),
          });
          st.textContent = `Bumped to ${res.new_version} (${res.ticket_count} tickets shipped). kb-doc TELL queued.`;
          await refreshVersionPill();
          renderVersionsView();
        } catch (err) {
          st.className = "v4-status-msg err";
          st.textContent = err.message;
        }
      });
    } catch (err) {
      el.innerHTML = `<div class="v4-card v4-status-msg err">Failed to load Version History: ${esc(err.message)}</div>`;
    }
  }

  async function renderConfigView() {
    const el = document.getElementById("v4-view-config");
    if (!el) return;
    el.innerHTML = `<div class="v4-card">Loading Boss Config...</div>`;
    try {
      const q = activeProject ? `?project=${encodeURIComponent(activeProject)}` : "";
      const data = await api(`/api/doc/config${q}`);
      const cfg = data.effective || data.global || {};
      const runs = data.runs || [];

      el.innerHTML = `
        <div class="v4-grid-2">
          <div class="v4-card">
            <h3>Boss Config Control (${activeProject ? "Effective for " + esc(activeProject) : "Global"})</h3>
            <div class="v4-field">
              <label for="cfg-scope">Save Scope</label>
              <select id="cfg-scope">
                <option value="global">Global Default (all projects — board/_doc_config.json)</option>
                ${activeProject ? `<option value="project">Project Override (${esc(activeProject)} only)</option>` : ""}
              </select>
            </div>
            <div class="v4-field">
              <label for="cfg-primary">Primary CLI Backend</label>
              <select id="cfg-primary">
                <option value="agy" ${cfg.primary_backend === "agy" ? "selected" : ""}>Antigravity (agy — sterilized home)</option>
                <option value="codex" ${cfg.primary_backend === "codex" ? "selected" : ""}>Codex (codex exec — read-only)</option>
              </select>
            </div>
            <div class="v4-field">
              <label for="cfg-primary-model">Primary Model</label>
              <input id="cfg-primary-model" type="text" value="${esc(cfg.primary_model || "gemini-4-hydrogen-medium")}" />
            </div>
            <div class="v4-field">
              <label for="cfg-fallback">Fallback CLI Backend</label>
              <select id="cfg-fallback">
                <option value="codex" ${cfg.fallback_backend === "codex" ? "selected" : ""}>Codex (codex exec)</option>
                <option value="agy" ${cfg.fallback_backend === "agy" ? "selected" : ""}>Antigravity (agy)</option>
              </select>
            </div>
            <div class="v4-field">
              <label for="cfg-fallback-model">Fallback Model</label>
              <input id="cfg-fallback-model" type="text" value="${esc(cfg.fallback_model || "gpt-6-luna")}" />
            </div>
            <div class="v4-field">
              <label for="cfg-reasoning">Fallback Reasoning Effort</label>
              <input id="cfg-reasoning" type="text" value="${esc(cfg.fallback_reasoning_effort || "medium")}" />
            </div>
          </div>

          <div class="v4-card">
            <h3>Clustering, Reminders &amp; Retention</h3>
            <div class="v4-field">
              <label for="cfg-cluster">Largest Cluster Threshold (tickets)</label>
              <input id="cfg-cluster" type="number" min="2" max="100" value="${Number(cfg.cluster_threshold ?? 7)}" />
            </div>
            <div class="v4-field">
              <label for="cfg-total">Scattered Pending-Done Safety Net (0 = disabled)</label>
              <input id="cfg-total" type="number" min="0" max="200" value="${Number(cfg.total_threshold ?? 12)}" />
            </div>
            <div class="v4-field">
              <label for="cfg-snooze">Snooze Delta (+N done tickets into largest cluster)</label>
              <input id="cfg-snooze" type="number" min="1" max="50" value="${Number(cfg.snooze_delta ?? 2)}" />
            </div>
            <div class="v4-field">
              <label for="cfg-timeout">CLI Timeout (seconds)</label>
              <input id="cfg-timeout" type="number" min="30" max="900" value="${Number(cfg.timeout_seconds ?? 150)}" />
            </div>
            <div class="v4-field">
              <label for="cfg-retention">Resolved Feedback Retention (days)</label>
              <input id="cfg-retention" type="number" min="7" max="3650" value="${Number(cfg.feedback_retention_days ?? 120)}" />
            </div>
            <label class="v4-checkbox-row">
              <input id="cfg-autotell" type="checkbox" ${cfg.auto_tell_on_bump !== false ? "checked" : ""} />
              Auto-run kb-doc TELL on version bump
            </label>
            <button type="button" id="v4-btn-save-cfg" class="v4-btn">Save Config</button>
            <div id="v4-cfg-status" class="v4-status-msg"></div>
          </div>
        </div>

        <div class="v4-card">
          <h3>Recent kb-doc Runs (${runs.length})</h3>
          ${runs.length ? runs.map((r) => `
            <div class="v4-run-row">
              [${esc(r.status)}] ${esc(r.mode)} · ${esc(r.version || "")} ${r.section ? "(" + esc(r.section) + ")" : ""} ·
              backend=${esc(r.backend_used || "—")}${r.fallback_used ? " (fallback)" : ""} · ${r.duration_ms || 0}ms
              ${r.error ? `<div class="v4-run-err">${esc(r.error)}</div>` : ""}
            </div>`).join("") : '<p class="v4-muted-sm">No kb-doc runs recorded yet.</p>'}
        </div>`;

      document.getElementById("v4-btn-save-cfg").addEventListener("click", async () => {
        const scope = document.getElementById("cfg-scope").value;
        const st = document.getElementById("v4-cfg-status");
        st.className = "v4-status-msg";
        st.textContent = "Saving...";
        try {
          await api("/api/doc/config", {
            method: "POST",
            body: JSON.stringify({
              scope,
              project: scope === "project" ? activeProject : null,
              config: {
                primary_backend: document.getElementById("cfg-primary").value,
                primary_model: document.getElementById("cfg-primary-model").value,
                fallback_backend: document.getElementById("cfg-fallback").value,
                fallback_model: document.getElementById("cfg-fallback-model").value,
                fallback_reasoning_effort: document.getElementById("cfg-reasoning").value,
                cluster_threshold: Number(document.getElementById("cfg-cluster").value),
                total_threshold: Number(document.getElementById("cfg-total").value),
                snooze_delta: Number(document.getElementById("cfg-snooze").value),
                timeout_seconds: Number(document.getElementById("cfg-timeout").value),
                feedback_retention_days: Number(document.getElementById("cfg-retention").value),
                auto_tell_on_bump: document.getElementById("cfg-autotell").checked,
              },
            }),
          });
          st.textContent = "Saved successfully.";
        } catch (err) {
          st.className = "v4-status-msg err";
          st.textContent = err.message;
        }
      });
    } catch (err) {
      el.innerHTML = `<div class="v4-card v4-status-msg err">Failed to load Config: ${esc(err.message)}</div>`;
    }
  }

  window.addEventListener("DOMContentLoaded", () => {
    ensureShellMounted();
    loadProjects();
  });
})();
