/* doc_shared/shell.js
 * Universal containerized doc viewer runtime (strict-CSP compliant: zero inline styles or blob URLs).
 * Isolates each section in try/catch, renders per-page version footers,
 * handles Boss on-demand SHOW generation, and Boss feedback history.
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
    if (o.method && o.method !== "GET") {
      headers["X-Kanban-CSRF"] = csrfToken();
    }
    const res = await fetch(url, Object.assign({}, o, { headers }));
    const data = await res.json().catch(() => ({ ok: false, error: "Invalid JSON" }));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function escapeHtml(s) {
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
    let activeStage = null;

    function destroyStage() {
      if (activeStage && typeof activeStage.destroy === "function") {
        try { activeStage.destroy(); } catch (_) {}
      }
      activeStage = null;
    }

    function loadOverridesCss() {
      const id = "kb-doc-project-overrides";
      let linkEl = document.getElementById(id);
      if (!linkEl) {
        linkEl = document.createElement("link");
        linkEl.id = id;
        linkEl.rel = "stylesheet";
        document.head.appendChild(linkEl);
      }
      linkEl.href = `/api/doc/overrides.css?project=${encodeURIComponent(project)}&t=${Date.now()}`;
    }

    async function loadManifest() {
      manifest = await apiJson(`/api/doc/manifest?project=${encodeURIComponent(project)}`);
      if (!activeSlug && manifest.sections && manifest.sections.length) {
        activeSlug = manifest.sections[0].slug;
      }
      renderShell();
      if (activeSlug) await renderSection(activeSlug);
    }

    function renderShell() {
      destroyStage();
      const sections = (manifest && manifest.sections) || [];
      if (!sections.length) {
        rootEl.innerHTML = `
          <div class="kb-doc-main">
            <h3>No documentation generated yet for <code>${escapeHtml(project)}</code></h3>
            <p class="kb-doc-empty-note">
              Brand-new projects start at <code>${escapeHtml((manifest && manifest.version) || "V0.0.0")}</code>
              and wait for the first version bump before <code>kb-doc</code> generates TELL pages.
            </p>
          </div>`;
        return;
      }

      const navHtml = sections.map((s) => {
        const outdated = s.has_show && s.show_version && s.tell_version && s.show_version !== s.tell_version;
        const badge = outdated
          ? `<span class="kb-doc-badge warn" title="SHOW outdated">SHOW ${escapeHtml(s.show_version)}</span>`
          : `<span class="kb-doc-badge">${escapeHtml(s.tell_version || "V0.0.0")}</span>`;
        return `<button type="button" class="kb-doc-nav-item ${s.slug === activeSlug ? "active" : ""}" data-slug="${escapeHtml(s.slug)}">
          <span>${escapeHtml(s.title)}</span>${badge}
        </button>`;
      }).join("");

      rootEl.innerHTML = `
        <div class="kb-doc-root">
          <aside class="kb-doc-sidebar">
            <div class="kb-doc-sidebar-head">
              <strong>${escapeHtml(project)}</strong>
              <span class="kb-doc-badge">${escapeHtml(manifest.version || "V0.0.0")}</span>
            </div>
            ${navHtml}
          </aside>
          <section class="kb-doc-main">
            <div class="kb-doc-toolbar">
              <div class="kb-mode-toggle" role="tablist">
                <button type="button" data-mode="tell" class="${activeMode === "tell" ? "active" : ""}">TELL</button>
                <button type="button" data-mode="show" class="${activeMode === "show" ? "active" : ""}">SHOW</button>
              </div>
              <div class="kb-doc-toolbar-actions">
                <button type="button" id="kb-btn-gen-show" class="cinema-btn">Generate / Refresh SHOW (Boss)</button>
                <button type="button" id="kb-btn-feedback" class="cinema-btn">Boss Feedback</button>
              </div>
            </div>
            <div id="kb-doc-body"></div>
            <div id="kb-doc-feedback-panel" class="kb-doc-fb-panel hidden"></div>
            <footer id="kb-doc-footer" class="kb-doc-footer"></footer>
          </section>
        </div>`;

      rootEl.querySelectorAll(".kb-doc-nav-item").forEach((btn) => {
        btn.addEventListener("click", () => {
          activeSlug = btn.getAttribute("data-slug");
          renderShell();
          renderSection(activeSlug);
        });
      });

      rootEl.querySelectorAll(".kb-mode-toggle button").forEach((btn) => {
        btn.addEventListener("click", () => {
          activeMode = btn.getAttribute("data-mode");
          renderShell();
          renderSection(activeSlug);
        });
      });

      const genBtn = rootEl.querySelector("#kb-btn-gen-show");
      if (genBtn) {
        genBtn.addEventListener("click", async () => {
          genBtn.disabled = true;
          genBtn.textContent = "Generating SHOW...";
          try {
            await apiJson("/api/doc/show/generate", {
              method: "POST",
              body: JSON.stringify({ project, slug: activeSlug }),
            });
            activeMode = "show";
            await loadManifest();
          } catch (err) {
            const bodyEl = rootEl.querySelector("#kb-doc-body");
            if (bodyEl) {
              bodyEl.innerHTML = `<div class="kb-doc-error"><strong>SHOW generation failed:</strong> ${escapeHtml(err.message)}</div>`;
            }
          } finally {
            genBtn.disabled = false;
            genBtn.textContent = "Generate / Refresh SHOW (Boss)";
          }
        });
      }

      const fbBtn = rootEl.querySelector("#kb-btn-feedback");
      if (fbBtn) {
        fbBtn.addEventListener("click", () => toggleFeedbackPanel());
      }
    }

    async function renderSection(slug) {
      destroyStage();
      const bodyEl = rootEl.querySelector("#kb-doc-body");
      const footerEl = rootEl.querySelector("#kb-doc-footer");
      if (!bodyEl || !footerEl) return;

      try {
        const sec = await apiJson(
          `/api/doc/section?project=${encodeURIComponent(project)}&slug=${encodeURIComponent(slug)}`
        );
        const meta = sec.meta || {};
        const tellVer = meta.tell_version || "—";
        const tellDate = (meta.tell_updated_at || "").slice(0, 10);
        const showVer = meta.show_version || "not generated";
        const showDate = (meta.show_updated_at || "").slice(0, 10);
        footerEl.innerHTML = `
          <span>Page last updated · TELL: <strong>${escapeHtml(tellVer)}</strong>${tellDate ? " (" + escapeHtml(tellDate) + ")" : ""} · SHOW: <strong>${escapeHtml(showVer)}</strong>${showDate ? " (" + escapeHtml(showDate) + ")" : ""}</span>
          <span>Tickets: ${escapeHtml((meta.source_tickets || []).join(", ") || "none")}</span>
        `;

        if (activeMode === "tell") {
          bodyEl.innerHTML = sec.tell_html || `<p class="kb-doc-empty-note">No TELL content yet.</p>`;
        } else {
          if (!sec.has_show || !sec.show_js) {
            bodyEl.innerHTML = `
              <div class="kb-doc-show-placeholder">
                <strong>SHOW is on-demand (Boss-triggered).</strong><br/>
                Click <em>Generate / Refresh SHOW (Boss)</em> above to build the 480×270 retro cinema for <code>${escapeHtml(slug)}</code>.
              </div>`;
            return;
          }
          const stageHost = document.createElement("div");
          bodyEl.innerHTML = "";
          bodyEl.appendChild(stageHost);
          try {
            const stamp = encodeURIComponent(meta.show_updated_at || String(Date.now()));
            const modUrl = `/api/doc/show.js?project=${encodeURIComponent(project)}&slug=${encodeURIComponent(slug)}&v=${stamp}`;
            const mod = await import(modUrl);
            if (typeof mod.mountShow === "function") {
              activeStage = mod.mountShow(stageHost, global.CinemaEngine, meta);
            } else {
              throw new Error("show.js did not export mountShow(container, engine, meta)");
            }
          } catch (err) {
            bodyEl.innerHTML = `<div class="kb-doc-error"><strong>Isolated SHOW section error (${escapeHtml(slug)}):</strong> ${escapeHtml(err.message)}</div>`;
          }
        }
      } catch (err) {
        bodyEl.innerHTML = `<div class="kb-doc-error"><strong>Section load error:</strong> ${escapeHtml(err.message)}</div>`;
      }
    }

    async function toggleFeedbackPanel() {
      const panel = rootEl.querySelector("#kb-doc-feedback-panel");
      if (!panel) return;
      if (!panel.classList.contains("hidden")) {
        panel.classList.add("hidden");
        return;
      }
      panel.classList.remove("hidden");
      const data = await apiJson(`/api/doc/feedback?project=${encodeURIComponent(project)}`);
      const items = data.feedback || [];
      const rows = items.slice().reverse().map((fb) => `
        <div class="kb-doc-fb-item">
          <div>
            <span class="kb-doc-badge ${fb.status === "open" ? "warn" : ""}">${escapeHtml(fb.status)}</span>
            <strong>${escapeHtml(fb.section)}</strong> · ${escapeHtml(fb.author)} · ${escapeHtml((fb.created_at || "").slice(0, 10))}
          </div>
          <div class="kb-doc-fb-text">${escapeHtml(fb.text)}</div>
          ${fb.resolution_note ? `<div class="kb-doc-fb-resolution">Resolved in ${escapeHtml(fb.resolved_in_version || "")}: ${escapeHtml(fb.resolution_note)}</div>` : ""}
        </div>`).join("");

      panel.innerHTML = `
        <h4 class="kb-doc-fb-title">Boss Feedback (resolved auto-purged after 120 days)</h4>
        <div class="kb-doc-fb-row">
          <input id="kb-fb-input" class="kb-doc-fb-input" type="text" placeholder="Leave feedback for next kb-doc run on ${escapeHtml(activeSlug || "global")}..." />
          <button type="button" id="kb-fb-send" class="cinema-btn">Submit</button>
        </div>
        <div class="kb-doc-fb-list">${rows || '<span class="kb-doc-muted-inline">No feedback yet.</span>'}</div>`;

      panel.querySelector("#kb-fb-send").addEventListener("click", async () => {
        const inp = panel.querySelector("#kb-fb-input");
        const txt = (inp.value || "").trim();
        if (txt.length < 3) return;
        await apiJson("/api/doc/feedback", {
          method: "POST",
          body: JSON.stringify({ project, section: activeSlug || "global", text: txt }),
        });
        panel.classList.add("hidden");
        toggleFeedbackPanel();
      });
    }

    loadOverridesCss();
    loadManifest();
    return { destroy: destroyStage, reload: loadManifest };
  }

  global.KanbanDocShell = { mountDocViewer };

  window.addEventListener("DOMContentLoaded", function () {
    const app = document.getElementById("doc-app");
    if (app && app.dataset.project) {
      mountDocViewer(app, app.dataset.project);
    }
  });
})(window);
