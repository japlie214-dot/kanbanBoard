(() => {
  "use strict";

  const STATUSES = ["backlog", "build", "verify", "done", "blocked"];
  const normalizeStatus = (s) => (s === "in-progress" ? "build" : s);
  const PAGE_SIZE = 40;
  const DEFAULT_APPROVER = "Boss";

  let boardState = { tickets: [], board_dir: "board/", total: 0 };
  let activeProject = "";
  let currentTicketRef = null;
  let currentDetail = null;
  let approvingRef = null;
  let approvingInFlight = false;
  let colLimits = {};
  let searchTimer = null;
  let toastTimer = null;

  const $ = (id) => document.getElementById(id);
  const csrfToken = () => {
    const meta = document.querySelector('meta[name="kb-csrf"]');
    return meta ? meta.getAttribute("content") || "" : "";
  };

  function showToast(message, kind = "ok", durationMs = 2400) {
    const el = $("kb-toast");
    if (!el) return;
    clearTimeout(toastTimer);
    el.textContent = message;
    el.className = `kb-toast ${kind === "err" ? "err" : "ok"}`;
    toastTimer = setTimeout(() => {
      el.classList.add("hidden");
    }, durationMs);
  }

  function clearButtonFeedback(btn, fallbackLabel) {
    if (!btn) return;
    if (btn._kbFbTimer) {
      clearTimeout(btn._kbFbTimer);
      btn._kbFbTimer = null;
    }
    btn.classList.remove("btn-feedback-ok", "btn-feedback-err");
    if (fallbackLabel !== undefined) {
      btn.textContent = fallbackLabel;
    } else if (btn.dataset.idleLabel) {
      btn.textContent = btn.dataset.idleLabel;
    }
  }

  function flashButtonFeedback(btn, label, kind = "ok", restoreLabel = null, durationMs = 1500) {
    if (!btn) return;
    if (!btn.dataset.idleLabel) {
      btn.dataset.idleLabel = restoreLabel || btn.textContent;
    }
    const targetIdle = restoreLabel || btn.dataset.idleLabel;
    btn.dataset.idleLabel = targetIdle;
    if (btn._kbFbTimer) clearTimeout(btn._kbFbTimer);
    btn.classList.remove("btn-feedback-ok", "btn-feedback-err");
    btn.classList.add(kind === "err" ? "btn-feedback-err" : "btn-feedback-ok");
    btn.textContent = label;
    btn._kbFbTimer = setTimeout(() => {
      btn.classList.remove("btn-feedback-ok", "btn-feedback-err");
      btn.textContent = targetIdle;
      btn._kbFbTimer = null;
    }, durationMs);
  }

  async function copyTextWithFallback(text) {
    if (!text) return { ok: false, error: "Nothing to copy" };
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      try {
        await navigator.clipboard.writeText(text);
        return { ok: true };
      } catch (err) {
        // Fall through to execCommand fallback if Clipboard API is blocked
        try {
          if (execCommandCopy(text)) return { ok: true };
        } catch (_) {}
        return { ok: false, error: String((err && err.message) || err || "Clipboard blocked") };
      }
    }
    try {
      if (execCommandCopy(text)) return { ok: true };
      return { ok: false, error: "Clipboard unavailable" };
    } catch (err) {
      return { ok: false, error: String((err && err.message) || err || "Clipboard unavailable") };
    }
  }

  function execCommandCopy(text) {
    if (typeof document.execCommand !== "function") return false;
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.className = "sr-copy-trap";
    document.body.appendChild(ta);
    ta.select();
    try {
      return Boolean(document.execCommand("copy"));
    } finally {
      document.body.removeChild(ta);
    }
  }

  async function handleCopyButton(btn, text, idleLabel, successToast) {
    const res = await copyTextWithFallback(text);
    if (res.ok) {
      flashButtonFeedback(btn, "Copied ✓", "ok", idleLabel, 1500);
      showToast(successToast || "Copied to clipboard", "ok");
    } else {
      flashButtonFeedback(btn, "Failed ✕", "err", idleLabel, 2000);
      showToast(`Copy failed: ${res.error || "permission denied"}`, "err", 3000);
    }
    return res.ok;
  }

  function fixMojibake(s) {
    return String(s ?? "")
      .replace(/â€“/g, "–")
      .replace(/â€”/g, "—")
      .replace(/â€™/g, "’")
      .replace(/â€œ/g, "“")
      .replace(/â€\u009d/g, "”")
      .replace(/â†’/g, "→");
  }

  function esc(str) {
    return fixMojibake(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function projectColorIdx(proj) {
    const s = String(proj || "");
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return h % 8;
  }

  function extractOwner(t) {
    if (typeof t.agent === "string" && t.agent.trim()) return t.agent.trim();
    const o = t.owner;
    if (typeof o === "string" && o.trim()) return o.trim();
    if (o && typeof o === "object") {
      for (const k of ["agent", "agent_id", "owner", "name", "id"]) {
        if (typeof o[k] === "string" && o[k].trim()) return o[k].trim();
      }
    }
    return "";
  }

  function avatarInitials(name) {
    if (!name) return "--";
    const parts = name.replace(/[^a-zA-Z0-9]+/g, " ").trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  }

  function isLeaseExpired(t) {
    if (typeof t.lease_expired === "boolean") return t.lease_expired;
    if (typeof t.lease_status === "string" && t.lease_status.toLowerCase().includes("expired")) return true;
    return false;
  }

  function filteredTickets() {
    const q = ($("f-q").value || "").trim().toLowerCase();
    const epic = $("f-epic").value;
    const hideDone = $("f-hidedone").checked;
    const showRetired = $("f-showretired") && $("f-showretired").checked;
    return boardState.tickets.filter((t) => {
      if (!showRetired && t.retired) return false;
      if (hideDone && t.status === "done") return false;
      if (activeProject && t.project !== activeProject) return false;
      if (epic && t.epic !== epic) return false;
      if (q) {
        const owner = extractOwner(t);
        const hay = `${t.ref || ""} ${t.id || ""} ${t.title || ""} ${owner} ${t.project || ""} ${t.epic || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  function renderProjectPills() {
    const counts = new Map();
    for (const t of boardState.tickets) {
      if (!t.project) continue;
      counts.set(t.project, (counts.get(t.project) || 0) + 1);
    }
    const projs = [...counts.keys()].sort();
    const html = [
      `<button type="button" class="proj-pill ${activeProject === "" ? "active" : ""}" data-proj="">All (${boardState.tickets.length})</button>`,
      ...projs.map((p) => {
        const idx = projectColorIdx(p);
        return `<button type="button" class="proj-pill ${activeProject === p ? "active" : ""}" data-proj="${esc(p)}">
          <span class="proj-dot pdot-${idx}"></span>${esc(p)} <span class="muted">${counts.get(p)}</span>
        </button>`;
      }),
    ].join("");
    $("project-pills").innerHTML = html;

    // Populate epic filter scoped to activeProject
    const epicSel = $("f-epic");
    const curEpic = epicSel.value;
    const epics = [...new Set(
      boardState.tickets
        .filter((t) => !activeProject || t.project === activeProject)
        .map((t) => t.epic)
        .filter(Boolean)
    )].sort();
    epicSel.innerHTML = '<option value="">All epics</option>' + epics.map((e) => `<option value="${esc(e)}">${esc(e)}</option>`).join("");
    epicSel.value = epics.includes(curEpic) ? curEpic : "";
  }

  function renderLeases() {
    const leased = boardState.tickets.filter((t) => extractOwner(t) && t.status !== "done");
    const active = leased.filter((t) => !isLeaseExpired(t));
    const stale = leased.filter((t) => isLeaseExpired(t));

    $("leases-summary").textContent = stale.length
      ? `${active.length} active · ${stale.length} stale`
      : `${active.length} active`;
    $("leases-popover-count").textContent = `${leased.length} total`;

    const list = $("leases-list");
    if (!leased.length) {
      list.innerHTML = '<div class="muted">No active agent leases.</div>';
      return;
    }
    list.innerHTML = leased
      .map((t) => {
        const exp = isLeaseExpired(t);
        const owner = extractOwner(t);
        return `<div class="lease-row ${exp ? "expired" : ""}" data-ref="${esc(t.ref)}">
          <span><strong>${esc(owner)}</strong> · ${esc(t.id)}</span>
          <span>${exp ? "Expired" : "Active"}</span>
        </div>`;
      })
      .join("");
  }

  function renderCardHtml(t) {
    const cidx = projectColorIdx(t.project);
    const total = Number(t.todo_total || 0);
    const done = Number(t.todo_done || 0);
    const owner = extractOwner(t);
    const exp = Boolean(owner && isLeaseExpired(t));
    const avatarCls = !owner ? "unassigned" : exp ? "stale" : "";
    const reviewBtn = t.status === "verify"
      ? `<button type="button" class="btn-review" data-approve="${esc(t.ref)}">Approve →</button>`
      : "";
    return `<article class="card p-${cidx} ${t.retired ? "retired" : ""} ${t.ref === currentTicketRef ? "selected" : ""}" data-ref="${esc(t.ref)}">
      <div class="card-top">
        <span class="proj-badge ptag-${cidx}">${esc(t.project)}</span>
        <span class="epic-badge">${esc(t.epic || "")}</span>
      </div>
      <div class="card-title">${esc(t.title)}</div>
      ${total > 0 ? `<progress class="card-progress" value="${done}" max="${total}" title="${done}/${total} checkpoints"></progress>` : ""}
      <div class="card-foot">
        <div class="card-foot-left">
          <span class="ref-chip">${esc(t.id)}</span>
          <span class="avatar ${avatarCls}" title="${esc(owner || "unassigned")}${exp ? " (lease expired)" : ""}">${esc(avatarInitials(owner))}</span>
          ${total > 0 ? `<span>${done}/${total}</span>` : ""}
          ${t.retired ? `<span class="retired-pill">RETIRED${t.days_until_purge != null ? ` · ${t.days_until_purge}d` : ""}</span>` : ""}
          ${t.is_rejected ? '<span class="rejected-pill">QA Reject</span>' : ""}
        </div>
        ${reviewBtn}
      </div>
    </article>`;
  }

  function renderColumnsHtml(items, scopeKey) {
    const hideDone = $("f-hidedone").checked;
    const cols = STATUSES.filter((s) => !(hideDone && s === "done"));
    return `<div class="board-columns">` + cols.map((status) => {
      const colItems = items.filter((t) => normalizeStatus(t.status) === status);
      const key = `${scopeKey}:${status}`;
      const limit = colLimits[key] || PAGE_SIZE;
      const shown = colItems.slice(0, limit);
      const remaining = colItems.length - shown.length;
      const cardsHtml = shown.map(renderCardHtml).join("");
      const moreHtml = remaining > 0
        ? `<button type="button" class="load-more-btn" data-more="${esc(key)}">Show ${Math.min(PAGE_SIZE, remaining)} more (${remaining} left)</button>`
        : "";
      return `<section class="column col-${status}">
        <div class="col-head"><span>${status}</span><span class="col-count">${colItems.length}</span></div>
        <div class="col-body">${cardsHtml || '<div class="muted">No tickets</div>'}${moreHtml}</div>
      </section>`;
    }).join("") + `</div>`;
  }

  function renderBoard() {
    const visible = filteredTickets();
    $("f-count").textContent = `${visible.length} / ${boardState.tickets.length}`;
    $("board-dir").textContent = boardState.board_dir || "board/";

    const swimlanes = $("f-swimlanes").checked;
    const canvas = $("board-canvas");

    if (!swimlanes) {
      canvas.innerHTML = renderColumnsHtml(visible, "flat");
      return;
    }

    const projs = [...new Set(visible.map((t) => t.project))].sort();
    if (!projs.length) {
      canvas.innerHTML = '<div class="muted">No matching tickets.</div>';
      return;
    }
    canvas.innerHTML = projs.map((p) => {
      const pItems = visible.filter((t) => t.project === p);
      const cidx = projectColorIdx(p);
      return `<div class="swimlane">
        <div class="swimlane-head p-${cidx}">
          <span class="proj-dot pdot-${cidx}"></span>
          <span>${esc(p)}</span>
          <span class="col-count">${pItems.length}</span>
        </div>
        ${renderColumnsHtml(pItems, "lane-" + p)}
      </div>`;
    }).join("");
  }

  /* Parse raw markdown ticket body into structured Jira-style sections */
  function parseMarkdownSections(rawBody) {
    const text = fixMojibake(rawBody || "").replace(/\r\n/g, "\n").trim();
    if (!text) return [];
    const sections = [];
    const lines = text.split("\n");
    let current = { title: "Summary", lines: [] };
    for (const line of lines) {
      const m = line.match(/^##\s+(.+?)\s*$/);
      if (m) {
        if (current.lines.join("\n").trim()) sections.push({ title: current.title, content: current.lines.join("\n").trim() });
        current = { title: m[1].trim(), lines: [] };
      } else {
        current.lines.push(line);
      }
    }
    if (current.lines.join("\n").trim()) {
      sections.push({ title: current.title, content: current.lines.join("\n").trim() });
    }
    return sections;
  }

  function parsePlanItemsFromMarkdown(md) {
    const items = [];
    for (const line of (md || "").split("\n")) {
      const m = line.match(/^\s*-\s*\[([ xX-])\]\s*(.+)$/);
      if (!m) continue;
      const mark = m[1].toLowerCase();
      const raw = m[2].trim();
      const idMatch = raw.match(/^([A-Za-z0-9_-]+)\s+(.*)$/);
      const id = idMatch ? idMatch[1] : "";
      let rest = idMatch ? idMatch[2] : raw;
      const tags = [];
      rest = rest.replace(/\[([^\]]+)\]/g, (_, tag) => {
        tags.push(tag.trim());
        return "";
      }).replace(/\s{2,}/g, " ").trim();
      items.push({
        id,
        state: mark === "x" ? "done" : mark === "-" ? "skipped" : "open",
        text: rest || raw,
        tags,
      });
    }
    return items;
  }

  function renderPlanSection(t, planMd) {
    const readySet = new Set(Array.isArray(t.ready_nodes) ? t.ready_nodes : []);
    let rows = [];
    if (Array.isArray(t.dag_nodes) && t.dag_nodes.length) {
      rows = t.dag_nodes.map((n) => {
        const tags = [];
        if (n.is_start) tags.push("START");
        if (n.lane) tags.push(`lane:${n.lane}`);
        if (Array.isArray(n.after) && n.after.length) tags.push(`after:${n.after.join(",")}`);
        if (n.acceptance) tags.push(`ACCEPTANCE:${n.acceptance}`);
        if (n.optional) tags.push("optional");
        return {
          id: n.id || "",
          state: n.checked || n.status === "done" ? "done" : n.skipped || n.status === "skipped" ? "skipped" : "open",
          text: String(n.text || n.label || "").replace(/\[[^\]]+\]/g, "").replace(/\s{2,}/g, " ").trim(),
          tags,
        };
      });
    } else {
      rows = parsePlanItemsFromMarkdown(planMd);
    }

    if (!rows.length) {
      return `<div class="spec-section"><div class="spec-head"><h4 class="spec-title">Execution Plan</h4></div><p class="muted">No plan steps defined.</p></div>`;
    }

    const doneCnt = rows.filter((r) => r.state === "done").length;
    const htmlRows = rows.map((r) => {
      const icon = r.state === "done" ? "✓" : r.state === "skipped" ? "⊘" : "○";
      const isReady = r.id && readySet.has(r.id) && r.state === "open";
      const tagPills = [
        r.id ? `<span class="ptag">${esc(r.id)}</span>` : "",
        isReady ? `<span class="ptag ptag-ready">READY</span>` : "",
        ...r.tags.map((tg) => {
          const cls = /MANDATORY/i.test(tg) ? "ptag ptag-mand" : "ptag";
          return `<span class="${cls}">${esc(tg)}</span>`;
        }),
      ].filter(Boolean).join("");
      return `<div class="plan-row ${r.state}">
        <span class="plan-icon ${r.state}">${icon}</span>
        <div class="plan-main">
          <div class="plan-text">${esc(r.text)}</div>
          ${tagPills ? `<div class="plan-tags">${tagPills}</div>` : ""}
        </div>
      </div>`;
    }).join("");

    return `<div class="spec-section">
      <div class="spec-head">
        <h4 class="spec-title">Execution Plan (${doneCnt} / ${rows.length})</h4>
      </div>
      <progress class="card-progress" value="${doneCnt}" max="${rows.length}"></progress>
      <div class="plan-list">${htmlRows}</div>
    </div>`;
  }

  function renderTicketDetail(t) {
    currentDetail = t;
    const cidx = projectColorIdx(t.project);
    $("drawer").classList.remove("hidden");
    $("d-breadcrumb").innerHTML = `<span class="proj-badge ptag-${cidx}">${esc(t.project)}</span> <span>›</span> <span>${esc(t.epic || "default")}</span>`;
    $("d-ref").textContent = t.id || t.ref;
    $("d-status").textContent = t.status;
    $("d-title").textContent = fixMojibake(t.title || "");
    $("d-rejected-pill").classList.toggle("hidden", !t.is_rejected);
    $("btn-drawer-approve").classList.toggle("hidden", t.status !== "verify");
    const rbtn = $("btn-drawer-retire");
    if (rbtn) {
      rbtn.classList.toggle("hidden", t.status === "done");
      const retLabel = t.retired ? "Restore" : "Retire";
      rbtn.dataset.idleLabel = retLabel;
      clearButtonFeedback(rbtn, retLabel);
    }
    clearButtonFeedback($("btn-copy-ref"), "Copy Ref");

    const owner = extractOwner(t) || "unassigned";
    const lease = t.lease_status || (t.status === "done" ? "Certified done" : "unclaimed");
    $("d-meta-grid").innerHTML = `
      <div class="meta-item"><span class="meta-k">Owner</span><span class="meta-v">${esc(owner)}</span></div>
      <div class="meta-item"><span class="meta-k">Lease</span><span class="meta-v">${esc(lease)}</span></div>
      <div class="meta-item"><span class="meta-k">Since</span><span class="meta-v">${esc(t.since || "—")}</span></div>
    `;

    // Build structured Overview sections (zero lazy raw dump!)
    const sections = parseMarkdownSections(t.body);
    let planMd = "";
    const parts = [];

    for (const sec of sections) {
      if (/^plan\b/i.test(sec.title)) {
        planMd = sec.content;
        continue;
      }
      if (/^execution\s+log$/i.test(sec.title)) {
        continue; // Shown in Activity & QA tab
      }
      if (/^prove$/i.test(sec.title)) {
        const cleanCmd = sec.content.replace(/^```[a-z]*\n?/i, "").replace(/\n?```$/i, "").trim();
        parts.push(`<div class="spec-section">
          <div class="spec-head">
            <h4 class="spec-title">Prove Command</h4>
            <button type="button" class="btn-ghost" data-copy-prove="${esc(cleanCmd)}">Copy</button>
          </div>
          <pre class="code-block">${esc(cleanCmd)}</pre>
        </div>`);
        continue;
      }
      parts.push(`<div class="spec-section">
        <div class="spec-head"><h4 class="spec-title">${esc(sec.title)}</h4></div>
        <p class="spec-prose">${esc(sec.content)}</p>
      </div>`);
    }

    parts.push(renderPlanSection(t, planMd));

    const files = Array.isArray(t.files) ? t.files : [];
    const fileLabels = files.map((f) => typeof f === "string" ? f : (f && (f.path || f.name)) ? String(f.path || f.name) : JSON.stringify(f));
    parts.push(`<div class="spec-section">
      <div class="spec-head"><h4 class="spec-title">Touched Files (${fileLabels.length})</h4></div>
      ${fileLabels.length ? `<div class="file-chips">${fileLabels.map((f) => `<span class="file-chip">${esc(f)}</span>`).join("")}</div>` : '<p class="muted">No files declared yet.</p>'}
    </div>`);

    $("tab-overview").innerHTML = parts.join("");

    // Activity & QA tab
    const logs = Array.isArray(t.execution_log) ? t.execution_log : [];
    $("d-audit-count").textContent = String(logs.length);
    const logLines = logs.map((entry) => {
      if (typeof entry === "string") return entry;
      if (entry && typeof entry === "object") {
        const ts = entry.timestamp || entry.ts || "";
        const node = entry.node || entry.id || "";
        const proof = entry.proof || entry.message || entry.raw || JSON.stringify(entry);
        return [ts, node, proof].filter(Boolean).join(" | ");
      }
      return String(entry);
    });
    $("tab-activity").innerHTML = `
      <div class="spec-section">
        <div class="spec-head"><h4 class="spec-title">QA / Status Note</h4></div>
        <pre class="code-block">${esc(t.note || "None")}</pre>
      </div>
      <div class="spec-section">
        <div class="spec-head"><h4 class="spec-title">Execution Log (${logLines.length})</h4></div>
        ${logLines.length ? `<pre class="code-block">${esc(logLines.join("\n"))}</pre>` : '<p class="muted">No execution log entries yet.</p>'}
      </div>
    `;

    // Docs tab
    $("tab-docs").innerHTML = `
      <div class="spec-section">
        <div class="spec-head"><h4 class="spec-title">Epic Spec</h4></div>
        <p class="spec-prose">${esc(t.epic_doc || "No epic.md available.")}</p>
      </div>
      <div class="spec-section">
        <div class="spec-head"><h4 class="spec-title">Project Charter</h4></div>
        <p class="spec-prose">${esc(t.project_doc || "No project.md available.")}</p>
      </div>
    `;
  }

  async function openDetail(ref) {
    currentTicketRef = ref;
    renderBoard();
    try {
      const resp = await fetch(`/api/ticket?ref=${encodeURIComponent(ref)}`, { cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (data.ticket) renderTicketDetail(data.ticket);
    } catch (err) {
      console.error("openDetail failed:", err);
    }
  }

  function closeDetail() {
    currentTicketRef = null;
    currentDetail = null;
    $("drawer").classList.add("hidden");
    renderBoard();
  }

  function resetSlider() {
    const slider = $("slide-approve");
    slider.value = "0";
    slider.disabled = false;
    $("slide-pct").textContent = "0%";
    $("slide-label-text").textContent = "Slide right to approve →";
  }

  function openApproveModal(ref) {
    approvingRef = ref;
    approvingInFlight = false;
    $("m-ref").textContent = ref;
    $("m-approver").value = DEFAULT_APPROVER;
    $("m-reason").value = "";
    $("m-error").classList.add("hidden");
    $("m-error").textContent = "";
    resetSlider();
    $("approve-modal-overlay").classList.remove("hidden");
    $("m-reason").focus();
  }

  function closeApproveModal() {
    approvingRef = null;
    approvingInFlight = false;
    $("approve-modal-overlay").classList.add("hidden");
    resetSlider();
  }

  async function triggerApproveFromSlide() {
    if (approvingInFlight) return;
    const targetRef = approvingRef;
    if (!targetRef) return;

    const approver = $("m-approver").value.trim();
    const reason = $("m-reason").value.trim();
    const errEl = $("m-error");
    const slider = $("slide-approve");

    if (approver.length < 2 || reason.length < 10) {
      errEl.textContent = "Approver (min 2 chars) and reason (min 10 chars) are required before sliding.";
      errEl.classList.remove("hidden");
      resetSlider();
      return;
    }

    approvingInFlight = true;
    slider.disabled = true;
    $("slide-label-text").textContent = "Confirm in Windows OS popup...";
    errEl.classList.add("hidden");

    try {
      const resp = await fetch("/api/ticket/manual-approve", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Kanban-CSRF": csrfToken(),
        },
        body: JSON.stringify({ ref: targetRef, approver, reason }),
      });
      const data = await resp.json();
      if (!resp.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${resp.status}`);
      }
      closeApproveModal();
      await refreshBoard();
      if (currentTicketRef === targetRef) {
        await openDetail(targetRef);
      }
    } catch (err) {
      errEl.textContent = String(err.message || err);
      errEl.classList.remove("hidden");
      approvingInFlight = false;
      resetSlider();
    }
  }

  async function refreshBoard(opts = {}) {
    const manual = Boolean(opts && opts.manual);
    const rbtn = $("btn-refresh");
    if (manual && rbtn) {
      rbtn.classList.add("btn-busy");
      rbtn.disabled = true;
    }
    try {
      const resp = await fetch("/api/board?summary=1", { cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const payload = await resp.json();
      boardState = {
        tickets: Array.isArray(payload.tickets) ? payload.tickets : [],
        board_dir: payload.board_dir || "board/",
        total: payload.total || 0,
      };
      renderProjectPills();
      renderLeases();
      renderBoard();
      if (currentTicketRef) await openDetail(currentTicketRef);
      if (manual) {
        flashButtonFeedback(rbtn, "✓", "ok", "↻", 1000);
        showToast(`Board refreshed (${boardState.tickets.length} tickets)`, "ok");
      }
    } catch (err) {
      console.error("refreshBoard failed:", err);
      if (manual) {
        flashButtonFeedback(rbtn, "!", "err", "↻", 1800);
        showToast(`Refresh failed: ${String((err && err.message) || err)}`, "err", 3000);
      }
    } finally {
      if (manual && rbtn) {
        rbtn.classList.remove("btn-busy");
        rbtn.disabled = false;
      }
    }
  }

  function connectSSE() {
    const es = new EventSource("/events");
    es.onmessage = () => refreshBoard();
    es.onerror = () => {
      $("conn-pill").innerHTML = '<span class="dot dot-stale"></span> offline';
    };
    es.onopen = () => {
      $("conn-pill").innerHTML = '<span class="dot dot-live"></span> live';
    };
  }

  function wireEvents() {
    $("f-q").addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(renderBoard, 150);
    });
    $("f-epic").addEventListener("change", renderBoard);
    $("f-swimlanes").addEventListener("change", () => {
      try { localStorage.setItem("kb-swimlanes", $("f-swimlanes").checked ? "1" : "0"); } catch (_) {}
      renderBoard();
    });
    $("f-hidedone").addEventListener("change", () => {
      try { localStorage.setItem("kb-hidedone", $("f-hidedone").checked ? "1" : "0"); } catch (_) {}
      renderBoard();
    });
    $("btn-refresh").addEventListener("click", () => refreshBoard({ manual: true }));

    $("project-pills").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-proj]");
      if (!btn) return;
      activeProject = btn.dataset.proj || "";
      renderProjectPills();
      renderBoard();
    });

    $("btn-theme").addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme") || "dark";
      const next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("kb-theme", next); } catch (_) {}
      flashButtonFeedback($("btn-theme"), "◐", "ok", "◐", 700);
      showToast(`Theme: ${next === "dark" ? "Dark" : "Light"}`, "ok", 1400);
    });

    $("btn-leases").addEventListener("click", () => {
      const pop = $("leases-popover");
      const hidden = pop.classList.toggle("hidden");
      $("btn-leases").setAttribute("aria-expanded", String(!hidden));
    });

    $("leases-list").addEventListener("click", (e) => {
      const row = e.target.closest("[data-ref]");
      if (row) {
        $("leases-popover").classList.add("hidden");
        openDetail(row.dataset.ref);
      }
    });

    $("board-canvas").addEventListener("click", (e) => {
      const moreBtn = e.target.closest("[data-more]");
      if (moreBtn) {
        const key = moreBtn.dataset.more;
        colLimits[key] = (colLimits[key] || PAGE_SIZE) + PAGE_SIZE;
        renderBoard();
        return;
      }
      const approveBtn = e.target.closest("[data-approve]");
      if (approveBtn) {
        e.stopPropagation();
        openApproveModal(approveBtn.dataset.approve);
        return;
      }
      const card = e.target.closest("[data-ref]");
      if (card) openDetail(card.dataset.ref);
    });

    $("tab-overview").addEventListener("click", (e) => {
      const copyBtn = e.target.closest("[data-copy-prove]");
      if (copyBtn) {
        handleCopyButton(copyBtn, copyBtn.dataset.copyProve || "", "Copy", "Copied prove command");
      }
    });

    $("btn-close-drawer").addEventListener("click", closeDetail);
    if ($("f-showretired")) $("f-showretired").addEventListener("change", renderBoard);
    if ($("btn-drawer-retire")) {
      $("btn-drawer-retire").addEventListener("click", async () => {
        const rbtn = $("btn-drawer-retire");
        if (!currentTicketRef || !currentDetail) return;
        const targetRef = currentTicketRef;
        const isRet = Boolean(currentDetail.retired);
        const idleLabel = isRet ? "Restore" : "Retire";
        let reason = "";
        if (!isRet) {
          reason = window.prompt("Retire reason (moves to backlog, auto-purges after 120d):", "") || "";
          if (reason.trim().length < 5) {
            if (reason.length > 0) {
              flashButtonFeedback(rbtn, "Min 5 chars", "err", idleLabel, 1800);
              showToast("Retire cancelled: reason must be at least 5 characters", "err", 2500);
            }
            return;
          }
        }
        rbtn.disabled = true;
        rbtn.classList.add("btn-busy");
        rbtn.textContent = isRet ? "Restoring..." : "Retiring...";
        try {
          const resp = await fetch(isRet ? "/api/ticket/restore" : "/api/ticket/retire", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Kanban-CSRF": csrfToken() },
            body: JSON.stringify({ ref: targetRef, reason: reason.trim() }),
          });
          const data = await resp.json();
          if (!resp.ok || data.ok === false) throw new Error(data.error || `HTTP ${resp.status}`);
          await refreshBoard();
          flashButtonFeedback(rbtn, isRet ? "Restored ✓" : "Retired ✓", "ok", isRet ? "Retire" : "Restore", 1500);
          showToast(isRet ? `Restored ${targetRef}` : `Retired ${targetRef} to backlog`, "ok");
        } catch (err) {
          const msg = String((err && err.message) || err);
          flashButtonFeedback(rbtn, "Failed ✕", "err", idleLabel, 2000);
          showToast(`${idleLabel} failed: ${msg}`, "err", 3200);
        } finally {
          rbtn.disabled = false;
          rbtn.classList.remove("btn-busy");
        }
      });
    }
    $("btn-drawer-approve").addEventListener("click", () => {
      if (currentTicketRef) openApproveModal(currentTicketRef);
    });
    $("btn-copy-ref").addEventListener("click", () => {
      const btn = $("btn-copy-ref");
      if (!currentTicketRef) {
        flashButtonFeedback(btn, "No ref", "err", "Copy Ref", 1500);
        showToast("No ticket selected to copy", "err");
        return;
      }
      handleCopyButton(btn, currentTicketRef, "Copy Ref", `Copied ref: ${currentTicketRef}`);
    });

    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
        btn.classList.add("active");
        const panel = $("tab-" + btn.dataset.tab);
        if (panel) panel.classList.remove("hidden");
      });
    });

    $("btn-close-modal").addEventListener("click", closeApproveModal);
    $("btn-cancel-approve").addEventListener("click", closeApproveModal);
    $("approve-form").addEventListener("submit", (e) => e.preventDefault());

    // Slide-to-Approve interaction (anti-misclick)
    const slider = $("slide-approve");
    slider.addEventListener("input", () => {
      const v = Number(slider.value);
      $("slide-pct").textContent = `${v}%`;
      if (v >= 92) {
        slider.value = "100";
        $("slide-pct").textContent = "100%";
        triggerApproveFromSlide();
      }
    });
    const snapBack = () => {
      if (!approvingInFlight && Number(slider.value) < 92) {
        resetSlider();
      }
    };
    slider.addEventListener("change", snapBack);
    slider.addEventListener("pointerup", snapBack);

    document.addEventListener("keydown", (e) => {
      if (e.target.matches("input, textarea, select")) return;
      const ws = document.querySelector("main.workspace");
      if (ws && ws.classList.contains("hidden")) return;
      if (e.key === "/") { e.preventDefault(); $("f-q").focus(); }
      if (e.key === "t") { $("btn-theme").click(); }
      if (e.key === "r") { refreshBoard({ manual: true }); }
      if (e.key === "Escape") { closeApproveModal(); closeDetail(); }
    });

    window.addEventListener("kb:open-ticket", (e) => {
      const ref = e && e.detail && e.detail.ref;
      if (ref) openDetail(ref);
    });
  }

  try {
    const savedTheme = localStorage.getItem("kb-theme");
    if (savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);
    if (localStorage.getItem("kb-swimlanes") === "1") $("f-swimlanes").checked = true;
    if (localStorage.getItem("kb-hidedone") === "1") $("f-hidedone").checked = true;
  } catch (_) {}

  wireEvents();
  refreshBoard();
  connectSSE();
})();
