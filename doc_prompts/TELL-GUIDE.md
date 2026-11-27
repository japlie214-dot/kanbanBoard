# TELL Authoring Guide (S-Tier Engineering Reference)

Write for engineers who want exact contracts fast. Apply every rule below:

## Information Architecture & Hierarchy
- Group pages by subsystem and reader intent (`parent_section` -> subsection `slug`), two levels deep.
- Update only subsections touched by this version's shipped tickets or open Boss feedback.
- Maintain two autonomous domain-paper-trail subsections when warranted by shipped tickets or Cases:
  - **`glossary`**: **canonical** project vocabulary—tight definitions only, zero implementation prose.
  - **`decisions`**: **three-gate** ADRs only—record a choice solely when it is (1) hard to reverse, (2) surprising without context, and (3) a real trade-off.

## Three Reading Speeds per Subsection
1. **Lead invariant** (1–2 sentences): state the exact guarantee first.
2. **Exact contract or map**: show real CLI flags, wire schemas, error codes, tables, or a declarative `stack_diagram` JSON object (`{title, groups:[{id,label,tone,nodes:[{id,title,subtitle,icon}]}], edges:[{from,to,label,tone,style}]}`).
3. **Failure modes & witness bounds**: state exact rejected inputs and status codes (e.g., `403`, `400`, `120d`).

## Output Hygiene
- Emit pure sanitized HTML fragments in `tell_html` (zero `<script>`, zero `style=""`, zero inline `on*` handlers).
- Vary layout per subsection; supply optional `overrides_css` when a project benefits from custom styling.
