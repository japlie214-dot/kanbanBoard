/* doc_shared/shell.js — KanbanBoard v4.0.1 Modular Living Doc Runtime
 * Strict-CSP compliant: zero inline styles, zero blob: URLs (uses /api/doc/show.js),
 * no blocking dialogs. Includes collapsible subsections, instant search (/), keyboard nav,
 * footer drift pills, clickable ticket chips, async queue status, rollback, and exports.
 */
(function (global) {
  "use strict";

  function csrfToken() {
    const meta = document.querySelector('meta[name="kb-csrf"]');
    return meta ? meta.getAttribute("content") || "" : "";
  }

  async function apiJson(url, opts) {
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

  function mountDocViewer(rootEl, project) {
    let manifest = null;
    let activeSlug = null;
    let activeMode = "tell";
    let docTheme = "light";
    let searchQuery = "";
    let collapsedGroups = {};
    let activeStage = null;
    let pollTimer = null;

    function destroyStage() {
      if (activeStage && typeof activeStage.destroy === "function") {
        try { activeStage.destroy(); } catch (_) {}
      }
      activeStage = null;
    }

    function stopPoll() {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    function showBanner(msg, isErr) {
      const el = rootEl.querySelector("#kb-doc-banner");
      if (!el) return;
      if (!msg) {
        el.classList.add("kb-doc-hidden");
        el.textContent = "";
        return;
      }
      el.classList.remove("kb-doc-hidden");
      el.classList.toggle("err", Boolean(isErr));
      el.textContent = msg;
    }

    function ensureOverridesLink() {
      const id = "kb-doc-overrides-link";
      let link = document.getElementById(id);
      if (!link) {
        link = document.createElement("link");
        link.id = id;
        link.rel = "stylesheet";
        document.head.appendChild(link);
      }
      link.href = `/api/doc/overrides.css?project=${encodeURIComponent(project)}`;
    }

    function filteredSections() {
      const all = (manifest && manifest.sections) || [];
      const q = searchQuery.trim().toLowerCase();
      if (!q) return all;
      return all.filter((s) =>
        `${s.parent_section || ""} ${s.title || ""} ${s.slug || ""} ${s.summary || ""}`.toLowerCase().includes(q)
      );
    }

    function groupList(list) {
      const map = new Map();
      list.forEach((s) => {
        const g = (s.parent_section || "General").trim() || "General";
        if (!map.has(g)) map.set(g, []);
        map.get(g).push(s);
      });
      return Array.from(map.entries());
    }

    function syncHash() {
      if (!activeSlug) return;
      try {
        history.replaceState(null, "", `#docs/${encodeURIComponent(project)}/${encodeURIComponent(activeSlug)}?mode=${activeMode}`);
      } catch (_) {}
    }

    function readInitialHash() {
      const h = (window.location.hash || "").replace(/^#/, "");
      const m = h.match(/^docs\/([^/]+)\/([^?]+)(?:\?mode=(tell|show))?$/);
      if (m && decodeURIComponent(m[1]) === project) {
        activeSlug = decodeURIComponent(m[2]);
        if (m[3]) activeMode = m[3];
      }
    }

    async function pollQueueStatus() {
      try {
        const st = await apiJson(`/api/doc/status?project=${encodeURIComponent(project)}`);
        if (st.busy || st.queued_count > 0) {
          const run = (st.running && st.running[0]) || null;
          const label = run ? `Running kb-doc (${run.mode.toUpperCase()}${run.slug ? " · " + run.slug : ""})` : `Queued: ${st.queued_count}`;
          showBanner(`${label} · Queued: ${st.queued_count} · Deferred: ${st.deferred_count}`, false);
          if (!pollTimer) {
            pollTimer = setInterval(async () => {
              const next = await apiJson(`/api/doc/status?project=${encodeURIComponent(project)}`).catch(() => null);
              if (next && !next.busy && next.queued_count === 0) {
                stopPoll();
                showBanner("kb-doc finished updating.", false);
                await loadManifest();
              }
            }, 3000);
          }
        } else if (st.deferred_count > 0) {
          showBanner(`${st.deferred_count} kb-doc job(s) deferred due to rate limits; auto-retry scheduled.`, false);
        }
      } catch (_) {}
    }

    async function loadManifest() {
      manifest = await apiJson(`/api/doc/manifest?project=${encodeURIComponent(project)}`);
      if (!activeSlug && manifest.sections && manifest.sections.length) {
        activeSlug = manifest.sections[0].slug;
      }
      renderShell();
      if (activeSlug) await renderSection(activeSlug);
      await pollQueueStatus();
    }

    function renderSidebarGroups() {
      const host = rootEl.querySelector("#kb-doc-groups");
      if (!host) return;
      const groups = groupList(filteredSections());
      if (!groups.length) {
        host.innerHTML = `<div class="kb-doc-error">No matching subsections.</div>`;
        return;
      }
      host.innerHTML = groups.map(([gName, items], gIdx) => {
        const isCollapsed = Boolean(collapsedGroups[gName]) && !searchQuery.trim();
        const rows = items.map((s, sIdx) => {
          const behind = s.has_show && s.show_version && s.tell_version && s.show_version !== s.tell_version;
          const badge = behind ? `<span class="kb-ver-pill behind">${esc(s.show_version)}</span>` : "";
          return `<button type="button" class="kb-doc-nav-item ${s.slug === activeSlug ? "active" : ""}" data-slug="${esc(s.slug)}">
            <span>${String(gIdx + 1).padStart(2, "0")}.${sIdx + 1} ${esc(s.title)}</span>${badge}
          </button>`;
        }).join("");
        return `<div class="kb-doc-group">
          <button type="button" class="kb-doc-group-toggle" data-group="${esc(gName)}">
            <span>${String(gIdx + 1).padStart(2, "0")} · ${esc(gName)}</span>
            <span>${isCollapsed ? "+" : "−"}</span>
          </button>
          <div class="kb-doc-group-items ${isCollapsed ? "kb-doc-hidden" : ""}">${rows}</div>
        </div>`;
      }).join("");

      host.querySelectorAll(".kb-doc-group-toggle").forEach((btn) => {
        btn.addEventListener("click", () => {
          const g = btn.getAttribute("data-group");
          collapsedGroups[g] = !collapsedGroups[g];
          renderSidebarGroups();
        });
      });
      host.querySelectorAll(".kb-doc-nav-item").forEach((btn) => {
        btn.addEventListener("click", () => {
          activeSlug = btn.getAttribute("data-slug");
          syncHash();
          renderSidebarGroups();
          renderSection(activeSlug);
        });
      });
    }

    function renderShell() {
      destroyStage();
      const sections = (manifest && manifest.sections) || [];
      if (!sections.length) {
        rootEl.innerHTML = `<div class="kb-doc-root kb-doc-empty" data-doc-theme="${esc(docTheme)}">
          <section class="kb-doc-main">
            <h2>No documentation generated yet for <code>${esc(project)}</code></h2>
            <p>Brand-new projects start at <code>${esc((manifest && manifest.version) || "V0.0.0")}</code> and wait for the first version bump before <code>kb-doc</code> runs.</p>
          </section>
        </div>`;
        return;
      }

      rootEl.innerHTML = `
        <div class="kb-doc-root" data-doc-theme="${esc(docTheme)}">
          <aside class="kb-doc-sidebar">
            <input type="search" id="kb-doc-search" class="kb-doc-search" placeholder="Search sections (/)" value="${esc(searchQuery)}" />
            <div id="kb-doc-groups"></div>
          </aside>
          <section class="kb-doc-main">
            <div class="kb-doc-toolbar">
              <div class="kb-mode-toggle" role="tablist">
                <button type="button" data-mode="tell" class="${activeMode === "tell" ? "active" : ""}">TELL</button>
                <button type="button" data-mode="show" class="${activeMode === "show" ? "active" : ""}">SHOW</button>
              </div>
              <div class="kb-doc-actions">
                <button type="button" id="kb-btn-gen-show" class="hw-btn">Generate SHOW</button>
                <button type="button" id="kb-btn-feedback" class="hw-btn">Feedback</button>
                <button type="button" id="kb-btn-revert" class="hw-btn">Revert</button>
                <a class="hw-btn" href="/api/doc/export/pdf?project=${encodeURIComponent(project)}" target="_blank" rel="noopener">Export TELL PDF</a>
                <a class="hw-btn" href="/api/doc/export/html?project=${encodeURIComponent(project)}" download="${esc(project)}-docs.html">Offline HTML</a>
                <button type="button" id="kb-btn-doc-theme" class="hw-btn">${docTheme === "light" ? "Dark Page" : "Light Page"}</button>
              </div>
            </div>
            <div id="kb-doc-banner" class="kb-doc-status-banner kb-doc-hidden"></div>
            <div>
              <h1 id="kb-doc-title" class="kb-doc-title"></h1>
              <p id="kb-show-subtitle" class="kb-show-subtitle kb-doc-hidden"></p>
            </div>
            <div id="kb-mini-toc" class="kb-mini-toc kb-doc-hidden"></div>
            <div id="kb-doc-body"></div>
            <div id="kb-show-companion" class="kb-show-companion kb-doc-hidden"></div>
            <div id="kb-doc-fb-panel" class="kb-fb-panel kb-doc-hidden"></div>
            <footer id="kb-doc-footer" class="kb-doc-footer"></footer>
          </section>
        </div>`;

      renderSidebarGroups();

      const searchEl = rootEl.querySelector("#kb-doc-search");
      searchEl.addEventListener("input", () => {
        searchQuery = searchEl.value;
        renderSidebarGroups();
      });

      rootEl.querySelectorAll(".kb-mode-toggle button").forEach((btn) => {
        btn.addEventListener("click", () => {
          activeMode = btn.getAttribute("data-mode");
          syncHash();
          renderShell();
          renderSection(activeSlug);
        });
      });

      rootEl.querySelector("#kb-btn-doc-theme").addEventListener("click", () => {
        docTheme = docTheme === "light" ? "dark" : "light";
        renderShell();
        renderSection(activeSlug);
      });

      rootEl.querySelector("#kb-btn-gen-show").addEventListener("click", async () => {
        try {
          showBanner("Queuing SHOW generation for " + activeSlug + "...", false);
          await apiJson("/api/doc/show/generate", {
            method: "POST",
            body: JSON.stringify({ project, slug: activeSlug }),
          });
          await pollQueueStatus();
        } catch (err) {
          showBanner("SHOW enqueue failed: " + err.message, true);
        }
      });

      rootEl.querySelector("#kb-btn-revert").addEventListener("click", async () => {
        try {
          const res = await apiJson("/api/doc/revert", {
            method: "POST",
            body: JSON.stringify({ project, slug: activeSlug }),
          });
          showBanner(`Reverted ${activeSlug} to snapshot ${res.reverted_to}.`, false);
          await loadManifest();
        } catch (err) {
          showBanner("Revert unavailable: " + err.message, true);
        }
      });

      rootEl.querySelector("#kb-btn-feedback").addEventListener("click", () => toggleFeedback());
    }

    function enhanceTellBody(bodyEl) {
      // Wire stack-diagram Light/Dark toggle buttons (strict CSP, zero inline handlers)
      bodyEl.querySelectorAll(".sd-theme-toggle").forEach((btn) => {
        btn.addEventListener("click", () => {
          const frame = btn.closest(".sd-frame");
          if (!frame) return;
          const next = frame.getAttribute("data-sd-theme") === "dark" ? "light" : "dark";
          frame.setAttribute("data-sd-theme", next);
          btn.textContent = next === "light" ? "Dark Graph" : "Light Graph";
        });
      });

      // Add Copy buttons to <pre> blocks
      bodyEl.querySelectorAll("pre").forEach((pre) => {
        const wrap = document.createElement("div");
        wrap.className = "kb-code-wrap";
        pre.parentNode.insertBefore(wrap, pre);
        wrap.appendChild(pre);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "kb-copy-btn";
        btn.textContent = "Copy";
        btn.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(pre.textContent || "");
            btn.textContent = "Copied";
            setTimeout(() => { btn.textContent = "Copy"; }, 1200);
          } catch (_) {}
        });
        wrap.appendChild(btn);
      });

      // Build compact "On this page" mini-TOC for long TELL pages
      const tocEl = rootEl.querySelector("#kb-mini-toc");
      const headings = Array.from(bodyEl.querySelectorAll("h2, h3"));
      if (tocEl && headings.length >= 2) {
        tocEl.innerHTML = "<span>On this page:</span>";
        headings.forEach((h, idx) => {
          if (!h.id) h.id = `h-${activeSlug}-${idx}`;
          const a = document.createElement("a");
          a.href = `#${h.id}`;
          a.textContent = h.textContent;
          tocEl.appendChild(a);
        });
        tocEl.classList.remove("kb-doc-hidden");
      } else if (tocEl) {
        tocEl.classList.add("kb-doc-hidden");
      }
    }

    async function renderSection(slug) {
      destroyStage();
      const bodyEl = rootEl.querySelector("#kb-doc-body");
      const footerEl = rootEl.querySelector("#kb-doc-footer");
      const titleEl = rootEl.querySelector("#kb-doc-title");
      const subEl = rootEl.querySelector("#kb-show-subtitle");
      const compEl = rootEl.querySelector("#kb-show-companion");
      const tocEl = rootEl.querySelector("#kb-mini-toc");
      if (!bodyEl || !footerEl) return;

      try {
        const sec = await apiJson(`/api/doc/section?project=${encodeURIComponent(project)}&slug=${encodeURIComponent(slug)}`);
        const meta = sec.meta || {};
        titleEl.textContent = meta.title || slug;

        // SHOW-only feeling/message subtitle
        if (activeMode === "show" && meta.show_subtitle) {
          subEl.textContent = meta.show_subtitle;
          subEl.classList.remove("kb-doc-hidden");
        } else {
          subEl.classList.add("kb-doc-hidden");
        }

        // Subtle version drift color-coding in footer
        const tVer = meta.tell_version || "V0.0.0";
        const tDate = (meta.tell_updated_at || "").slice(0, 10);
        const sVer = meta.show_version || null;
        const showCls = !sVer ? "missing" : (sVer !== tVer ? "behind" : "");
        const showTxt = !sVer ? "SHOW: not generated" : `SHOW: ${sVer}${sVer !== tVer ? " (behind)" : ""}`;
        const ticketsHtml = (meta.source_tickets || []).map((t) =>
          `<button type="button" class="kb-ticket-link" data-ticket="${esc(t)}">${esc(t)}</button>`
        ).join(" ");

        footerEl.innerHTML = `
          <span>
            <span class="kb-ver-pill">TELL: ${esc(tVer)}${tDate ? " · " + esc(tDate) : ""}</span>
            <span class="kb-ver-pill ${showCls}">${esc(showTxt)}</span>
          </span>
          <span>${ticketsHtml || "No linked tickets"}</span>`;

        footerEl.querySelectorAll(".kb-ticket-link").forEach((btn) => {
          btn.addEventListener("click", () => {
            const ref = btn.getAttribute("data-ticket");
            window.dispatchEvent(new CustomEvent("kb:open-ticket", { detail: { ref } }));
          });
        });

        if (activeMode === "tell") {
          compEl.classList.add("kb-doc-hidden");
          const diag = sec.diagram_html || "";
          bodyEl.innerHTML = diag + (sec.tell_html || "<p>No TELL content yet.</p>");
          enhanceTellBody(bodyEl);
        } else {
          if (tocEl) tocEl.classList.add("kb-doc-hidden");
          if (!sec.has_show) {
            compEl.classList.add("kb-doc-hidden");
            bodyEl.innerHTML = `<div class="kb-doc-status-banner">SHOW is on-demand. Click <strong>Generate SHOW</strong> above to queue the 480×270 retro cinema for <code>${esc(slug)}</code>.</div>`;
            return;
          }
          const stageHost = document.createElement("div");
          bodyEl.innerHTML = "";
          bodyEl.appendChild(stageHost);
          try {
            // Strict-CSP compliant dynamic ESM import from 'self' (zero blob: URLs)
            const mod = await import(`/api/doc/show.js?project=${encodeURIComponent(project)}&slug=${encodeURIComponent(slug)}&v=${encodeURIComponent(sVer || "0")}`);
            if (typeof mod.mountShow === "function") {
              activeStage = mod.mountShow(stageHost, global.CinemaEngine, meta);
            } else {
              throw new Error("show.js did not export mountShow(container, engine, meta)");
            }
          } catch (err) {
            bodyEl.innerHTML = `<div class="kb-doc-error"><strong>Isolated SHOW error (${esc(slug)}):</strong> ${esc(err.message)}</div>`;
          }
          if (meta.show_companion_html) {
            compEl.innerHTML = `<div class="kb-show-companion-kicker">Another Angle</div>${meta.show_companion_html}`;
            compEl.classList.remove("kb-doc-hidden");
          } else {
            compEl.classList.add("kb-doc-hidden");
          }
        }
      } catch (err) {
        bodyEl.innerHTML = `<div class="kb-doc-error"><strong>Section load error:</strong> ${esc(err.message)}</div>`;
      }
    }

    async function toggleFeedback() {
      const panel = rootEl.querySelector("#kb-doc-fb-panel");
      if (!panel) return;
      if (!panel.classList.contains("kb-doc-hidden")) {
        panel.classList.add("kb-doc-hidden");
        return;
      }
      panel.classList.remove("kb-doc-hidden");
      const data = await apiJson(`/api/doc/feedback?project=${encodeURIComponent(project)}`);
      const items = (data.feedback || []).slice().reverse();
      const rows = items.map((fb) => `
        <div class="kb-fb-item">
          <span class="kb-ver-pill ${fb.status === "open" ? "behind" : ""}">${esc(fb.status)}</span>
          <strong>${esc(fb.section)}</strong> · ${esc(fb.author)} · ${esc((fb.created_at || "").slice(0, 10))}
          <div>${esc(fb.text)}</div>
          ${fb.resolution_note ? `<div>Resolved (${esc(fb.resolved_in_version || "")}): ${esc(fb.resolution_note)}</div>` : ""}
        </div>`).join("");

      panel.innerHTML = `
        <div class="kb-fb-row">
          <input id="kb-fb-input" class="kb-fb-input" type="text" placeholder="Leave feedback on ${esc(activeSlug || "global")}..." />
          <button type="button" id="kb-fb-send" class="hw-btn">Submit</button>
          <button type="button" id="kb-fb-apply" class="hw-btn">Run TELL (Apply Feedback)</button>
        </div>
        <div>${rows || "No feedback yet."}</div>`;

      panel.querySelector("#kb-fb-send").addEventListener("click", async () => {
        const txt = (panel.querySelector("#kb-fb-input").value || "").trim();
        if (txt.length < 3) return;
        await apiJson("/api/doc/feedback", {
          method: "POST",
          body: JSON.stringify({ project, section: activeSlug || "global", text: txt }),
        });
        panel.classList.add("kb-doc-hidden");
        toggleFeedback();
      });

      panel.querySelector("#kb-fb-apply").addEventListener("click", async () => {
        try {
          await apiJson("/api/doc/tell/refresh", {
            method: "POST",
            body: JSON.stringify({ project }),
          });
          showBanner("Queued TELL refresh to apply open Boss feedback.", false);
          await pollQueueStatus();
        } catch (err) {
          showBanner("TELL refresh failed: " + err.message, true);
        }
      });
    }

    function onGlobalKey(e) {
      if (e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
      if (e.key === "/") {
        const s = rootEl.querySelector("#kb-doc-search");
        if (s) { e.preventDefault(); s.focus(); }
      } else if (e.key === "m" || e.key === "M") {
        activeMode = activeMode === "tell" ? "show" : "tell";
        syncHash();
        renderShell();
        renderSection(activeSlug);
      } else if (e.key === "[" || e.key === "]") {
        const list = filteredSections();
        const idx = list.findIndex((s) => s.slug === activeSlug);
        if (idx !== -1 && list.length > 1) {
          const nextIdx = (idx + (e.key === "]" ? 1 : -1) + list.length) % list.length;
          activeSlug = list[nextIdx].slug;
          syncHash();
          renderSidebarGroups();
          renderSection(activeSlug);
        }
      }
    }

    window.addEventListener("keydown", onGlobalKey);
    readInitialHash();
    ensureOverridesLink();
    loadManifest();

    return {
      destroy: function () {
        destroyStage();
        stopPoll();
        window.removeEventListener("keydown", onGlobalKey);
      },
      reload: loadManifest,
    };
  }

  global.KanbanDocShell = { mountDocViewer };
})(window);
