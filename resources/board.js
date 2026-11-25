(() => {
  "use strict";

  const STATUSES = ["backlog", "in-progress", "verify", "done", "blocked"];
  let boardData = { projects: [], tickets: [], board_dir: "board/" };
  let currentTicketRef = null;
  let approvingRef = null;

  const $ = (id) => document.getElementById(id);
  const csrfToken = () => {
    const meta = document.querySelector('meta[name="kb-csrf"]');
    return meta ? meta.getAttribute("content") || "" : "";
  };

  function esc(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function flattenTickets(payload) {
    if (Array.isArray(payload.tickets)) return payload.tickets;
    const boardObj = payload.board || payload;
    const projects = boardObj.projects || payload.projects || [];
    const out = [];

    for (const proj of projects) {
      const projName = proj.slug || proj.name || "";
      const projDoc = proj.doc || proj.charter || proj.body || "";

      // kb.py stores tickets directly on proj.tickets
      const tickets = Array.isArray(proj.tickets) ? proj.tickets : [];
      for (const t of tickets) {
        const ref = t.ref || t.reference || `${projName}/${t.epic || "core"}/${t.id}`;
        const ownerObj = typeof t.owner === "object" && t.owner !== null ? t.owner : null;
        const agent = (ownerObj ? ownerObj.agent : t.owner) || t.agent || "";
        const leaseExp = (ownerObj ? ownerObj.lease_expires : null) || t.lease_expires || t.lease_until;

        // Find epic doc if available
        let epicDoc = t.epic_doc || "";
        if (!epicDoc && Array.isArray(proj.epics)) {
          const ep = proj.epics.find((e) => e.slug === t.epic || e.name === t.epic);
          if (ep) epicDoc = ep.doc || ep.spec || ep.body || "";
        }

        // Compute DAG progress counts
        const nodes = Array.isArray(t.dag_nodes) ? t.dag_nodes : (Array.isArray(t.nodes) ? t.nodes : []);
        const totalNodes = t.todo_total ?? nodes.length;
        const doneNodes = t.todo_done ?? nodes.filter((n) => n.checked || n.status === "done").length;

        out.push({
          ...t,
          ref,
          agent,
          lease_expires: leaseExp,
          project: t.project || projName,
          epic: t.epic || "",
          project_doc: projDoc,
          epic_doc: epicDoc,
          todo_total: totalNodes,
          todo_done: doneNodes,
        });
      }

      // Backward-compatibility: if tickets are nested inside epics
      for (const epic of proj.epics || []) {
        for (const t of epic.tickets || []) {
          const ref = t.ref || t.reference || `${projName}/${epic.slug || epic.name}/${t.id}`;
          const ownerObj = typeof t.owner === "object" && t.owner !== null ? t.owner : null;
          const agent = (ownerObj ? ownerObj.agent : t.owner) || t.agent || "";
          const leaseExp = (ownerObj ? ownerObj.lease_expires : null) || t.lease_expires || t.lease_until;

          const nodes = Array.isArray(t.dag_nodes) ? t.dag_nodes : (Array.isArray(t.nodes) ? t.nodes : []);
          const totalNodes = t.todo_total ?? nodes.length;
          const doneNodes = t.todo_done ?? nodes.filter((n) => n.checked || n.status === "done").length;

          out.push({
            ...t,
            ref,
            agent,
            lease_expires: leaseExp,
            project: t.project || projName,
            epic: t.epic || epic.slug || epic.name || "",
            project_doc: projDoc,
            epic_doc: epic.doc || epic.spec || epic.body || "",
            todo_total: totalNodes,
            todo_done: doneNodes,
          });
        }
      }
    }
    return out;
  }

  function isLeaseExpired(t) {
    if (typeof t.lease_expired === "boolean") return t.lease_expired;
    const exp = t.lease_expires || t.lease_until;
    if (!exp) return false;
    const ts = Date.parse(exp);
    return !Number.isNaN(ts) && ts < Date.now();
  }

  function filteredTickets() {
    const q = ($("f-q").value || "").trim().toLowerCase();
    const proj = $("f-project").value;
    const epic = $("f-epic").value;
    const hideDone = $("f-hidedone").checked;
    return boardData.tickets.filter((t) => {
      if (hideDone && t.status === "done") return false;
      if (proj && t.project !== proj) return false;
      if (epic && t.epic !== epic) return false;
      if (q) {
        const hay = `${t.ref || ""} ${t.id || ""} ${t.title || ""} ${t.agent || t.owner || ""} ${t.note || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  function populateFilters() {
    const projSel = $("f-project");
    const epicSel = $("f-epic");
    const curProj = projSel.value;
    const curEpic = epicSel.value;

    const projs = [...new Set(boardData.tickets.map((t) => t.project).filter(Boolean))].sort();
    projSel.innerHTML = '<option value="">All projects</option>' + projs.map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join("");
    projSel.value = projs.includes(curProj) ? curProj : "";

    const epics = [...new Set(
      boardData.tickets
        .filter((t) => !projSel.value || t.project === projSel.value)
        .map((t) => t.epic)
        .filter(Boolean)
    )].sort();
    epicSel.innerHTML = '<option value="">All epics</option>' + epics.map((e) => `<option value="${esc(e)}">${esc(e)}</option>`).join("");
    epicSel.value = epics.includes(curEpic) ? curEpic : "";
  }

  function renderLeases() {
    const leased = boardData.tickets.filter((t) => (t.agent || t.owner) && t.status !== "done");
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
        return `<div class="lease-row ${exp ? "expired" : ""}" data-ref="${esc(t.ref)}">
          <span><strong>${esc(t.agent || t.owner)}</strong> · ${esc(t.id || t.ref)}</span>
          <span>${exp ? "Expired" : "Active"}</span>
        </div>`;
      })
      .join("");
  }

  function renderBoard() {
    const all = boardData.tickets;
    const visible = filteredTickets();
    $("f-count").textContent = `${visible.length} / ${all.length}`;
    $("board-dir").textContent = boardData.board_dir || "board/";

    const hideDone = $("f-hidedone").checked;
    const cols = STATUSES.filter((s) => !(hideDone && s === "done"));

    const container = $("board-columns");
    container.innerHTML = cols
      .map((status) => {
        const items = visible.filter((t) => t.status === status);
        const cardsHtml = items
          .map((t) => {
            const total = t.todo_total || (Array.isArray(t.nodes) ? t.nodes.length : 0);
            const done = t.todo_done || (Array.isArray(t.nodes) ? t.nodes.filter((n) => n.checked).length : 0);
            const pct = total > 0 ? Math.round((done / total) * 100) : 0;
            const agent = t.agent || t.owner || "";
            const exp = agent && isLeaseExpired(t);
            const approveBtn = status === "verify"
              ? `<button type="button" class="btn-approve card-approve-btn" data-approve="${esc(t.ref)}">✓ Approve</button>`
              : "";
            return `<article class="card ${t.ref === currentTicketRef ? "selected" : ""}" data-ref="${esc(t.ref)}">
              <div class="card-top">
                <span class="ref-chip">${esc(t.id || t.ref)}</span>
                <span class="proj-tag">${esc(t.project)}${t.epic ? " / " + esc(t.epic) : ""}</span>
              </div>
              <div class="card-title">${esc(t.title)}</div>
              ${total > 0 ? `<div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>` : ""}
              <div class="card-foot">
                <span>${agent ? esc(agent) + (exp ? " (stale)" : "") : "unassigned"}${total > 0 ? ` · ${done}/${total}` : ""}</span>
                ${approveBtn}
              </div>
            </article>`;
          })
          .join("");

        return `<section class="column col-${status}">
          <div class="col-head"><span>${status}</span><span>${items.length}</span></div>
          <div class="col-body">${cardsHtml || '<div class="muted" style="padding:8px 4px;font-size:12px;">No tickets</div>'}</div>
        </section>`;
      })
      .join("");
  }

  function openDetail(ref) {
    const t = boardData.tickets.find((x) => x.ref === ref);
    if (!t) return;
    currentTicketRef = ref;
    $("drawer").classList.remove("hidden");
    $("d-breadcrumb").textContent = `${t.project || ""} › ${t.epic || ""}`;
    $("d-ref").textContent = t.id || t.ref;
    $("d-status").textContent = t.status;
    $("d-title").textContent = t.title || "";

    const approveBtn = $("btn-drawer-approve");
    if (t.status === "verify") {
      approveBtn.classList.remove("hidden");
    } else {
      approveBtn.classList.add("hidden");
    }

    const agent = t.agent || t.owner || "unassigned";
    const exp = agent !== "unassigned" && isLeaseExpired(t);
    $("d-lease-bar").innerHTML = `<span>Owner: <strong>${esc(agent)}</strong></span><span>${exp ? "Lease expired" : (t.status === "done" ? "Certified done" : "Active")}</span>`;

    // Overview tab (always default — never an empty DAG void)
    const files = Array.isArray(t.files) ? t.files : [];
    const bodyText = t.body || t.spec || t.content || "(No ticket body)";
    $("tab-overview").innerHTML = `
      <h4>Ticket Spec &amp; Plan</h4>
      <div class="mono-pre">${esc(bodyText)}</div>
      <h4>Touched Files (${files.length})</h4>
      ${files.length ? `<div class="mono-pre">${files.map(esc).join("\n")}</div>` : '<p class="muted">No files declared yet.</p>'}
    `;

    // Activity & QA tab
    const logs = Array.isArray(t.audit) ? t.audit : Array.isArray(t.execution_log) ? t.execution_log : [];
    $("d-audit-count").textContent = String(logs.length);
    $("tab-activity").innerHTML = `
      <h4>QA / Status Note</h4>
      <div class="mono-pre">${esc(t.note || t.qa_note || "None")}</div>
      <h4>Execution &amp; Audit Stream (${logs.length})</h4>
      ${logs.length ? `<div class="mono-pre">${logs.map((l) => esc(typeof l === "string" ? l : JSON.stringify(l))).join("\n")}</div>` : '<p class="muted">No audit entries yet.</p>'}
    `;

    // Docs tab
    $("tab-docs").innerHTML = `
      <h4>Epic Spec</h4>
      <div class="mono-pre">${esc(t.epic_doc || "No epic.md loaded.")}</div>
      <h4>Project Charter</h4>
      <div class="mono-pre">${esc(t.project_doc || "No project.md loaded.")}</div>
    `;

    renderBoard();
  }

  function closeDetail() {
    currentTicketRef = null;
    $("drawer").classList.add("hidden");
    renderBoard();
  }

  function openApproveModal(ref) {
    approvingRef = ref;
    $("m-ref").textContent = ref;
    $("m-error").classList.add("hidden");
    $("m-error").textContent = "";
    $("approve-modal-overlay").classList.remove("hidden");
    $("m-approver").focus();
  }

  function closeApproveModal() {
    approvingRef = null;
    $("approve-modal-overlay").classList.add("hidden");
    $("approve-form").reset();
  }

  async function handleApproveSubmit(e) {
    e.preventDefault();
    const targetRef = approvingRef; // Capture BEFORE closeApproveModal() resets approvingRef
    if (!targetRef) return;

    const approver = $("m-approver").value.trim();
    const reason = $("m-reason").value.trim();
    const errEl = $("m-error");
    const submitBtn = $("btn-submit-approve");

    if (approver.length < 2 || reason.length < 10) {
      errEl.textContent = "Approver (min 2 chars) and reason (min 10 chars) are required.";
      errEl.classList.remove("hidden");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Confirm in OS popup...";
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
        openDetail(targetRef);
      }
    } catch (err) {
      errEl.textContent = String(err.message || err);
      errEl.classList.remove("hidden");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Confirm & Approve";
    }
  }

  async function refreshBoard() {
    try {
      const resp = await fetch("/api/board", { cache: "no-store" });
      if (!resp.ok) return;
      const payload = await resp.json();
      const boardObj = payload.board || payload;
      boardData = {
        ...payload,
        board_dir: boardObj.board_dir || payload.board_dir || "board/",
        projects: boardObj.projects || payload.projects || [],
        tickets: flattenTickets(payload),
      };
      if ($("board-dir")) $("board-dir").textContent = boardData.board_dir;
      populateFilters();
      renderLeases();
      renderBoard();
      if (currentTicketRef) openDetail(currentTicketRef);
    } catch (err) {
      console.error("[kanban] refreshBoard error:", err);
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
    $("f-q").addEventListener("input", renderBoard);
    $("f-project").addEventListener("change", () => { populateFilters(); renderBoard(); });
    $("f-epic").addEventListener("change", renderBoard);
    $("f-hidedone").addEventListener("change", renderBoard);
    $("btn-refresh").addEventListener("click", refreshBoard);

    $("btn-theme").addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme") || "dark";
      const next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("kb-theme", next); } catch (_) {}
    });

    $("btn-leases").addEventListener("click", () => {
      const pop = $("leases-popover");
      const open = pop.classList.toggle("hidden");
      $("btn-leases").setAttribute("aria-expanded", String(!open));
    });

    $("leases-list").addEventListener("click", (e) => {
      const row = e.target.closest("[data-ref]");
      if (row) {
        $("leases-popover").classList.add("hidden");
        openDetail(row.dataset.ref);
      }
    });

    $("board-columns").addEventListener("click", (e) => {
      const approveBtn = e.target.closest("[data-approve]");
      if (approveBtn) {
        e.stopPropagation();
        openApproveModal(approveBtn.dataset.approve);
        return;
      }
      const card = e.target.closest("[data-ref]");
      if (card) openDetail(card.dataset.ref);
    });

    $("btn-close-drawer").addEventListener("click", closeDetail);
    $("btn-drawer-approve").addEventListener("click", () => {
      if (currentTicketRef) openApproveModal(currentTicketRef);
    });
    $("btn-copy-ref").addEventListener("click", () => {
      if (currentTicketRef && navigator.clipboard) {
        navigator.clipboard.writeText(currentTicketRef);
      }
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
    $("approve-form").addEventListener("submit", handleApproveSubmit);

    document.addEventListener("keydown", (e) => {
      if (e.target.matches("input, textarea, select")) return;
      if (e.key === "/") { e.preventDefault(); $("f-q").focus(); }
      if (e.key === "t") { $("btn-theme").click(); }
      if (e.key === "r") { refreshBoard(); }
      if (e.key === "Escape") { closeApproveModal(); closeDetail(); }
    });
  }

  try {
    const saved = localStorage.getItem("kb-theme");
    if (saved) document.documentElement.setAttribute("data-theme", saved);
  } catch (_) {}

  wireEvents();
  refreshBoard();
  connectSSE();
})();
