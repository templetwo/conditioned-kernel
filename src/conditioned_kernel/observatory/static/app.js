"use strict";
/*
 * Conditioned Kernel — Interior View
 * Static frontend. Dependency-free, no build step, no external assets.
 *
 * Every number rendered by this file is read from a server response — a
 * TurnTrace (trace.py), a session summary, or a replay result (replay.py).
 * This file intentionally does NOT reimplement any pipeline business rule
 * (byte accounting, Jaccard similarity, evidence matching, budget
 * enforcement, stage status derivation). Those live in
 * observatory/compute.py and are computed once, server-side, per the
 * honesty contract in design_handoff_interior_view/README.md §10. Where a
 * value this design calls for is not yet exposed by the current backend
 * contract, this file says so plainly (see NA()) instead of inventing it —
 * per §10's own rule: "Where the trace cannot settle something, say so and
 * name the value that would."
 *
 * ---------------------------------------------------------------------
 * API CONTRACT this file consumes — read directly off the real
 * observatory/server.py + turn_api.py + brief.py built for this handoff
 * (not this file's own guess; verified against their source):
 *
 *   GET  /api/session
 *     -> { session_id, goal, open_thread_count, recent_turns_on_disk,
 *          runtime_config: {
 *            kernel: { model, mode, think, temperature, seed, num_ctx,
 *                       keep_alive, timeout_s, stream, endpoint },
 *            edge_profile: <EdgeProfile.to_dict()>,
 *            edge_report: <edge_status_report(profile)>,
 *            acceptance_mode, paths: { state_dir, logs_dir },
 *            server: { host, port, observer_enabled } },
 *          turns: [ { turn_id, session_id, started_at, completed_at,
 *                      user_input, decision, label, answer, pass_count,
 *                      packet_bytes, violations, advisories, observations,
 *                      error } ] }
 *     Note: no top-level "connection" or "config" (layout/defaultStage/
 *     showObservations) field exists on this endpoint yet — this file
 *     defaults those client-side (documented at each call site) rather
 *     than inventing server support for them.
 *
 *   POST /api/turn              { text }                    -> TurnTrace.to_dict()
 *   GET  /api/turn/:id/trace                                 -> TurnTrace.to_dict() | 404 {error}
 *   GET  /api/turn/:id/brief                                  -> text/markdown (build_full_debug_brief) | 404 {error}
 *   GET  /api/stream                                          -> text/event-stream
 *        `event: stage`  data: { turn_id, stage: StageTrace.to_dict() }
 *        `event: turn_complete` data: { turn_id, decision }
 *        (published back-to-back right after run_traced_turn finishes —
 *        pacing is post-hoc, content is real; see turn_api.py's own note)
 *   GET  /api/observer/status                                 -> { enabled }
 *   POST /api/feedback          { turn_id, marks[], note }    -> { ok, recorded }
 *   POST /api/replay            { turn_id, sections }         -> replay.run_replay() + { turn_id }
 *   POST /api/observer/stage    { turn_id, ask, payload_kind, -> { turn_id, ask, ask_label,
 *                                  include_prior_dialogue }        system_prompt, payload, disclosure }
 *   POST /api/observer/send     (same body)                   -> same + { ok:false, stub:true, message }
 *        (this build's cloud send is an intentional stub — see turn_api.py's
 *        Dashboard.observer_send docstring; acceptance criterion 19/22)
 *
 *   Studio Flow mode (turn_api.Dashboard(session_mode="flow"), started via
 *   `ck dashboard --session-mode flow`): the same endpoints above serve a
 *   flow.FlowTrace (schema "ck.flow_trace.v1") instead of a pipeline
 *   TurnTrace wherever a turn is flow-shaped — GET /api/session's own
 *   runtime_config.session_mode says which, and each turn summary in
 *   `turns[]` carries `mode: "flow"` or `"pipeline"`. A FlowTrace has no
 *   stages[]/passes[]/final_decision; it carries field_before,
 *   composed_prompt, raw_reply, reply_status, displayed_text, observations,
 *   integration_actions, and field_after instead. GET /api/stream emits
 *   `event: field_before` / `event: traveled` / `event: field_after` (then
 *   `turn_complete`) for a flow turn rather than 12 `event: stage`s.
 * ---------------------------------------------------------------------
 */

// ============================================================== helpers ==

const NA = "— not exposed by this trace";

function h(tag, attrs, children) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const k in attrs) {
      if (k === "class") el.className = attrs[k];
      else if (k === "style" && typeof attrs[k] === "object") Object.assign(el.style, attrs[k]);
      else if (k.startsWith("on") && typeof attrs[k] === "function") el.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== undefined && attrs[k] !== null) el.setAttribute(k, attrs[k]);
    }
  }
  (Array.isArray(children) ? children : children != null ? [children] : []).forEach((c) => {
    if (c == null) return;
    el.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
  });
  return el;
}
function txt(tag, cls, text) { return h(tag, cls ? { class: cls } : null, text); }
function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function mount(node, children) { clear(node); (Array.isArray(children) ? children : [children]).forEach((c) => c != null && node.appendChild(c)); }

function bytesUtf8(s) { return new TextEncoder().encode(String(s == null ? "" : s)).length; }
function isNil(v) { return v === undefined || v === null; }
function orNA(v, fmt) { return isNil(v) || v === "" ? NA : (fmt ? fmt(v) : String(v)); }
function fmtPct(v) {
  if (isNil(v)) return NA;
  const n = Number(v);
  return (n < 1 && n > 0 ? n.toFixed(2) : n.toFixed(1)) + "%";
}
function fmtBytes(n) { return isNil(n) ? NA : n + " B"; }
function clipStr(s, n) {
  s = String(s == null ? "" : s).trim();
  return s.length <= n ? s : s.slice(0, Math.max(0, n - 1)) + "…";
}
function joinOr(list, empty) {
  if (!list || !list.length) return empty === undefined ? "[]" : empty;
  return list.join(" · ");
}
// Parses the ISO-compact timestamp ids.make_id() embeds in every id this
// system mints ("<prefix>_YYYYMMDDTHHMMSSZ_<hex>") — presentational only,
// never used to decide anything, only to display a request start/end time
// PassTrace does not otherwise carry.
function idTimestamp(id) {
  if (!id) return null;
  const m = /_(\d{8}T\d{6}Z)_/.exec(String(id));
  if (!m) return null;
  const s = m[1];
  return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}T${s.slice(9, 11)}:${s.slice(11, 13)}:${s.slice(13, 15)}Z`;
}
function isoDurationSeconds(startIso, endIso) {
  if (!startIso || !endIso) return null;
  const a = Date.parse(startIso), b = Date.parse(endIso);
  if (isNaN(a) || isNaN(b)) return null;
  return (b - a) / 1000;
}
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return { ok: true, bytes: bytesUtf8(text) };
  } catch (e) {
    return { ok: false, error: String((e && e.message) || e) };
  }
}

// ================================================================ tones ==

const TONE = {
  ok: "var(--status-ok)",
  active: "var(--status-active)",
  warn: "var(--status-warn)",
  bad: "var(--status-bad)",
  fix: "var(--status-fix)",
  skip: "var(--status-skip)",
  wait: "var(--status-wait)",
};
const CTX_COLOR = {
  current_user_input: "var(--ctx-user)",
  recent_dialogue: "var(--ctx-recent)",
  durable_state: "var(--ctx-state)",
  system_instructions: "var(--ctx-system)",
  output_schema: "var(--ctx-schema)",
  constraints: "var(--ctx-constraints)",
};
// Server-side statuses (compute.derive_stage_status): completed, active,
// waiting, warning, rejected, repaired, skipped.
const STAGE_STATUS_TONE = {
  completed: TONE.ok,
  active: TONE.active,
  waiting: TONE.wait,
  warning: TONE.warn,
  rejected: TONE.bad,
  repaired: TONE.fix,
  skipped: TONE.skip,
};
const STATIC_STAGE_NAMES = {
  1: "INPUT", 2: "STATE LOAD", 3: "RECENT MEMORY", 4: "PACKET COMPILE",
  5: "EDGE BUDGET", 6: "KERNEL REQUEST", 7: "RAW OUTPUT", 8: "PARSE",
  9: "VALIDATE", 10: "REPAIR", 11: "DECISION", 12: "PERSIST",
};
const SIDE_PANEL_NAMES = { 0: "RUNTIME", "-1": "SESSION", "-2": "OBSERVER", "-3": "REPLAY" };
const STAGE_IDS_BY_LABEL = {
  "Final decision": 11, "Packet composition": 4, "Validation": 9,
  "What you said": 1, "Persistence": 12,
};
const MARKS = [
  ["useful", "useful"], ["not_useful", "not useful"],
  ["wrong_acceptance", "wrong acceptance"], ["wrong_rejection", "wrong rejection"],
  ["substrate_dominated", "substrate dominated user input"], ["memory_dominated", "recent memory dominated"],
];
// Button labels only — mirrors brief.ASK_LABELS's values verbatim (static
// navigation chrome, not a computed value). The actual prompt/system text
// sent to a model is entirely server-owned (brief.py) and only ever shown
// here via the staged response's own `system_prompt` / `payload` fields —
// this file never invents or duplicates that text.
const OBS_ASKS = {
  explain: { label: "Explain this turn" },
  bug: { label: "Where is the bug?" },
  change: { label: "What should Claude Code change?" },
};
const REPLAY_SECTION_DEFAULT_ORDER = ["recent", "state", "obligation", "system", "schema", "constraints"];

// ---------------------------------------------------------- flow mode ----
//
// Studio Flow (`ck chat --mode flow` / `ck dashboard --session-mode flow`)
// replaces the acceptance-court metaphor for the living conversational
// path: field before -> model speaks through field -> output reaches
// Anthony -> substrate observes what traveled -> field integrates and
// shifts -> next turn (see flow.py's module docstring). A FlowTrace
// (flow.FlowTrace.to_dict(), schema "ck.flow_trace.v1") has a different
// shape than a pipeline TurnTrace — no stages[], no passes[], no
// final_decision — so every renderer below branches on `isFlowTurn()`
// before touching trace-shape-specific fields, and the pipeline branch of
// each is left byte-identical to before this mode existed.
const FLOW_TRACE_SCHEMA = "ck.flow_trace.v1";
// Reuses the same context-share palette tokens the pipeline panels already
// use (CTX_COLOR above) — no new colors invented for Flow.
const FLOW_KIND_COLOR = {
  topic: "var(--ctx-recent)",
  canonical: "var(--ctx-state)",
  thread: "var(--ctx-constraints)",
};
const FLOW_ACTION_TONE = {
  strengthened: TONE.ok,
  created: "var(--ctx-state)",
  decayed: TONE.skip,
  softened: TONE.warn,
  dropped: TONE.bad,
};
const FLOW_PANELS = [
  { id: "field_before", label: "FIELD BEFORE" },
  { id: "traveled", label: "WHAT TRAVELED" },
  { id: "field_after", label: "FIELD AFTER" },
];

// ================================================================== API ==

const Api = {
  async getSession() { return Api._json("GET", "/api/session"); },
  async postTurn(text) { return Api._json("POST", "/api/turn", { text }); },
  async getTrace(turnId) { return Api._json("GET", `/api/turn/${encodeURIComponent(turnId)}/trace`); },
  async getBrief(turnId) { return Api._text("GET", `/api/turn/${encodeURIComponent(turnId)}/brief`); },
  async postFeedback(turnId, marks, note) {
    return Api._json("POST", "/api/feedback", { turn_id: turnId, marks, note });
  },
  async postReplay(turnId, sections) {
    return Api._json("POST", "/api/replay", { turn_id: turnId, sections });
  },
  async getObserverStatus() { return Api._json("GET", "/api/observer/status"); },
  async postObserverStage(turnId, ask, payloadKind, includePriorDialogue) {
    return Api._json("POST", "/api/observer/stage", {
      turn_id: turnId, ask, payload_kind: payloadKind, include_prior_dialogue: includePriorDialogue,
    });
  },
  async postObserverSend(turnId, ask, payloadKind, includePriorDialogue) {
    return Api._json("POST", "/api/observer/send", {
      turn_id: turnId, ask, payload_kind: payloadKind, include_prior_dialogue: includePriorDialogue,
    });
  },
  async _json(method, url, body) {
    const res = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`${method} ${url} -> ${res.status}${detail ? ": " + detail.slice(0, 300) : ""}`);
    }
    if (res.status === 204) return null;
    return res.json();
  },
  async _text(method, url) {
    const res = await fetch(url, { method });
    if (!res.ok) throw new Error(`${method} ${url} -> ${res.status}`);
    return res.text();
  },
};

// ================================================================ state ==

const State = {
  session: null,          // /api/session response
  currentTurnId: null,    // selected turn's id (from session.turns)
  trace: null,             // full TurnTrace for currentTurnId, once fetched
  traceCache: new Map(),   // turn_id -> TurnTrace
  stage: null,             // selected panel id, null = configured default
  flowPanel: null,          // selected flow panel id, null = "field_before" (see FLOW_PANELS)
  layout: null,             // "rail" | "spine" | null = from session.config
  play: -1,                 // replay-walkthrough animation index, -1 = idle
  marks: {},                 // "turnId:markKey" -> bool (mirrors last feedback POST)
  notes: {},                  // turnId -> note text
  draft: "",
  sendNote: "",
  sendBad: false,
  sending: false,
  ops: "",
  opsErr: false,
  connected: null,          // null = unknown, true/false once probed
  exp: {},                   // replay-panel section overrides {key: bool}
  replayResult: null,        // last POST /api/replay response
  replayLoading: false,
  obsAsk: "explain",           // which ask is staged/selected: explain|bug|change
  obsPayloadKind: "compact",   // "compact" | "full" — mirrors turn_api.py's payload_kind
  obsDialogue: false,           // include_prior_dialogue, compact brief only
  obsPending: null,              // staged POST /api/observer/stage response
  obs: null,                      // POST /api/observer/send response (always a stub in this build)
  brief: null,                 // cached markdown brief for currentTurnId
  briefLoading: false,
  sse: null,
};

function setState(patch) {
  Object.assign(State, patch);
  render();
}

// ---- derived getters --------------------------------------------------

function layout() { return State.layout || (State.session && State.session.config && State.session.config.layout) || "rail"; }
function defaultStageId() {
  const label = (State.session && State.session.config && State.session.config.defaultStage) || "Final decision";
  return STAGE_IDS_BY_LABEL[label] || 11;
}
function selectedStage() { return State.stage === null ? defaultStageId() : State.stage; }
// Flow-mode helpers. `isFlowSession()` reads the dashboard process's own
// runtime config (turn_api.Dashboard.session_mode, unaffected by which
// turn is currently selected) so the rail defaults to the flow shape even
// before any turn has loaded. `isFlowTurn()` additionally recognizes a
// specific trace/summary as flow, so a mixed-history dashboard (unlikely,
// but never assumed away) still renders each turn by its own kind.
function isFlowSession() {
  const rc = State.session && State.session.runtime_config;
  return !!(rc && rc.session_mode === "flow");
}
function isFlowTurn(t, summary) {
  if (t && t.schema === FLOW_TRACE_SCHEMA) return true;
  if (!t && summary && summary.mode === "flow") return true;
  if (!t && !summary && isFlowSession()) return true;
  return false;
}
function selectedFlowPanel() { return State.flowPanel || FLOW_PANELS[0].id; }
// /api/session does not (yet) carry a "config" block for these three
// tweakable props (README §8) — default them client-side rather than
// inventing server support. Documented gap, see final report.
function showObservations() { return !State.session || !State.session.config || State.session.config.showObservations !== false; }
function observerEnabled() {
  const rc = State.session && State.session.runtime_config;
  return !!(rc && rc.server && rc.server.observer_enabled);
}
// session.turns (turn_api._summarize_turn) does not carry a display index,
// a "spoken" boolean, or a duration — all three are pure presentational
// derivations from fields the summary already has (array position, an
// answer-is-non-null check identical to trace.py's own final_decision.answer
// semantics, and simple timestamp subtraction), never a new business rule.
function turnsList() {
  const raw = (State.session && State.session.turns) || [];
  return raw.map((t, i) => ({
    ...t,
    n: i + 1,
    spoken: !isNil(t.answer),
    elapsed_seconds: isoDurationSeconds(t.started_at, t.completed_at),
  }));
}
function currentTurnSummary() { return turnsList().find((t) => t.turn_id === State.currentTurnId) || null; }
// The two "runtime_config" shapes in this app are NOT the same: TurnTrace's
// is already flat (trace.py's own construction — model, mode, temperature,
// seed, num_ctx, keep_alive, think, base_url, profile, state_dir, logs_dir).
// /api/session's is nested (turn_api.Dashboard.session_payload — kernel /
// edge_profile / acceptance_mode / paths / server). Normalize both to the
// flat shape the panels below already read, rather than conflating them.
function normalizeRuntimeConfig(rc, sourceIsSession) {
  if (!rc) return null;
  if (!sourceIsSession) return rc;
  const k = rc.kernel || {};
  return {
    model: k.model, mode: k.mode, acceptance_mode: rc.acceptance_mode,
    temperature: k.temperature, seed: k.seed, num_ctx: k.num_ctx, keep_alive: k.keep_alive,
    think: k.think, base_url: k.endpoint, profile: rc.edge_profile || {},
    state_dir: (rc.paths || {}).state_dir, logs_dir: (rc.paths || {}).logs_dir,
  };
}
function currentRuntimeConfig() {
  if (State.trace && State.trace.runtime_config) return normalizeRuntimeConfig(State.trace.runtime_config, false);
  if (State.session && State.session.runtime_config) return normalizeRuntimeConfig(State.session.runtime_config, true);
  return {};
}
function currentPass() {
  if (!State.trace || !State.trace.passes || !State.trace.passes.length) return null;
  return State.trace.passes[State.trace.passes.length - 1];
}
function firstPass() {
  if (!State.trace || !State.trace.passes || !State.trace.passes.length) return null;
  return State.trace.passes[0];
}
function stageByIndex(idx) {
  if (!State.trace || !State.trace.stages) return null;
  return State.trace.stages.find((s) => s.index === idx) || null;
}

// ============================================================ render ====

let renderScheduled = false;
function render() {
  if (renderScheduled) return;
  renderScheduled = true;
  requestAnimationFrame(() => {
    renderScheduled = false;
    renderHeader();
    renderConversation();
    renderPipelineHead();
    renderStageNav();
    renderPanel();
    renderNotebook();
  });
}

// ------------------------------------------------------------- header ---

function renderHeader() {
  const rail = document.getElementById("btn-rail");
  const spine = document.getElementById("btn-spine");
  const spineOn = layout() === "spine";
  rail.className = "pill" + (spineOn ? "" : " active");
  spine.className = "pill" + (spineOn ? " active" : "");
  rail.onclick = () => setState({ layout: "rail" });
  spine.onclick = () => setState({ layout: "spine" });

  const meta = document.getElementById("hdr-meta");
  const rc = currentRuntimeConfig();
  const profile = rc && rc.profile;
  const sel = selectedStage();

  const chip = (label, id, violet) => {
    const btn = h("button", { class: "hdr-chip mono" + (violet ? " observer" : "") + (sel === id ? " active" : ""), type: "button" }, `${label} ↗`);
    btn.onclick = () => setState({ stage: id, play: -1 });
    return btn;
  };

  const items = [
    h("span", null, [h("span", { class: "meta-label" }, "session "), (State.session && State.session.session_id) || NA]),
    h("span", null, [h("span", { class: "meta-label" }, "model "), h("span", { class: "meta-model" }, (rc && rc.model) || NA)]),
    h("span", null, [h("span", { class: "meta-label" }, "edge "), (profile && profile.profile_id) || NA]),
    h("span", null, [h("span", { class: "meta-label" }, "num_ctx "), (rc && rc.num_ctx != null) ? String(rc.num_ctx) : NA]),
    h("span", null, [h("span", { class: "meta-label" }, "packet budget "), (profile && profile.max_packet_bytes != null) ? profile.max_packet_bytes + " B" : NA]),
    h("span", null, [h("span", { class: "meta-label" }, "acceptance "), (rc && rc.acceptance_mode) || NA]),
    h("span", { class: "conn-item", title: "dashboard reachability only — this build does not probe Ollama itself" }, [
      h("span", { class: "conn-dot" + (State.connected === false ? " down" : "") }),
      State.connected === false ? "dashboard unreachable" : (rc && rc.base_url) || NA,
    ]),
    chip("runtime & edge profile", 0, false),
    chip("attractor timeline", -1, false),
    chip("replay turn", -3, false),
  ];
  if (observerEnabled()) items.push(chip("claude observer", -2, true));
  if (isFlowSession()) {
    items.splice(6, 0, h("span", { style: { color: "var(--ctx-recent)" } }, [h("span", { class: "meta-label" }, "session mode "), "flow"]));
  }
  mount(meta, items);
}

// -------------------------------------------------------- conversation --

function renderConversation() {
  const listEl = document.getElementById("convo-list");
  const metaEl = document.getElementById("convo-meta");
  const turns = turnsList();

  if (!State.session) {
    mount(listEl, h("div", { class: "empty-placeholder" }, "Loading session…"));
    metaEl.textContent = "";
  } else if (!turns.length) {
    mount(listEl, h("div", { class: "empty-placeholder" }, "No turns yet in this session. Send a message below, or this may be a fresh session started with --new-session."));
    metaEl.textContent = "0 turns · new session";
  } else {
    const accepted = turns.filter((t) => t.spoken).length;
    metaEl.textContent = isFlowSession()
      ? `${turns.length} turns · flow mode · resumed session`
      : `${turns.length} turns · ${accepted} accepted · ${turns.length - accepted} rejected · resumed session`;
    mount(listEl, turns.map((t) => (t.mode === "flow" ? renderFlowTurnCard(t) : renderTurnCard(t))));
  }

  const input = document.getElementById("draft-input");
  input.value = State.draft;
  input.oninput = (e) => { State.draft = e.target.value; };
  input.onkeydown = (e) => { if (e.key === "Enter" && !State.sending) doSend(); };
  const sendBtn = document.getElementById("send-btn");
  sendBtn.disabled = State.sending;
  sendBtn.onclick = () => { if (!State.sending) doSend(); };

  const note = document.getElementById("send-note");
  note.textContent = State.sendNote || defaultSendNote();
  note.className = "send-note mono" + (State.sendBad ? " bad" : "");
}

function defaultSendNote() {
  const sid = (State.session && State.session.session_id) || "this session";
  if (isFlowSession()) {
    return `Enter or Send calls POST /api/turn — Studio Flow mode, resuming ${sid}.`;
  }
  return `Enter or Send calls POST /api/turn against pipeline.run_turn, resuming ${sid}.`;
}

function renderTurnCard(t) {
  const repaired = t.pass_count > 1;
  const badge = t.decision === "accept" ? (repaired ? "repaired · accepted" : "accepted") : (t.decision || "rejected");
  const tone = t.decision === "accept" ? (repaired ? TONE.fix : TONE.ok) : TONE.bad;
  const selected = t.turn_id === State.currentTurnId;
  const summaryParts = [];
  summaryParts.push(`${t.pass_count} pass${t.pass_count === 1 ? "" : "es"}`);
  if (!isNil(t.packet_bytes)) summaryParts.push(`${t.packet_bytes} B packet`);
  if (!isNil(t.elapsed_seconds)) summaryParts.push(`${Number(t.elapsed_seconds).toFixed(1)} s`);
  summaryParts.push((t.violations && t.violations.length) ? t.violations.map((v) => String(v).split(":")[0]).join(", ") : "no violations");
  // /api/session's turn summary does not carry applied_updates — that
  // level of detail is only on the full TurnTrace (see stage 12 once a
  // turn is selected), so it is intentionally left off the card.

  const obs = t.observations || [];
  const flagLine = obs.length ? obs[0].label + (obs.length > 1 ? ` +${obs.length - 1} more` : "") : null;

  const card = h("div", { class: "turn-card" + (selected ? " selected" : "") }, [
    h("div", { class: "turn-card-top" }, [
      h("span", { class: "turn-card-time mono" }, (t.started_at || "").slice(11, 19) || t.started_at || ""),
      h("span", { class: "turn-card-badge mono", style: { color: tone } }, badge),
      h("span", { class: "spacer" }),
      h("span", { class: "turn-card-n mono" }, `turn ${t.n}`),
    ]),
    h("div", { class: "turn-card-msg-row" }, [
      h("span", { class: "turn-card-rule" }),
      h("p", { class: "turn-card-user" }, t.user_input),
    ]),
  ]);
  if (t.spoken && t.answer) {
    card.appendChild(h("p", { class: "turn-card-spoken" }, t.answer));
  } else if (!t.spoken) {
    card.appendChild(h("div", { class: "turn-card-withheld" }, [
      h("p", { class: "turn-card-withheld-text" }, t.answer || "(no candidate answer recorded)"),
      h("p", { class: "turn-card-withheld-label mono" }, "withheld — never spoken, never stored"),
    ]));
  }
  card.appendChild(h("div", { class: "turn-card-summary" }, h("span", null, summaryParts.join(" · "))));
  if (flagLine) {
    card.appendChild(h("div", { class: "turn-card-flag" }, [h("span", null, "◇"), h("span", null, flagLine)]));
  }
  card.onclick = () => selectTurn(t.turn_id);
  return card;
}

// Flow's own turn card — a deliberately different renderer, not a branch
// inside renderTurnCard, so the pipeline card above stays byte-identical.
// Flow has no accept/reject court (spec point 5): every nonempty
// generation reaches the terminal, so there is no "withheld" state and no
// accept/reject tone to borrow — the badge and rule use the neutral
// `--ctx-recent` token already in the palette (see FLOW_KIND_COLOR), never
// the ok/bad status colors, so a flow turn never reads as an acceptance
// verdict it never went through.
function renderFlowTurnCard(t) {
  const selected = t.turn_id === State.currentTurnId;
  const obs = t.observations || [];
  const flagLine = obs.length ? obs[0].label + (obs.length > 1 ? ` +${obs.length - 1} more` : "") : null;

  const card = h("div", { class: "turn-card flow" + (selected ? " selected" : "") }, [
    h("div", { class: "turn-card-top" }, [
      h("span", { class: "turn-card-time mono" }, (t.started_at || "").slice(11, 19) || t.started_at || ""),
      h("span", { class: "turn-card-badge mono", style: { color: "var(--ctx-recent)" } }, "flow"),
      h("span", { class: "spacer" }),
      h("span", { class: "turn-card-n mono" }, `turn ${t.n}`),
    ]),
    h("div", { class: "turn-card-msg-row" }, [
      h("span", { class: "turn-card-rule" }),
      h("p", { class: "turn-card-user" }, t.user_input),
    ]),
  ]);
  if (t.answer) {
    card.appendChild(h("p", { class: "turn-card-spoken" }, t.answer));
  }
  const summaryParts = [`reply_status ${t.error ? "error" : "ok"}`, `${obs.length} observation${obs.length === 1 ? "" : "s"}`];
  card.appendChild(h("div", { class: "turn-card-summary" }, h("span", null, summaryParts.join(" · "))));
  if (flagLine) {
    card.appendChild(h("div", { class: "turn-card-flag" }, [h("span", null, "◇"), h("span", null, flagLine)]));
  }
  card.onclick = () => selectTurn(t.turn_id);
  return card;
}

async function selectTurn(turnId) {
  setState({ currentTurnId: turnId, stage: null, flowPanel: null, play: -1, ops: "", opsErr: false, replayResult: null, brief: null, obs: null, obsPending: null });
  await loadTrace(turnId);
}

async function loadTrace(turnId) {
  if (State.traceCache.has(turnId)) {
    setState({ trace: State.traceCache.get(turnId) });
    return;
  }
  try {
    const trace = await Api.getTrace(turnId);
    State.traceCache.set(turnId, trace);
    if (State.currentTurnId === turnId) setState({ trace });
  } catch (e) {
    if (State.currentTurnId === turnId) {
      setState({ trace: null, ops: `failed to load trace: ${e.message}`, opsErr: true });
    }
  }
}

// ---------------------------------------------------------- pipeline head

function renderPipelineHead() {
  const idsEl = document.getElementById("pipeline-ids");
  const utterEl = document.getElementById("utterance");
  const flagsEl = document.getElementById("flags");
  const replayBtn = document.getElementById("replay-btn");

  const t = State.trace;
  const summary = currentTurnSummary();
  const flow = isFlowTurn(t, summary);
  utterEl.classList.toggle("flow", flow);

  if (!t && !summary) {
    idsEl.textContent = "";
    mount(utterEl, h("div", { class: "empty-placeholder" }, "Select a turn on the left, or send a message, to see it travel through the pipeline."));
    clear(flagsEl);
    replayBtn.disabled = true;
    replayBtn.textContent = "▶ replay stages";
    replayBtn.onclick = null;
    return;
  }

  if (flow) {
    renderFlowPipelineHead(t, summary, idsEl, utterEl, flagsEl, replayBtn);
    return;
  }

  replayBtn.disabled = false;
  replayBtn.textContent = "▶ replay stages";
  replayBtn.onclick = () => doReplayWalkthrough();

  if (t) {
    idsEl.textContent = `turn ${summary ? summary.n : "—"} · ${(t.passes[0] && t.passes[0].packet_id) || NA} · ${(currentPass() && currentPass().receipt_id) || NA}`;
  } else {
    idsEl.textContent = `turn ${summary.n} · loading…`;
  }

  const userText = t ? t.user_input : summary.user_input;
  const decision = t ? t.final_decision.decision : summary.decision;
  const label = t ? t.final_decision.label : summary.label;
  const passCount = t ? t.passes.length : summary.pass_count;
  const started = t ? t.started_at : summary.started_at;
  const completed = t ? t.completed_at : summary.completed_at;
  const dur = isoDurationSeconds(started, completed);
  const tone = decision === "accept" ? TONE.ok : (decision === "reject" ? TONE.bad : TONE.warn);

  mount(utterEl, [
    h("div", { class: "utterance-left" }, [
      h("div", { class: "utterance-eyebrow" }, "The human utterance"),
      h("p", { class: "utterance-msg" }, userText),
    ]),
    h("div", { class: "utterance-right" }, [
      h("span", null, started || NA),
      h("span", null, `${userText.length} chars · ${bytesUtf8(userText)} B`),
      h("span", { style: { color: tone } }, label || decision || NA),
      h("span", null, `${dur != null ? dur.toFixed(0) : NA} s · ${passCount} pass${passCount === 1 ? "" : "es"}`),
    ]),
  ]);

  if (!showObservations() || !t) { clear(flagsEl); return; }
  const all = t.observations || [];
  const shown = all.slice(0, 2).map((f) => h("div", { class: "banner" }, [
    h("span", { class: "banner-label" }, f.label),
    h("span", { class: "banner-detail" }, f.detail),
  ]));
  if (all.length > 2) {
    shown.push(h("div", { class: "banner more" }, [
      h("span", { class: "banner-label mono more" }, `+${all.length - 2} more`),
      h("span", { class: "banner-detail" }, all.slice(2).map((f) => f.label.toLowerCase()).join(" · ") + " — see the panel this stage flagged ◇ on"),
    ]));
  }
  mount(flagsEl, shown);
}

// Flow's own utterance-box + observation-banner rendering. Same DOM
// targets and the same `.banner` component the pipeline branch above
// uses for its observations (never rejection-red — the banner tokens are
// the same neutral amber `--obs-*` set either way), just built from a
// FlowTrace's own fields instead of final_decision/passes.
function renderFlowPipelineHead(t, summary, idsEl, utterEl, flagsEl, replayBtn) {
  replayBtn.disabled = true;
  replayBtn.textContent = "flow — no stage replay";
  replayBtn.onclick = null;

  if (t) {
    idsEl.textContent = `turn ${summary ? summary.n : "—"} · flow · reply_status=${t.reply_status || NA}`;
  } else {
    idsEl.textContent = `turn ${summary.n} · flow · loading…`;
  }

  const userText = t ? t.user_input : summary.user_input;
  const started = t ? t.started_at : summary.started_at;
  const completed = t ? t.completed_at : summary.completed_at;
  const dur = isoDurationSeconds(started, completed);

  mount(utterEl, [
    h("div", { class: "utterance-left" }, [
      h("div", { class: "utterance-eyebrow", style: { color: "var(--ctx-recent)" } }, "The human utterance · flow"),
      h("p", { class: "utterance-msg" }, userText),
    ]),
    h("div", { class: "utterance-right" }, [
      h("span", null, started || NA),
      h("span", null, `${userText.length} chars · ${bytesUtf8(userText)} B`),
      h("span", { style: { color: "var(--ctx-recent)" } }, "FLOW"),
      h("span", null, `${dur != null ? dur.toFixed(0) : NA} s`),
    ]),
  ]);

  if (!showObservations() || !t) { clear(flagsEl); return; }
  const all = t.observations || [];
  const shown = all.slice(0, 2).map((f) => h("div", { class: "banner" }, [
    h("span", { class: "banner-label" }, f.label),
    h("span", { class: "banner-detail" }, f.detail),
  ]));
  if (all.length > 2) {
    shown.push(h("div", { class: "banner more" }, [
      h("span", { class: "banner-label mono more" }, `+${all.length - 2} more`),
      h("span", { class: "banner-detail" }, all.slice(2).map((f) => f.label.toLowerCase()).join(" · ") + " — see FIELD AFTER for every observation."),
    ]));
  }
  mount(flagsEl, shown);
}

// ------------------------------------------------------------- stage nav

function renderStageNav() {
  const navEl = document.getElementById("stage-nav");
  const railFlow = document.getElementById("rail-flow");
  const spine = layout() === "spine";
  railFlow.className = "rail-flow " + (spine ? "layout-spine" : "layout-rail");
  navEl.className = "stage-nav " + (spine ? "spine" : "rail");

  const t = State.trace;
  const summary = currentTurnSummary();
  if (isFlowTurn(t, summary)) {
    return renderFlowStageNav(navEl);
  }

  const sel = selectedStage();
  const chips = [];
  for (let id = 1; id <= 12; id++) {
    const st = State.trace ? stageByIndex(id) : null;
    const status = State.play >= 0
      ? (id < State.play ? "completed" : id === State.play ? "active" : "waiting")
      : (st ? st.status : "waiting");
    const name = st ? st.name.replace(/_/g, " ").toUpperCase() : STATIC_STAGE_NAMES[id];
    const flag = State.play < 0 && st ? !!st.flag : false;
    const on = sel === id;
    const chip = h("button", {
      class: "stage-chip" + (on ? " selected" : ""), type: "button",
      style: on ? { borderColor: "var(--sel-border)" } : null,
    }, [
      h("span", { class: "stage-chip-dot", style: { background: STAGE_STATUS_TONE[status] || TONE.wait } }),
      h("span", { class: "stage-chip-num" }, String(id).padStart(2, "0")),
      h("span", { class: "stage-chip-name", style: { color: on ? "var(--text-strong)" : (status === "waiting" ? "var(--text-decorative-1)" : "var(--text-dim)") } }, name),
    ]);
    if (flag) chip.appendChild(h("span", { class: "stage-chip-flag" }, "◇"));
    chip.onclick = () => setState({ stage: id, play: -1 });
    chips.push(chip);
  }
  mount(navEl, chips);
}

// Flow's own 3-chip nav — FIELD BEFORE / WHAT TRAVELED / FIELD AFTER
// (FLOW_PANELS) — reusing the exact same `.stage-chip` component the
// pipeline's 12-chip nav uses above, just fewer of them and selected via
// `State.flowPanel` instead of `State.stage`/`selectedStage()`.
function renderFlowStageNav(navEl) {
  const sel = selectedFlowPanel();
  const chips = FLOW_PANELS.map((p) => {
    const on = sel === p.id;
    const chip = h("button", {
      class: "stage-chip" + (on ? " selected" : ""), type: "button",
      style: on ? { borderColor: "var(--sel-border)" } : null,
    }, [
      h("span", { class: "stage-chip-dot", style: { background: "var(--ctx-recent)" } }),
      h("span", { class: "stage-chip-name", style: { color: on ? "var(--text-strong)" : "var(--text-dim)" } }, p.label),
    ]);
    chip.onclick = () => setState({ flowPanel: p.id });
    return chip;
  });
  mount(navEl, chips);
}

// ------------------------------------------------------------- panel ----

function renderPanel() {
  const headerEl = document.getElementById("panel-header");
  const blocksEl = document.getElementById("panel-blocks");
  const sel = selectedStage();

  if (sel > 0) {
    const t = State.trace;
    const summary = currentTurnSummary();
    if (isFlowTurn(t, summary)) {
      if (!t) {
        mount(headerEl, [h("h3", { class: "panel-title" }, "Loading flow turn…"), h("span", { class: "panel-sub" }, "")]);
        mount(blocksEl, h("div", { class: "empty-placeholder" }, "Fetching this turn's field trace."));
        return;
      }
      renderFlowPanel(t, headerEl, blocksEl);
      return;
    }
  }

  if (!State.trace && sel > 0) {
    mount(headerEl, [h("h3", { class: "panel-title" }, "No turn selected"), h("span", { class: "panel-sub" }, "pick a turn on the left, or send one")]);
    mount(blocksEl, h("div", { class: "empty-placeholder" }, "Nothing to show yet."));
    return;
  }

  const P = buildPanel(sel);
  const srcLabel = P.srcModule ? `${P.srcModule}:${P.srcLine || "?"} · ${P.srcFn || ""}` : (P.srcStatic || "—");
  const srcBtn = h("button", { class: "panel-src-btn mono", type: "button", title: "copy source path" }, srcLabel);
  srcBtn.onclick = async () => {
    const res = await copyToClipboard(P.srcModule ? `${P.srcModule}:${P.srcLine || ""}` : srcLabel);
    setState({ ops: res.ok ? `copied ${res.bytes} bytes to clipboard` : "clipboard unavailable", opsErr: !res.ok });
  };
  mount(headerEl, [
    h("h3", { class: "panel-title" }, P.title),
    h("span", { class: "panel-sub" }, P.sub),
    h("span", { class: "spacer" }),
    srcBtn,
  ]);

  const blockNodes = P.blocks.map((b) => {
    const wrap = h("div", { class: "block" });
    if (b.label) {
      wrap.appendChild(h("div", { class: "block-label-row" }, [
        h("span", { class: "block-label" }, b.label),
        b.note ? h("span", { class: "block-note" }, b.note) : null,
      ]));
    }
    wrap.appendChild(renderBlock(b));
    return wrap;
  });
  mount(blocksEl, blockNodes);
}

// ----------------------------------------------------------- block types

function renderBlock(b) {
  switch (b.type) {
    case "note": return renderNote(b);
    case "text": return renderText(b);
    case "kv": return renderKv(b);
    case "bars": return renderBars(b);
    case "meter": return renderMeter(b);
    case "cards": return renderCards(b);
    case "checks": return renderChecks(b);
    case "split": return renderSplit(b);
    case "diff": return renderDiff(b);
    case "sections": return renderSections(b);
    case "code": return renderCode(b);
    case "groups": return renderGroups(b);
    case "toggles": return renderToggles(b);
    case "gate": return renderGate(b);
    case "ask": return renderAsk(b);
    default: return h("div", { class: "empty-placeholder" }, `unknown block type: ${b.type}`);
  }
}

function renderNote(b) { return h("div", { class: `blk-note ${b.kind || "info"}` }, b.body); }
function renderText(b) { return h("p", { class: "blk-text", style: { borderLeftColor: b.tone || TONE.ok } }, b.body); }

function renderKv(b) {
  return h("div", { class: "blk-kv" }, (b.rows || []).map((r) => h("div", { class: "kv-row" }, [
    h("span", { class: "kv-key" }, r.k),
    h("span", { class: "kv-val", style: { color: r.tone || "var(--text-body-1)", textDecoration: r.strike ? "line-through" : "none" } }, r.v),
    h("span", { class: "kv-meta" }, r.meta || ""),
  ])));
}

function renderBars(b) {
  const rows = b.rows || [];
  const track = h("div", { class: "bars-track" }, rows.map((r) => h("span", { style: { flex: "0 0 auto", width: r.pctW, background: r.tone } })));
  const lines = rows.map((r) => h("div", { class: "bars-row" }, [
    h("span", { class: "bars-swatch", style: { background: r.tone } }),
    h("span", { class: "bars-label" }, r.k),
    h("span", { class: "bars-minitrack" }, h("span", { class: "bars-minifill", style: { width: r.pctW, background: r.tone } })),
    h("span", { class: "bars-pct" }, r.pctLabel),
    h("span", { class: "bars-bytes" }, r.bytes),
  ]));
  return h("div", { class: "blk-bars" }, [track, ...lines]);
}

function renderMeter(b) {
  return h("div", { class: "blk-meter" }, [
    h("div", { class: "meter-track" }, h("span", { class: "meter-fill", style: { width: b.pct, background: b.tone } })),
    h("div", { class: "meter-labels" }, [h("span", null, b.used), h("span", null, b.max)]),
  ]);
}

function renderCards(b) {
  return h("div", { class: "blk-cards" }, (b.rows || []).map((r) => {
    const card = h("div", { class: "card", style: { background: r.bg || "var(--surface-alt-row-2)", borderColor: r.border || "var(--hairline)" } }, [
      h("div", { class: "card-head" }, [
        h("span", { class: "card-title", style: { color: r.tone } }, r.title),
        h("span", { class: "spacer" }),
        h("span", { class: "card-meta" }, r.meta || ""),
      ]),
      h("div", { class: "card-body-row" }, [h("span", { class: "card-rule" }), h("p", { class: "card-body" }, r.body)]),
      r.body2 ? h("p", { class: "card-body2" }, r.body2) : null,
    ]);
    if (r.flag) card.appendChild(h("p", { class: "card-flag" }, `◇ ${r.flag}`));
    return card;
  }));
}

function renderChecks(b) {
  return h("div", { class: "blk-checks" }, (b.rows || []).map((r) => h("div", { class: "checks-row", style: { background: r.bg || "transparent" } }, [
    h("span", { class: "checks-status", style: { color: r.tone } }, r.status),
    h("span", { class: "checks-name" }, r.name),
    h("div", { class: "checks-mid" }, [
      h("span", { class: "checks-reason" }, r.reason),
      h("span", { class: "checks-examined mono" }, `examined: ${r.examined}`),
    ]),
    h("span", { class: "checks-severity" }, r.severity || ""),
  ])));
}

function renderSplit(b) {
  return h("div", { class: "blk-split" }, [
    h("div", null, [h("div", { class: "split-label" }, b.leftLabel), h("pre", { class: "split-pre" }, b.left)]),
    h("div", null, [h("div", { class: "split-label" }, b.rightLabel), h("pre", { class: "split-pre" }, b.right)]),
  ]);
}

function renderDiff(b) {
  const header = h("div", { class: "diff-header" }, [h("span", null, "field"), h("span", null, b.leftLabel), h("span", null, b.rightLabel)]);
  const rows = (b.rows || []).map((r) => h("div", { class: "diff-row" }, [
    h("span", { class: "diff-key" }, r.k),
    h("span", { class: "diff-before", style: { color: r.leftTone || "var(--text-dim)", textDecoration: r.strike ? "line-through" : "none" } }, r.before),
    h("span", { class: "diff-after", style: { color: r.rightTone || "var(--text-dim)" } }, r.after),
  ]));
  return h("div", { class: "blk-diff" }, [header, ...rows]);
}

function renderSections(b) {
  return h("div", { class: "blk-sections" }, (b.rows || []).map((r) => h("div", { class: "section-block" }, [
    h("div", { class: "section-head", style: { borderLeftColor: r.tone } }, [
      h("span", { class: "section-label", style: { color: r.tone } }, r.k),
      h("span", { class: "spacer" }),
      h("span", { class: "section-bytes" }, `${r.bytes} · ${r.pctLabel}`),
      h("span", { class: "section-src" }, r.src),
    ]),
    h("pre", { class: "section-body" }, r.body),
  ])));
}

function renderCode(b) {
  const pre = h("pre", { class: "code-pre" }, b.body);
  const btn = h("button", { class: "code-copy mono", type: "button" }, "copy");
  btn.onclick = async () => {
    const res = await copyToClipboard(b.body);
    setState({ ops: res.ok ? `copied ${res.bytes} bytes to clipboard` : "clipboard unavailable", opsErr: !res.ok });
  };
  return h("div", { class: "blk-code" }, [btn, pre]);
}

function renderGroups(b) {
  return h("div", { class: "blk-groups" }, (b.rows || []).map((g) => h("div", { class: "group" }, [
    h("div", { class: "group-head", style: { color: g.tone, borderLeftColor: g.tone } }, g.title),
    h("div", { class: "group-items" }, (g.items || []).map((i) => h("div", { class: "group-item" }, [
      h("span", { class: "group-item-key" }, i.k),
      h("span", { class: "group-item-val", style: { color: i.tone || "var(--text-body-1)" } }, i.v),
      h("span", { class: "group-item-meta" }, i.meta || ""),
    ]))),
  ])));
}

function renderToggles(b) {
  return h("div", { class: "blk-toggles" }, (b.rows || []).map((r) => {
    const row = h("button", { class: "toggle-row" + (r.locked ? " locked" : ""), type: "button" }, [
      h("span", {
        class: "toggle-box",
        style: {
          borderColor: r.locked ? "var(--hover-border)" : (r.on ? "var(--status-ok)" : "var(--hover-border)"),
          background: r.on ? (r.locked ? "var(--text-meta)" : "var(--status-ok)") : "transparent",
        },
      }, r.on ? "✓" : ""),
      h("span", { class: "toggle-label", style: { color: r.on ? "var(--text-body-strong)" : "var(--text-label)" } }, r.label),
      h("span", { class: "toggle-meta" }, r.meta || ""),
    ]);
    if (!r.locked && r.onClick) row.onclick = r.onClick;
    return row;
  }));
}

function renderGate(b) {
  const rows = (b.rows || []).map((r) => h("div", { class: "gate-row" }, [
    h("span", { class: "gate-key" }, r.k),
    h("span", { class: "gate-val", style: { color: r.tone } }, r.v),
    h("span", { class: "gate-meta" }, r.meta),
  ]));
  const sendBtn = h("button", { class: "gate-send", type: "button" }, "Send to Claude");
  sendBtn.onclick = b.onSend;
  const cancelBtn = h("button", { class: "gate-cancel", type: "button" }, "Cancel");
  cancelBtn.onclick = b.onCancel;
  return h("div", { class: "blk-gate" }, [
    ...rows,
    h("div", { class: "gate-actions" }, [sendBtn, cancelBtn, h("span", { class: "spacer" }), h("span", { class: "gate-hint" }, "review the rows above — this is the only send")]),
  ]);
}

function renderAsk(b) {
  const buttons = (b.buttons || []).map((q) => {
    const btn = h("button", { class: "ask-btn" + (q.active ? " active" : ""), type: "button" }, q.label);
    btn.onclick = q.onClick;
    return btn;
  });
  const parts = [h("div", { class: "ask-buttons" }, buttons)];
  if (b.status) parts.push(h("span", { class: "ask-status mono", style: { color: b.statusTone } }, b.status));
  if (b.body) parts.push(h("div", { class: "ask-response" }, b.body));
  return h("div", { class: "blk-ask" }, parts);
}

// ================================================================ panels ==

function buildPanel(id) {
  if (id === 1) return panelInput();
  if (id === 2) return panelStateLoad();
  if (id === 3) return panelRecentMemory();
  if (id === 4) return panelPacketCompile();
  if (id === 5) return panelEdgeBudget();
  if (id === 6) return panelKernelRequest();
  if (id === 7) return panelRawOutput();
  if (id === 8) return panelParse();
  if (id === 9) return panelValidate();
  if (id === 10) return panelRepair();
  if (id === 11) return panelDecision();
  if (id === 12) return panelPersist();
  if (id === 0) return panelRuntime();
  if (id === -1) return panelAttractor();
  if (id === -2) return panelObserver();
  if (id === -3) return panelReplay();
  return { title: "Unknown panel", sub: "", srcStatic: "—", blocks: [{ type: "note", kind: "bad", body: `no panel builder for id ${id}` }] };
}

function withSource(panel, stageIndex) {
  const st = stageByIndex(stageIndex);
  if (st) { panel.srcModule = st.source_module; panel.srcLine = st.source_line; panel.srcFn = st.source_function; }
  else panel.srcStatic = "— source resolves once a trace is loaded";
  return panel;
}

// ============================================================= flow panel ==
//
// Interior View for Flow turns: three panels — FIELD BEFORE, WHAT
// TRAVELED, FIELD AFTER — built entirely from the same block types
// (text/kv/bars/cards/diff/note) the pipeline panels above already use.
// No new block type, no new panel chrome: renderFlowPanel below reuses
// renderBlock() and the panel-header markup verbatim.

function renderFlowPanel(t, headerEl, blocksEl) {
  const P = buildFlowPanel(selectedFlowPanel(), t);
  const srcLabel = P.srcStatic || "—";
  const srcBtn = h("button", { class: "panel-src-btn mono", type: "button", title: "copy source path" }, srcLabel);
  srcBtn.onclick = async () => {
    const res = await copyToClipboard(srcLabel);
    setState({ ops: res.ok ? `copied ${res.bytes} bytes to clipboard` : "clipboard unavailable", opsErr: !res.ok });
  };
  mount(headerEl, [
    h("h3", { class: "panel-title" }, P.title),
    h("span", { class: "panel-sub" }, P.sub),
    h("span", { class: "spacer" }),
    srcBtn,
  ]);
  const blockNodes = P.blocks.map((b) => {
    const wrap = h("div", { class: "block" });
    if (b.label) {
      wrap.appendChild(h("div", { class: "block-label-row" }, [
        h("span", { class: "block-label" }, b.label),
        b.note ? h("span", { class: "block-note" }, b.note) : null,
      ]));
    }
    wrap.appendChild(renderBlock(b));
    return wrap;
  });
  mount(blocksEl, blockNodes);
}

function buildFlowPanel(id, t) {
  if (id === "traveled") return flowPanelTraveled(t);
  if (id === "field_after") return flowPanelFieldAfter(t);
  return flowPanelFieldBefore(t);
}

// ---- FIELD BEFORE --------------------------------------------------------
//
// flow.compose_field's own output (FlowTrace.field_before): the current
// message (always primary, never byte-budgeted) plus the small number of
// live field elements that won a slot this turn, each with salience and
// momentum (spec point 3).

function flowPanelFieldBefore(t) {
  const fb = t.field_before || {};
  const selected = fb.selected || [];
  const blocks = [];

  blocks.push({
    type: "text", label: "Current message", note: "always primary — never counted against the field's byte budget",
    body: fb.current_message || t.user_input, tone: CTX_COLOR.current_user_input,
  });

  blocks.push({
    type: "kv", label: "Composition", rows: [
      { k: "intents detected", v: joinOr(fb.intents, "(none)"), meta: "context_field.detect_intents" },
      { k: "live elements carried", v: String(fb.live_element_count ?? 0), meta: "flow_field.json, before this turn" },
      { k: "candidate pool this turn", v: String(fb.candidate_pool_size ?? 0), meta: "carried + newly-relevant canonical/thread candidates" },
      { k: "selected into the prompt", v: `${selected.length} element(s)`, meta: "bin-packed by score within the byte budget" },
      { k: "byte budget", v: `${fb.selected_bytes ?? 0} / ${fb.byte_budget ?? 0} B`, meta: "bounds carried elements only, never the current message" },
      { k: "relevant canonical state", v: String((fb.relevant_canonical || []).length), meta: "entered only because it matched this message's intents" },
    ],
  });

  if (selected.length) {
    blocks.push({
      type: "bars", label: "Salience", note: "0–1 — how strongly each element competed for a slot this turn",
      rows: selected.map((e) => ({
        k: `${e.kind}: ${clipStr(e.content, 46)}`,
        tone: FLOW_KIND_COLOR[e.kind] || "var(--text-dim)",
        pctW: `${Math.round(Math.min(1, e.salience) * 100)}%`,
        pctLabel: e.salience.toFixed(2),
        bytes: `${bytesUtf8(e.content)} B`,
      })),
    });
    blocks.push({
      type: "bars", label: "Momentum", note: "recent strengthening — decays toward 0 when nothing continues an element",
      rows: selected.map((e) => ({
        k: `${e.kind}: ${clipStr(e.content, 46)}`,
        tone: FLOW_KIND_COLOR[e.kind] || "var(--text-dim)",
        pctW: `${Math.round(Math.min(1, e.momentum) * 100)}%`,
        pctLabel: e.momentum.toFixed(2),
        bytes: `${e.turns_seen} turn${e.turns_seen === 1 ? "" : "s"} seen`,
      })),
    });
    blocks.push({
      type: "cards", label: "Selected field elements — full content", note: "what actually traveled alongside the current message",
      rows: selected.map((e) => ({
        title: `${e.kind} · ${e.source}`,
        tone: FLOW_KIND_COLOR[e.kind] || "var(--text-dim)",
        meta: `salience ${e.salience.toFixed(2)} · momentum ${e.momentum.toFixed(2)} · ${e.element_id}`,
        body: e.content,
        body2: e.topic_tags && e.topic_tags.length ? `tags: ${e.topic_tags.join(", ")}` : null,
      })),
    });
  } else {
    blocks.push({ type: "note", kind: "info", body: "No carried field elements were selected this turn — the field was quiet, or nothing yet outcompeted the byte budget. The current message still travels on its own; the field is never forced to fill a slot." });
  }

  if ((fb.relevant_canonical || []).length) {
    blocks.push({
      type: "kv", label: "Canonical state judged relevant to this message", note: "context_field.detect_intents + _tags_match — never entered unconditionally",
      rows: fb.relevant_canonical.map((c) => ({ k: c.kind, v: c.content, meta: c.source_key || "" })),
    });
  }

  return { title: "Field before", sub: "the living field this turn began with", srcStatic: "conditioned_kernel/flow.py · compose_field", blocks };
}

// ---- WHAT TRAVELED --------------------------------------------------------
//
// The composed prompt (no output schema, no evidence requirement — spec
// point 4) and the model's own reply, verbatim (spec point 5: every
// nonempty generation reaches the terminal).

function flowPanelTraveled(t) {
  const cp = t.composed_prompt || {};
  const blocks = [];
  blocks.push({
    type: "kv", label: "Transport", rows: [
      { k: "model", v: cp.model || (t.runtime_config && t.runtime_config.model) || NA, meta: "" },
      { k: "reply_status", v: t.reply_status || NA, meta: "generate.RunStatus", tone: (t.reply_status === "completed" || t.reply_status === "dry_run") ? TONE.ok : (t.error ? TONE.warn : undefined) },
      { k: "output schema", v: "none — plain conversational reply, no evidence_used, no candidate JSON", meta: "build_flow_model_input sends no `format` key", tone: TONE.skip },
      { k: "transport error", v: t.error || "none", meta: "", tone: t.error ? TONE.warn : undefined },
    ],
  });
  blocks.push({ type: "text", label: "System prompt", body: cp.system || NA, tone: CTX_COLOR.system_instructions });
  blocks.push({ type: "text", label: "Composed user message", note: "field context (prose) + the person's message, always labeled and unburied", body: cp.user || NA, tone: CTX_COLOR.current_user_input });
  blocks.push({ type: "text", label: "Verbatim reply — what reached you", note: "every nonempty generation is displayed; no accept/reject branch", body: t.displayed_text || NA, tone: TONE.ok });
  if (!isNil(t.raw_reply) && t.raw_reply !== t.displayed_text) {
    blocks.push({ type: "text", label: "Raw reply, before display formatting", body: t.raw_reply, tone: TONE.skip });
  }
  return { title: "What traveled", sub: "the composed prompt and the model's own words, unedited", srcStatic: "conditioned_kernel/flow.py · build_flow_model_input, run_flow_turn", blocks };
}

// ---- FIELD AFTER ----------------------------------------------------------
//
// integrate_field's own actions (strengthened/created/decayed/softened/
// dropped — spec point 8), shown as a before→after diff, plus this turn's
// observations (spec point 6: descriptive register, never a rejection
// reason — reused verbatim from the ◇ banner styling, never status-bad red).

function flowPanelFieldAfter(t) {
  const fb = t.field_before || {};
  const fa = t.field_after || {};
  const actions = t.integration_actions || [];
  const observations = t.observations || [];
  const beforeById = {};
  (fb.selected || []).forEach((e) => { beforeById[e.element_id] = e; });
  const afterById = {};
  (fa.elements || []).forEach((e) => { afterById[e.element_id] = e; });

  const blocks = [];

  blocks.push({
    type: "kv", label: "Observations", note: "descriptive only — never a rejection reason, never blocking (spec point 6)",
    rows: observations.length
      ? observations.map((o) => ({ k: o.label, v: o.detail, meta: "" }))
      : [{ k: "—", v: "no observations recorded for this turn", meta: "" }],
  });

  const countOf = (action) => actions.filter((a) => a.action === action).length;
  blocks.push({
    type: "kv", label: "What happened after the exchange", note: "integrate_field — runs strictly after display, never before (spec point 8)",
    rows: [
      { k: "strengthened", v: String(countOf("strengthened")), tone: FLOW_ACTION_TONE.strengthened },
      { k: "created", v: String(countOf("created")), tone: FLOW_ACTION_TONE.created },
      { k: "decayed", v: String(countOf("decayed")), tone: FLOW_ACTION_TONE.decayed },
      { k: "softened", v: String(countOf("softened")), tone: FLOW_ACTION_TONE.softened },
      { k: "dropped", v: String(countOf("dropped")), tone: FLOW_ACTION_TONE.dropped },
      { k: "field size now", v: `${(fa.elements || []).length} element(s)`, meta: "bounded carry" },
      { k: "turn_count", v: String(fa.turn_count ?? NA), meta: "flow_field.json" },
    ],
  });

  if (actions.length) {
    blocks.push({
      type: "diff", label: "Salience, before → after", note: "(new) = created this turn · (dropped) = fell below the eviction floor",
      leftLabel: "before", rightLabel: "after",
      rows: actions.map((a) => {
        const before = beforeById[a.element_id];
        const after = afterById[a.element_id];
        const beforeStr = before ? before.salience.toFixed(2) : (a.action === "created" ? "(new)" : "—");
        const afterStr = after ? after.salience.toFixed(2) : "(dropped)";
        return {
          k: `${a.action} · ${a.element_id}`,
          before: beforeStr,
          after: afterStr,
          rightTone: FLOW_ACTION_TONE[a.action] || "var(--text-dim)",
          strike: a.action === "dropped",
        };
      }),
    });
    blocks.push({
      type: "kv", label: "Detail", note: "integrate_field's own reason, one per action",
      rows: actions.map((a) => ({ k: a.action, v: a.detail, meta: a.element_id, tone: FLOW_ACTION_TONE[a.action] })),
    });
  } else {
    blocks.push({ type: "note", kind: "info", body: "No integration actions were recorded for this turn." });
  }

  if ((fa.elements || []).length) {
    blocks.push({
      type: "cards", label: "Field now", note: `${(fa.elements || []).length} element(s) carried into the next turn`,
      rows: (fa.elements || []).map((e) => ({
        title: `${e.kind} · ${e.source}`,
        tone: FLOW_KIND_COLOR[e.kind] || "var(--text-dim)",
        meta: `salience ${e.salience.toFixed(2)} · momentum ${e.momentum.toFixed(2)} · turns_seen ${e.turns_seen}`,
        body: e.content,
      })),
    });
  }

  return { title: "Field after", sub: "how the substrate shifted once the exchange was observed", srcStatic: "conditioned_kernel/flow.py · integrate_field", blocks };
}

// ---- 01 INPUT -----------------------------------------------------------

function panelInput() {
  const t = State.trace;
  const summary = currentTurnSummary();
  const blocks = [];
  blocks.push({ type: "text", label: "Exact user message", note: "verbatim, before compilation", body: t.user_input, tone: CTX_COLOR.current_user_input });
  const pktUserInput = t.packet && t.packet.user_input;
  const clipped = !isNil(pktUserInput) && pktUserInput !== t.user_input;
  blocks.push({
    type: "kv", label: "Measured", rows: [
      { k: "timestamp", v: t.started_at || NA, meta: "submitted" },
      { k: "session_id", v: t.session_id, meta: "resumed" },
      { k: "characters", v: String(t.user_input.length), meta: "" },
      { k: "utf-8 bytes", v: String(bytesUtf8(t.user_input)), meta: "" },
      { k: "clipped by budget", v: clipped ? "yes" : "no — packet.user_input matches the raw message", meta: "edge.enforce_packet_budget", tone: clipped ? TONE.warn : undefined },
      { k: "turn", v: `${summary ? summary.n : "—"} of ${turnsList().length}`, meta: "" },
    ],
  });
  blocks.push({ type: "note", kind: "info", body: "This string is written into packet.user_input and nowhere else. Every other byte in the packet was chosen by the substrate, not by you." });
  return withSource({ title: "What you said", sub: "the water — unchanged by anything downstream", blocks }, 1);
}

// ---- 02 STATE LOAD --------------------------------------------------------

function panelStateLoad() {
  const t = State.trace;
  const pkt = t.packet || {};
  const digest = pkt.state_digest || {};
  const blocks = [];
  blocks.push({
    type: "kv", label: "packet.state_digest", note: "reached the packet, verbatim", rows: [
      { k: "goal", v: digest.goal || NA, meta: !isNil(digest.goal) ? `${bytesUtf8(digest.goal)} B` : "" },
      { k: "active_profile", v: digest.active_profile || NA, meta: "" },
      { k: "session_id", v: digest.session_id || NA, meta: "" },
      { k: "open_thread_count", v: isNil(digest.open_thread_count) ? NA : String(digest.open_thread_count), meta: "" },
      { k: "receipt_count_24h", v: isNil(digest.receipt_count_24h) ? NA : String(digest.receipt_count_24h), meta: "" },
    ],
  });
  const facts = pkt.facts || [];
  blocks.push({
    type: "kv", label: "packet.facts", note: `${facts.length} kept (already max_facts-trimmed)`,
    rows: facts.length ? facts.map((f, i) => ({ k: `facts[${i}]`, v: f, meta: `${bytesUtf8(f)} B` }))
      : [{ k: "—", v: "no facts in this packet", meta: "" }],
  });
  const threads = pkt.open_threads || [];
  blocks.push({
    type: "kv", label: "packet.open_threads", note: `${threads.length} open (already max_open_threads-trimmed)`,
    rows: threads.length ? threads.map((th) => ({ k: th.id, v: th.title, meta: "" }))
      : [{ k: "—", v: "no open threads in this packet", meta: "" }],
  });
  if (pkt.authoritative_obligation) {
    const obl = pkt.authoritative_obligation;
    blocks.push({
      type: "kv", label: "packet.authoritative_obligation", note: "companion path only · authoritative_state.resolve_obligation",
      rows: [
        { k: "kind", v: obl.kind, tone: CTX_COLOR.durable_state },
        ...(obl.claims || []).map((c, i) => ({ k: `claims[${i}]`, v: c, meta: "→ fact slot", tone: TONE.ok })),
        { k: "fallback_answer", v: obl.fallback_answer || NA, meta: "held in reserve unless the model failed the required substrings" },
        { k: "source_fields", v: joinOr(obl.source_fields), meta: "" },
      ],
    });
  }
  blocks.push({
    type: "note", kind: "info",
    body: "Only the fields already present in the compiled packet are shown here, exactly as they reached the model. This trace does not carry a separate record of every field SubstrateState.load() read from state/current.json, state/threads.json, or state/methods.json before compilation, so a full loaded-vs-omitted breakdown per source file is not shown — a StageTrace.input_summary for stage 02 would settle it.",
  });
  return withSource({ title: "Substrate state loaded for this turn", sub: "what reached the packet, exactly as it reached it", blocks }, 2);
}

// ---- 03 RECENT MEMORY -----------------------------------------------------

function panelRecentMemory() {
  const t = State.trace;
  const pkt = t.packet || {};
  const recent = pkt.recent_turns || [];
  const blocks = [];
  const totalBytes = recent.length ? bytesUtf8(JSON.stringify(recent)) : 0;

  blocks.push({
    type: "kv", label: "Selection", rows: [
      { k: "in this packet", v: String(recent.length), meta: "packet.recent_turns, already selected and clipped" },
      { k: "clip applied on write", v: "user → 200 chars · answer → 280 chars", meta: "state._clip_text", tone: TONE.warn },
      { k: "total dialogue bytes", v: `${totalBytes} B`, meta: "JSON.stringify(packet.recent_turns), utf-8" },
      { k: "ordering", v: "oldest → newest", meta: "validate.prior_accepted_answer reads the last entry only", tone: TONE.warn },
    ],
  });

  if (recent.length) {
    blocks.push({
      type: "cards", label: "Turns carried into this packet", note: "each entry as the model saw it",
      rows: recent.map((r, i) => {
        const last = i === recent.length - 1;
        return {
          title: `recent_turns[${i}]${last ? " · compared by the stale check" : " · never compared"}`,
          tone: last ? TONE.fix : TONE.skip,
          meta: `${bytesUtf8(JSON.stringify(r))} B · ${r.ts || NA}`,
          body: r.user, body2: r.answer,
          bg: last ? "#1D1E22" : "var(--surface-alt-row-2)", border: last ? "#2C2F36" : "var(--hairline)",
        };
      }),
    });
    const stg = stageByIndex(3);
    if (stg && stg.flag) {
      blocks.push({ type: "note", kind: "warn", body: "This turn's stage chip is flagged ◇ for memory repetition — see the pinned observation banner above the rail for the computed pairwise figure (compute.memory_repetition, ≥60% Jaccard)." });
    }
  } else {
    blocks.push({ type: "note", kind: "info", body: "recent_turns is empty in this packet — either the session began fresh (--new-session), or nothing has been accepted into dialogue memory yet. Whatever the model said in this turn, it did not carry prior dialogue." });
  }
  return withSource({ title: "Recent dialogue memory", sub: "byte-capped ring of accepted turns · oldest dropped first", blocks }, 3);
}

// ---- 04 PACKET COMPILE ----------------------------------------------------

function extractSystemText(modelInput) {
  // Presentational mirror of compute._system_text_from_model_input — pulls
  // the literal system string back out of the real request body rather than
  // keeping a second, driftable copy of it.
  if (!modelInput) return "";
  const payload = modelInput.payload || {};
  if (modelInput.mode === "chat_json") {
    const sys = (payload.messages || []).find((m) => m.role === "system");
    return sys ? String(sys.content || "") : "";
  }
  const prompt = String(payload.prompt || "");
  const marker = "\n\nARRIVAL_PACKET:\n";
  const idx = prompt.indexOf(marker);
  return idx >= 0 ? prompt.slice(0, idx) : "";
}

function panelPacketCompile() {
  const t = State.trace;
  const pkt = t.packet || {};
  const pass = currentPass();
  const rows = t.context_share_bytes || [];
  const total = rows.reduce((a, r) => a + r.bytes, 0);
  const blocks = [];

  blocks.push({
    type: "bars", label: "Context share", note: `share of the ${total} model-input bytes — bytes, not attention`,
    rows: rows.map((r) => ({ k: r.source, tone: CTX_COLOR[r.source_id] || "var(--text-dim)", pctW: `${r.share_pct}%`, pctLabel: fmtPct(r.share_pct), bytes: fmtBytes(r.bytes) })),
  });
  blocks.push({ type: "note", kind: "info", body: "This is a byte census of what was sent. It is not influence, attention, or causal contribution — nothing here can know how the kernel weighted these bytes internally." });

  // Context field: AVAILABLE → SELECTED → inference field (companion path)
  const field = pkt.context_field || {};
  if (field && (field.selected || field.omitted || field.selection_records)) {
    const sel = field.selected || [];
    const om = field.omitted || [];
    const recs = field.selection_records || [];
    const reasonById = {};
    recs.forEach((r) => { if (r && r.contribution_id) reasonById[r.contribution_id] = r.reason; });
    const selLines = sel.length
      ? sel.map((c) => `✓ ${c.contribution_id} [${c.kind}/${c.authority}] ${c.source_module}.${c.source_key}\n  ${String(c.content || "").slice(0, 160)}\n  reason: ${reasonById[c.contribution_id] || "selected"}`).join("\n\n")
      : "(none — quiet substrate for this turn)";
    const omLines = om.length
      ? om.slice(0, 30).map((row) => {
          const c = row.contribution || row;
          const cid = row.contribution_id || c.contribution_id;
          return `· ${cid} (${c.kind || "?"}): ${row.reason || reasonById[cid] || "omitted"}`;
        }).join("\n") + (om.length > 30 ? `\n… +${om.length - 30} more` : "")
      : "(none)";
    blocks.push({
      type: "code",
      label: "Context field — SELECTED contributions",
      note: `AVAILABLE ${field.available_count ?? "?"} → SELECTED ${field.selected_count ?? sel.length} · intents ${JSON.stringify(pkt.intents || [])}`,
      body: selLines,
    });
    blocks.push({
      type: "code",
      label: "Context field — OMITTED (withheld from inference)",
      note: "substrate still holds these; they were not narrated into this turn",
      body: omLines,
    });
  }

  const byId = {};
  rows.forEach((r) => { byId[r.source_id] = r; });
  const systemText = extractSystemText(pass && pass.model_input);
  const schema = pass && pass.model_input && pass.model_input.payload && pass.model_input.payload.format;
  // Companion path: show the actual user message content (selected context + current human message)
  let companionUserBody = "";
  try {
    const mi = pass && pass.model_input;
    const msgs = (mi && mi.payload && mi.payload.messages) || [];
    const um = msgs.find((m) => m.role === "user");
    if (um) companionUserBody = String(um.content || "");
  } catch (_) { /* ignore */ }
  const sectionRows = [
    { id: "current_user_input", src: "packet.user_input", body: t.user_input },
    { id: "recent_dialogue", src: "packet.recent_turns (selected only)", body: (pkt.recent_turns || []).length ? pkt.recent_turns.map((r, i) => `[${i}] user: ${r.user}\n    answer: ${r.answer}`).join("\n") : "[]" },
    { id: "durable_state", src: "selected facts · open_threads", body: `goal (control plane): ${(pkt.state_digest || {}).goal || ""}\n\nselected facts:\n${(pkt.facts || []).length ? (pkt.facts || []).map((f, i) => `  [${i}] ${f}`).join("\n") : "  (none)"}\n\nselected open_threads:\n${(pkt.open_threads || []).length ? (pkt.open_threads || []).map((th) => `  ${th.id} — ${th.title}`).join("\n") : "  (none)"}${pkt.authoritative_obligation ? `\n\nauthoritative_obligation (${pkt.authoritative_obligation.kind}):\n${(pkt.authoritative_obligation.claims || []).map((c) => `  must preserve: ${c}`).join("\n")}` : ""}` },
    { id: "system_instructions", src: `build_model_input${pkt.repair ? " + packet.repair" : ""}`, body: systemText + (pkt.repair ? `\n\nrepair (pass ${pkt.repair.pass_index}):\n${pkt.repair.instruction}\n${(pkt.repair.hints || []).map((hh) => `  · ${hh}`).join("\n")}` : "") },
    { id: "output_schema", src: "CANDIDATE_FORMAT", body: schema ? JSON.stringify(schema, null, 2) : NA },
    { id: "constraints", src: "constraints · acceptance_contract", body: JSON.stringify({ constraints: pkt.constraints, acceptance_contract: pkt.acceptance_contract }, null, 2) },
  ];
  if (companionUserBody) {
    sectionRows.splice(1, 0, {
      id: "compiled_inference_field",
      src: "model_input.user (Selected context + Current human message)",
      body: companionUserBody,
    });
  }
  blocks.push({
    type: "sections", label: "Sources", note: "labelled blocks — companion uses selected field only",
    rows: sectionRows.map((s) => {
      const r = byId[s.id];
      return { k: r ? r.source : s.id, tone: CTX_COLOR[s.id] || "var(--text-dim)", bytes: r ? fmtBytes(r.bytes) : NA, pctLabel: r ? fmtPct(r.share_pct) : NA, src: s.src, body: s.body };
    }),
  });

  const mismatchNote = (t.notes || []).find((n) => n.startsWith("packet_bytes mismatch"));
  blocks.push({
    type: "code", label: "Raw arrival packet",
    body: JSON.stringify(pkt, null, 2),
    note: `packet_bytes ${isNil(t.packet_bytes) ? NA : t.packet_bytes + " B"} (edge.packet_byte_size, logged if available else recomputed)${mismatchNote ? " — " + mismatchNote : ""}`,
  });
  return withSource({ title: "Packet composition", sub: "the arrival packet, by where each byte came from", blocks }, 4);
}

// ---- 05 EDGE BUDGET --------------------------------------------------------

function panelEdgeBudget() {
  const t = State.trace;
  const pkt = t.packet || {};
  const profile = (t.runtime_config && t.runtime_config.profile) || {};
  const maxBytes = profile.max_packet_bytes;
  const usedPct = (!isNil(t.packet_bytes) && maxBytes) ? (t.packet_bytes / maxBytes) * 100 : null;
  const blocks = [];

  blocks.push({
    type: "meter", label: "Packet size", note: "after trimming",
    pct: usedPct != null ? `${Math.min(usedPct, 100).toFixed(1)}%` : "0%",
    tone: usedPct != null && usedPct > 80 ? TONE.warn : TONE.ok,
    used: `${isNil(t.packet_bytes) ? NA : t.packet_bytes + " B"} used${usedPct != null ? ` (${fmtPct(usedPct)})` : ""}`,
    max: `max_packet_bytes ${isNil(maxBytes) ? NA : maxBytes + " B"}`,
  });

  blocks.push({
    type: "kv", label: "Packet after budget enforcement", note: "edge.enforce_packet_budget, strict=true",
    rows: [
      { k: "facts", v: `${(pkt.facts || []).length} entries`, meta: `max_facts=${isNil(profile.max_facts) ? NA : profile.max_facts}` },
      { k: "open_threads", v: `${(pkt.open_threads || []).length} entries, titles clipped to 120`, meta: `max_open_threads=${isNil(profile.max_open_threads) ? NA : profile.max_open_threads}` },
      { k: "recent_turns", v: `${(pkt.recent_turns || []).length} entries, user 200 / answer 280`, meta: "" },
      { k: "user_input", v: `${(pkt.user_input || "").length} chars`, meta: "cap 800" },
      { k: "state_digest.goal", v: `${((pkt.state_digest || {}).goal || "").length} chars`, meta: "cap 240" },
      { k: "constraints.max_words", v: String((pkt.constraints || {}).max_words), meta: `bounded by profile.max_answer_words=${isNil(profile.max_answer_words) ? NA : profile.max_answer_words}` },
    ],
  });

  const stg = stageByIndex(5);
  if (stg && stg.flag) {
    const dropped = (t.observations || []).find((o) => o.label === "Budget dropped state");
    blocks.push({ type: "note", kind: "warn", body: dropped ? dropped.detail : "edge.enforce_packet_budget dropped fact slot(s) this turn at max_facts — see the pinned observation banner above for which ones." });
  }

  blocks.push({
    type: "kv", label: "Budget levers, in the order edge.enforce_packet_budget applies them", note: "verified against the current checkout of edge.py",
    rows: [
      { k: "1 · facts", v: `truncate to max_facts=${isNil(profile.max_facts) ? NA : profile.max_facts}`, meta: "silent" },
      { k: "2 · open_threads", v: `truncate to max_open_threads=${isNil(profile.max_open_threads) ? NA : profile.max_open_threads}`, meta: "silent" },
      { k: "3 · clip", v: "titles 120 · recent user 200 / answer 280 · user_input 800 · goal 240", meta: "silent" },
      { k: "4 · constraints.max_words", v: `bounded to profile.max_answer_words=${isNil(profile.max_answer_words) ? NA : profile.max_answer_words}`, meta: "silent" },
      { k: "5 · repair prose", v: "violations to 5 × 80 chars, instruction to 160", meta: "only if still over max_packet_bytes" },
      { k: "6 · recent_turns", v: "drop oldest until under budget", meta: "only if still over" },
      { k: "7 · facts from the end", v: "drop until 2 remain", meta: "only if still over" },
      { k: "8 · BudgetError", v: "fail closed (strict=true)", meta: "last resort", tone: TONE.skip },
    ],
  });
  return withSource({ title: "Edge budget enforcement", sub: "what the profile cut before the packet left the substrate", blocks }, 5);
}

// ---- 06 KERNEL REQUEST -----------------------------------------------------

function panelKernelRequest() {
  const t = State.trace;
  const pass = currentPass();
  const rc = t.runtime_config || {};
  const profile = rc.profile || {};
  const path = rc.mode === "chat_json" ? "/api/chat" : "/api/generate";
  const startTs = idTimestamp(pass && pass.packet_id) || (t.stages && t.started_at);
  const endTs = idTimestamp(pass && pass.candidate_id);
  const blocks = [];

  blocks.push({
    type: "kv", label: "Transport", rows: [
      { k: "method", v: `POST ${(rc.base_url || "")}${path}`, meta: "localhost, no auth", tone: TONE.ok },
      { k: "model", v: rc.model || NA, meta: "" },
      { k: "stream", v: String(!!profile.stream), meta: "full candidate buffered before acceptance" },
      { k: "think", v: String(!!rc.think), meta: "reasoning channel off at the API, not by prompt", tone: TONE.skip },
      { k: "keep_alive", v: rc.keep_alive || NA, meta: "" },
      { k: "timeout", v: isNil(profile.timeout_s) ? NA : `${profile.timeout_s} s`, meta: "profile.timeout_s" },
      { k: "request start", v: startTs || NA, meta: "parsed from packet_id's embedded timestamp" },
      { k: "request end", v: endTs || NA, meta: (pass && pass.telemetry && !isNil(pass.telemetry.elapsed)) ? `${Number(pass.telemetry.elapsed).toFixed(3)} s measured` : "not logged for this pass" },
      { k: "packet_hash", v: (pass && pass.model_input && pass.model_input.packet_hash) || NA, meta: "compile.packet_hash — carried on model_input, not the packet itself" },
      { k: "secrets", v: "none present", meta: "nothing to redact on a local packet", tone: TONE.skip },
    ],
  });
  blocks.push({
    type: "kv", label: "options", rows: [
      { k: "temperature", v: isNil(rc.temperature) ? NA : String(rc.temperature), meta: "" },
      { k: "seed", v: isNil(rc.seed) ? NA : String(rc.seed), meta: "fixed for reproducibility" },
      { k: "num_ctx", v: isNil(rc.num_ctx) ? NA : String(rc.num_ctx), meta: "tokens" },
    ],
  });
  blocks.push({ type: "note", kind: "info", body: "packet_id and created_at are stripped from the model input by compile.build_model_input — they change every build, and leaving them in would make an identical state + input produce a different prompt each run. They stay on the packet for receipts." });

  const modelInput = pass && pass.model_input;
  blocks.push({
    type: "code", label: "Request body",
    body: modelInput ? JSON.stringify(modelInput.payload || modelInput, null, 2) : NA,
    note: modelInput ? `${bytesUtf8(JSON.stringify(modelInput.payload || modelInput))} B` : "model_input not present on this pass",
  });
  return withSource({ title: "Kernel request", sub: "exactly what was POSTed to Ollama", blocks }, 6);
}

// ---- 07 RAW OUTPUT ---------------------------------------------------------

function panelRawOutput() {
  const t = State.trace;
  const pass = currentPass();
  const tel = pass && pass.telemetry;
  const profile = (t.runtime_config && t.runtime_config.profile) || {};
  const blocks = [];
  blocks.push({
    type: "kv", label: "Transport result", rows: [
      { k: "status", v: (tel && !isNil(tel.status)) ? tel.status : NA, meta: "RunStatus", tone: tel && tel.status === "completed" ? TONE.ok : undefined },
      { k: "final response chars", v: (tel && !isNil(tel.chars)) ? String(tel.chars) : NA, meta: "final_response_chars" },
      { k: "thinking channel", v: t.runtime_config && t.runtime_config.think ? ((tel && !isNil(tel.think)) ? `${tel.think} chars` : NA) : "disabled", meta: "think=false — 0 chars emitted", tone: TONE.skip },
      { k: "elapsed", v: (tel && !isNil(tel.elapsed)) ? `${Number(tel.elapsed).toFixed(3)} s` : "not logged for this pass", meta: !isNil(profile.timeout_s) ? `of ${profile.timeout_s} s timeout` : "" },
      { k: "transport error", v: t.error || "none", meta: "", tone: t.error ? TONE.bad : undefined },
      { k: "output null?", v: pass && pass.raw_text == null ? "yes" : "no", meta: "empty string would be a real observed answer; null is not", tone: TONE.skip },
    ],
  });
  blocks.push({
    type: "code", label: "Response text",
    body: pass && !isNil(pass.raw_text) ? pass.raw_text : NA,
    note: `logs/candidates.jsonl raw_text, verbatim${(tel && !isNil(tel.chars)) ? ` · transport measured ${tel.chars} chars, which counts the kernel's own whitespace` : ""}`,
  });
  blocks.push({ type: "note", kind: "info", body: "Thinking channel: disabled. The profile sets think=false, so no reasoning channel was emitted and none is shown. When a thinking-capable kernel does emit one, it is recorded as separate telemetry and never used as the answer." });
  return withSource({ title: "Raw model output", sub: "before the substrate touches it", blocks }, 7);
}

// ---- 08 PARSE ---------------------------------------------------------------

function panelParse() {
  const t = State.trace;
  const pass = currentPass();
  const blocks = [];
  const parsed = pass ? {
    candidate_id: pass.candidate_id, packet_id: pass.packet_id, pass_index: pass.pass_index,
    answer: pass.answer, evidence_used: pass.evidence_used, next_state: { thread_touch: pass.thread_touch },
  } : {};
  blocks.push({
    type: "split", label: "Side by side", note: "return_path.parse.parse_candidate extracts the first JSON object",
    leftLabel: "raw model text", left: pass && !isNil(pass.raw_text) ? pass.raw_text : NA,
    rightLabel: "parsed candidate", right: JSON.stringify(parsed, null, 2),
  });
  blocks.push({
    type: "kv", label: "Parse result", rows: [
      { k: "answer", v: pass ? `present · ${pass.answer.length} chars` : NA, meta: "" },
      { k: "evidence_used", v: pass ? `array of ${pass.evidence_used.length}` : NA, meta: "" },
      { k: "next_state.thread_touch", v: pass && pass.thread_touch.length ? pass.thread_touch.join(", ") : "[]", meta: pass && pass.thread_touch.length ? "ids checked at validation" : "" },
      { k: "authoritative_kind", v: (pass && pass.authoritative_kind) || "—", meta: pass && pass.authoritative_fallback ? "substrate fallback was substituted" : "", tone: pass && pass.authoritative_fallback ? TONE.warn : undefined },
    ],
  });
  blocks.push({ type: "note", kind: "info", body: "status: proposed in the candidate object means model-proposed, not trusted — everything from here down is the substrate deciding whether to believe it." });
  return withSource({ title: "Candidate parsing", sub: "raw text → candidate object", blocks }, 8);
}

// ---- 09 VALIDATE --------------------------------------------------------------

function panelValidate() {
  const t = State.trace;
  const pass = currentPass();
  const blocks = [];
  const viol = (pass && pass.violations) || [];
  const adv = (pass && pass.advisories) || [];

  if (pass && Array.isArray(pass.checks) && pass.checks.length) {
    blocks.push({
      type: "checks", label: "Checks", note: `acceptance_mode=${(t.runtime_config || {}).acceptance_mode || "?"} · ${viol.length} violations · ${adv.length} advisories`,
      rows: pass.checks.map((c) => ({ ...c, tone: { PASS: TONE.ok, FAIL: TONE.bad, ADVISORY: TONE.warn, SKIP: TONE.skip }[c.status] })),
    });
  } else {
    const rows = [];
    viol.forEach((v) => rows.push({ status: "FAIL", name: String(v).split(":")[0], reason: String(v), examined: "pass.violations", severity: "hard", tone: TONE.bad, bg: "var(--note-bad-bg)" }));
    adv.forEach((a) => rows.push({ status: "ADVISORY", name: String(a), reason: String(a), examined: "pass.advisories", severity: "recorded, not enforced", tone: TONE.warn }));
    blocks.push({
      type: "checks", label: "Checks", note: `${viol.length} violations · ${adv.length} advisories · PASS checks not individually enumerated`,
      rows: rows.length ? rows : [{ status: "PASS", name: "no violations or advisories", reason: "this pass recorded neither", examined: "pass.violations, pass.advisories", severity: "", tone: TONE.ok }],
    });
    blocks.push({ type: "note", kind: "info", body: "This trace does not carry the full validate_candidate check-by-check table (17–19 named checks with individual PASS/FAIL/ADVISORY/SKIP status). Only violations (FAIL) and advisories (ADVISORY) are recorded per pass; every other named check is implied PASS by its absence from both lists. A pass.checks[] field on PassTrace, populated the same way compute.py already builds citation_audit()/labeled_evidence_pool(), would settle the rest." });
  }

  if (Array.isArray(pass && pass.citation_audit) && pass.citation_audit.length) {
    blocks.push({
      type: "kv", label: "Citations examined", note: "evidence_used vs the packet evidence pool · validate._evidence_ok",
      rows: pass.citation_audit.map((a) => ({ k: a.status, v: a.citation, meta: a.reason, tone: a.status === "MATCHED" ? TONE.ok : TONE.bad })),
    });
    const misses = pass.citation_audit.filter((a) => a.status === "MISS");
    if (misses.length) {
      blocks.push({
        type: "cards", label: "Why each miss missed",
        note: "compute._explain_miss — truncation checked first (state._clip_text's 280-char write cap), then a genuine near-miss (Jaccard ≥ 0.6), else simply not in the packet",
        rows: misses.map((m) => ({
          title: clipStr(m.citation, 90),
          meta: [m.kind, isNil(m.similarity) ? null : `${Math.round(m.similarity * 100)}% similar`].filter(Boolean).join(" · "),
          body: m.reason,
          body2: m.match ? `nearest pool entry: ${m.match.source_key} — “${clipStr(m.match.value, 100)}”` : "no pool entry is close enough to name.",
          tone: TONE.bad,
        })),
      });
    }
  } else if (pass && pass.evidence_used && pass.evidence_used.length) {
    blocks.push({
      type: "kv", label: "evidence_used", note: "not audited by this trace — citation-vs-pool matching is not yet attached to PassTrace",
      rows: pass.evidence_used.map((e, i) => ({ k: `[${i}]`, v: e, meta: "" })),
    });
  }

  if (Array.isArray(pass && pass.evidence_pool) && pass.evidence_pool.length) {
    blocks.push({
      type: "kv", label: "Evidence pool", note: "validate._packet_evidence_pool, labelled — every fact, thread id/title, recent turn, and the goal, lowercased and deduped",
      rows: pass.evidence_pool.map((e) => ({ k: e.source_key, v: e.value, meta: `${e.length} chars` })),
    });
  }

  blocks.push({
    type: "kv", label: "Receipt", rows: [
      { k: "receipt_id", v: (pass && pass.receipt_id) || NA, meta: "" },
      { k: "violations", v: viol.length ? viol.join(" · ") : "[]", meta: "hard", tone: viol.length ? TONE.bad : TONE.ok },
      { k: "advisories", v: adv.length ? adv.join(" · ") : "[]", meta: "recorded, not enforced", tone: adv.length ? TONE.warn : TONE.skip },
      { k: "word_count", v: pass ? String(pass.word_count) : NA, meta: "" },
      { k: "decision", v: (pass && pass.decision) || NA, meta: "", tone: pass && pass.decision === "accept" ? TONE.ok : TONE.bad },
    ],
  });
  if (viol.length) {
    blocks.push({ type: "note", kind: "bad", body: `Rejected by a closed-set rule in return_path/validate.py: ${viol.map((v) => String(v).split(":")[0]).join(" and ")}. The kernel produced something; the substrate refused it — this is a heuristic rejection, not evidence the JSON itself was malformed.` });
  }
  blocks.push({ type: "note", kind: "info", body: "apply_companion_grounding only substitutes substrate evidence when every citation the model gave is empty or under 12 characters — a wrong-but-long citation is rejected on its own merits; no citation at all is quietly filled in." });
  return withSource({ title: "Validation", sub: "every closed-set check, individually where the trace carries it", blocks }, 9);
}

// ---- 10 REPAIR ------------------------------------------------------------

function panelRepair() {
  const t = State.trace;
  const blocks = [];
  if (t.passes.length === 1) {
    blocks.push({ type: "note", kind: "info", body: "Repair not invoked. Pass 0 was decided with no repair loop entered — the one-repair boundary is unchanged." });
    return withSource({ title: "Repair path", sub: "one pass, hard boundary", blocks }, 10);
  }
  const p0 = t.passes[0], pN = t.passes[t.passes.length - 1];
  const profile = (t.runtime_config && t.runtime_config.profile) || {};
  const repairBlock = pN.packet && pN.packet.repair;

  blocks.push({
    type: "kv", label: "Trigger", rows: [
      { k: "decision at pass 0", v: p0.decision || NA, meta: "return_path.assess.assess", tone: TONE.fix },
      { k: "violations that triggered it", v: joinOr(p0.violations), meta: "", tone: TONE.bad },
      { k: "max_repair", v: isNil(profile.max_repair) ? NA : String(profile.max_repair), meta: "profile — no second repair is possible", tone: TONE.warn },
    ],
  });
  blocks.push({ type: "split", label: "Candidate before and after repair", note: "same packet plus a repair block", leftLabel: "pass 0 answer", left: p0.answer, rightLabel: `pass ${pN.pass_index} answer`, right: pN.answer });
  if (repairBlock) {
    blocks.push({
      type: "kv", label: "Repair instruction embedded in packet.repair", rows: [
        { k: "instruction", v: repairBlock.instruction, meta: `${bytesUtf8(repairBlock.instruction)} B` },
        ...(repairBlock.hints || []).map((hh, i) => ({ k: `hints[${i}]`, v: hh, meta: "", tone: CTX_COLOR.system_instructions })),
        { k: "allowed_thread_ids", v: joinOr(repairBlock.allowed_thread_ids, ", "), meta: "" },
        { k: "allowed_evidence_samples", v: joinOr(repairBlock.allowed_evidence_samples), meta: "" },
        { k: "example_json", v: JSON.stringify(repairBlock.example_json), meta: "shape only", tone: TONE.skip },
      ],
    });
  } else {
    blocks.push({ type: "note", kind: "warn", body: "packet.repair was not present on the final pass's stored packet — the repair instruction embedded in the request cannot be shown for this turn." });
  }
  blocks.push({
    type: "kv", label: "Second validation", rows: [
      { k: "violations at pass 0", v: joinOr(p0.violations), meta: "", tone: TONE.bad },
      { k: `violations at pass ${pN.pass_index}`, v: joinOr(pN.violations), meta: "", tone: pN.violations.length ? TONE.bad : TONE.ok },
      { k: "word_count", v: `${p0.word_count} → ${pN.word_count}`, meta: "" },
      { k: "outcome", v: pN.decision === "accept" ? "repair resolved the violation" : "repair did not resolve it", meta: "", tone: pN.decision === "accept" ? TONE.ok : TONE.bad },
    ],
  });
  const changed = p0.answer !== pN.answer;
  blocks.push({
    type: "note", kind: pN.decision === "accept" ? "info" : "warn",
    body: pN.decision === "accept"
      ? "Repair changed the answer. The final-pass answer differs from pass 0 and cleared validation. Whether it is a better answer is a judgement the substrate does not make — that is what the operator marks below are for."
      : changed
        ? "Repair produced a different answer, but it still failed validation. The exact token-overlap figure is not carried on this trace — compare the two answers above as raw strings."
        : "Repair changed nothing: the final-pass answer is byte-identical to pass 0 and carries the same violation. The repair hints were present in the packet and had no effect on this kernel.",
  });
  return withSource({ title: "Repair path", sub: "one pass, hard boundary", blocks }, 10);
}

// ---- 11 DECISION ------------------------------------------------------------

function panelDecision() {
  const t = State.trace;
  const pass = currentPass();
  const fd = t.final_decision || {};
  const blocks = [];
  const accepted = fd.decision === "accept";
  blocks.push({
    type: "note", kind: accepted ? "info" : "bad",
    body: accepted ? `${fd.label || "ACCEPTED"}. The candidate cleared validation on pass ${pass ? pass.pass_index : "?"} and was spoken to you.` : `${fd.label || "REJECTED"}. The candidate failed validation. Nothing was spoken.`,
  });
  blocks.push({
    type: "text", label: accepted ? "Final user-visible response" : "Candidate that was never spoken",
    note: accepted ? "printed as ck> " : "printed only as a reject notice on stderr",
    body: accepted ? fd.answer : (pass ? pass.answer : NA),
    tone: accepted ? TONE.ok : TONE.bad,
  });
  const dur = isoDurationSeconds(t.started_at, t.completed_at);
  const enteredMemory = t.persistence && t.persistence.recent_turn_appended;
  const durableMutated = t.persistence && (t.persistence.applied_updates || []).some((a) => String(a).startsWith("touched_thread"));
  const profile = (t.runtime_config && t.runtime_config.profile) || {};
  blocks.push({
    type: "kv", label: "Outcome", rows: [
      { k: "decision", v: fd.decision || NA, meta: "", tone: accepted ? TONE.ok : TONE.bad },
      { k: "violations", v: joinOr(fd.violations, "none"), meta: "", tone: (fd.violations || []).length ? TONE.bad : TONE.ok },
      { k: "advisory warnings", v: joinOr(fd.advisories, "none"), meta: "not enforced in companion mode", tone: (fd.advisories || []).length ? TONE.warn : TONE.skip },
      { k: "entered recent dialogue", v: enteredMemory ? "yes" : "no", meta: enteredMemory ? "this answer will shape later turns" : "memory untouched", tone: enteredMemory ? TONE.warn : TONE.skip },
      { k: "durable state mutation permitted", v: durableMutated ? "yes — thread timestamps only" : "no", meta: "apply_state_updates is allowlisted: thread_touch only" },
      { k: "passes used", v: `${t.passes.length} of ${isNil(profile.max_repair) ? "?" : profile.max_repair + 1}`, meta: "" },
      { k: "turn duration", v: dur != null ? `${dur.toFixed(3)} s` : NA, meta: "started_at → completed_at" },
      { k: "generation time", v: (pass && pass.telemetry && !isNil(pass.telemetry.elapsed)) ? `${Number(pass.telemetry.elapsed).toFixed(3)} s` : NA, meta: "measured at the client" },
    ],
  });
  if (accepted && (fd.advisories || []).length) {
    blocks.push({ type: "note", kind: "warn", body: `Accepted with an unenforced finding: ${fd.advisories.join(", ")}. In companion mode that is by design. The same candidate in measurement mode would be rejected.` });
  }
  return withSource({ title: "Final decision", sub: "what the substrate did with the candidate", blocks }, 11);
}

// ---- 12 PERSIST -------------------------------------------------------------

function panelPersist() {
  const t = State.trace;
  const pass = currentPass();
  const persistence = t.persistence || {};
  const applied = persistence.applied_updates || [];
  const appended = persistence.recent_turn_appended;
  const touched = applied.filter((a) => String(a).startsWith("touched_thread"));
  const blocks = [];

  blocks.push({
    type: "groups", label: "What survived this turn", note: "three stores, never conflated",
    rows: [
      { title: "Conversational memory", tone: appended ? TONE.warn : TONE.skip, items: [
        { k: "recent turn appended", v: appended ? "yes" : "no", meta: appended ? "state.append_recent_turn wrote user + answer into current.json" : "rejected or poisoned candidates never enter memory", tone: appended ? TONE.warn : TONE.skip },
        { k: "stored answer", v: appended ? clipStr(pass ? pass.answer : "", 280) : "—", meta: appended ? "clipped to 280 chars on write — later turns compile against this string" : "" },
      ] },
      { title: "Durable substrate state", tone: touched.length ? TONE.active : TONE.skip, items: [
        { k: "state keys changed", v: touched.length ? "threads[].last_touched_at" : "none", meta: touched.length ? touched.map((x) => String(x).split(":")[1]).join(", ") : "no allowlisted delta applied", tone: touched.length ? TONE.active : TONE.skip },
        { k: "goal · facts · thread titles", v: "unchanged", meta: "the model cannot write these; no path exists", tone: TONE.skip },
      ] },
      { title: "Operational logs", tone: TONE.fix, items: [
        { k: "logs/receipts.jsonl", v: `+${t.passes.length} line${t.passes.length > 1 ? "s" : ""}`, meta: "one per pass", tone: TONE.fix },
        { k: "logs/candidates.jsonl", v: `+${t.passes.length} line${t.passes.length > 1 ? "s" : ""}`, meta: "raw_text preserved verbatim, including rejected candidates", tone: TONE.fix },
        { k: "logs/errors.jsonl", v: t.error ? "written" : "no write", meta: t.error ? String(t.error) : "no budget or transport error this turn", tone: t.error ? TONE.bad : TONE.skip },
      ] },
    ],
  });
  blocks.push({
    type: "note", kind: appended ? "warn" : "info",
    body: appended
      ? "This answer is now part of the riverbed. It will be compiled into every following packet until the byte cap pushes it out, and the model will read it as prior dialogue it should stay consistent with."
      : "Nothing entered conversational memory this turn. Only the operational logs grew — which is why the trace you are reading still exists.",
  });
  blocks.push({ type: "code", label: "Recorded outcome", body: JSON.stringify(persistence.outcome || {}, null, 2), note: "return_path.accept.accept_candidate's own outcome object" });
  return withSource({ title: "Persistence", sub: "an answer being spoken is not the same as it becoming true", blocks }, 12);
}

// ---- 0 RUNTIME & EDGE PROFILE ------------------------------------------------

function panelRuntime() {
  const rc = currentRuntimeConfig() || {};
  const profile = rc.profile || {};
  const blocks = [];
  blocks.push({
    type: "kv", label: "Kernel", rows: [
      { k: "model", v: rc.model || NA, meta: "runtime_config.model", tone: TONE.ok },
      { k: "mode", v: rc.mode || NA, meta: rc.mode === "chat_json" ? "/api/chat" : "/api/generate" },
      { k: "think", v: String(!!rc.think), meta: "reasoning channel", tone: TONE.skip },
      { k: "temperature", v: isNil(rc.temperature) ? NA : String(rc.temperature), meta: "" },
      { k: "seed", v: isNil(rc.seed) ? NA : String(rc.seed), meta: "fixed" },
      { k: "num_ctx", v: isNil(rc.num_ctx) ? NA : String(rc.num_ctx), meta: "tokens" },
      { k: "keep_alive", v: rc.keep_alive || NA, meta: "" },
      { k: "timeout_s", v: isNil(profile.timeout_s) ? NA : String(profile.timeout_s), meta: "" },
      { k: "stream", v: String(!!profile.stream), meta: "substrate buffers the full candidate", tone: TONE.skip },
      { k: "endpoint", v: rc.base_url || NA, meta: "localhost only" },
    ],
  });
  blocks.push({
    type: "kv", label: "Edge profile", rows: [
      { k: "profile_id", v: profile.profile_id || NA, meta: "configs/edge/*.json", tone: CTX_COLOR.durable_state },
      { k: "target_device", v: profile.target_device || NA, meta: profile.arch || "" },
      { k: "ram_gb", v: isNil(profile.ram_gb) ? NA : String(profile.ram_gb), meta: "planning bound" },
      { k: "max_packet_bytes", v: isNil(profile.max_packet_bytes) ? NA : String(profile.max_packet_bytes), meta: "packet budget" },
      { k: "max_facts", v: isNil(profile.max_facts) ? NA : String(profile.max_facts), meta: "" },
      { k: "max_open_threads", v: isNil(profile.max_open_threads) ? NA : String(profile.max_open_threads), meta: "" },
      { k: "max_answer_words", v: isNil(profile.max_answer_words) ? NA : String(profile.max_answer_words), meta: "" },
      { k: "max_repair", v: isNil(profile.max_repair) ? NA : String(profile.max_repair), meta: "one pass, hard boundary" },
      { k: "working set (est.)", v: (!isNil(profile.estimated_model_ram_mb) && !isNil(profile.estimated_substrate_ram_mb)) ? `${profile.estimated_model_ram_mb + profile.estimated_substrate_ram_mb} MB` : NA, meta: "estimate" },
      { k: "cloud / sensors / tools", v: `${!!profile.cloud} / ${!!profile.sensors} / ${!!profile.tools}`, meta: "out of scope for v0", tone: TONE.skip },
    ],
  });
  blocks.push({
    type: "kv", label: "Acceptance and paths", rows: [
      { k: "acceptance_mode", v: rc.acceptance_mode || NA, meta: "studio product path", tone: TONE.ok },
      { k: "state_dir", v: rc.state_dir || NA, meta: "current.json · threads.json · methods.json" },
      { k: "logs_dir", v: rc.logs_dir || NA, meta: "history · candidates · receipts · errors" },
    ],
  });
  blocks.push({ type: "note", kind: "info", body: "In companion mode the substrate may supply evidence when the model cites none, goal reference is optional, and not_responsive is advisory. Measurement mode hardens all three into rejections." });
  return { title: "Runtime and edge profile", sub: "actual values in force for this turn", srcStatic: "conditioned_kernel/edge.py · EdgeProfile", blocks };
}

// ---- -1 ATTRACTOR TIMELINE ----------------------------------------------------

function panelAttractor() {
  const blocks = [];
  const turns = turnsList();
  const flagged = turns.filter((t) => (t.observations || []).some((o) => o.label === "Stale-response attractor" || o.label === "Prior answer carried forward" || o.label === "High recent-context repetition"));

  blocks.push({
    type: "note", kind: "info",
    body: "This panel does not run its own cross-session clustering (that would recompute a business rule client-side against numbers already owned by the pipeline). It lists what each turn's own trace already computed via compute.derive_observations, which flags repetition, staleness, and carried-forward answers per turn. A dedicated session-lineage endpoint exposing compute.cluster_candidates() / compute.stored_answer_carried() across every candidate in the session would settle full attractor grouping — GET /api/session does not carry that yet.",
  });

  if (flagged.length) {
    blocks.push({
      type: "cards", label: "Turns flagged for repetition or carry-forward", note: "each row is this turn's own computed observations, not a new comparison",
      rows: flagged.map((t) => {
        const obs = (t.observations || []).filter((o) => o.label !== "Advisory not enforced");
        return {
          title: `turn ${t.n} · ${t.decision || "?"}`, tone: TONE.warn, meta: t.turn_id,
          body: t.user_input, body2: obs.map((o) => `${o.label}: ${o.detail}`).join("\n\n"),
          bg: "var(--note-bad-bg)", border: "var(--note-bad-border)",
        };
      }),
    });
  } else if (turns.length) {
    blocks.push({ type: "note", kind: "info", body: "No turn in this session's currently-loaded summary carries a repetition, staleness, or carried-forward observation." });
  } else {
    blocks.push({ type: "note", kind: "info", body: "No turns in this session yet." });
  }

  blocks.push({
    type: "kv", label: "Session totals", note: "from /api/session, already computed per turn",
    rows: [
      { k: "turns", v: String(turns.length), meta: "" },
      { k: "accepted", v: String(turns.filter((t) => t.spoken).length), meta: "" },
      { k: "rejected", v: String(turns.filter((t) => !t.spoken).length), meta: "" },
      { k: "flagged for repetition/carry-forward", v: String(flagged.length), meta: "" },
    ],
  });
  blocks.push({ type: "note", kind: "info", body: "This panel does not claim to know why a phrase repeated — whether compilation created the groove, the kernel fell into it, or a repeat penalty was too weak against the context already containing the answer. It shows only what each turn's own trace already recorded." });
  return { title: "Attractor timeline", sub: "session-scale, from each turn's own recorded observations", srcStatic: "GET /api/session · per-turn observations", blocks };
}

// ---- -2 CLAUDE OBSERVER ------------------------------------------------------

function panelObserver() {
  const t = State.trace;
  const summary = currentTurnSummary();
  const blocks = [];
  blocks.push({
    type: "note", kind: "info",
    body: "This pane is scaffolding for building the substrate, not part of it. It never touches pipeline.run_turn, never writes to state/, logs/, or operator_feedback.jsonl. Every request is staged first (POST /api/observer/stage) and shows exactly what it would transmit before anything is sent. Cloud send itself (POST /api/observer/send) is an intentional stub in this build — see the status line after Send.",
  });

  const payloadOn = (kind) => State.obsPayloadKind === kind;
  blocks.push({
    type: "toggles", label: "Payload kind", note: "kept separate per turn_api.py — compact brief vs full debug brief, built server-side",
    rows: [
      { label: "Compact brief", meta: "composition figures, candidate, non-passing checks, evidence audit, source map, persistence — no full packet JSON", on: payloadOn("compact"), onClick: () => setState({ obsPayloadKind: "compact", obsPending: null }) },
      { label: "Full debug brief", meta: "everything, including the full packet and the complete TurnTrace JSON — same text as GET /api/turn/:id/brief", on: payloadOn("full"), onClick: () => setState({ obsPayloadKind: "full", obsPending: null }) },
      { label: "Include prior dialogue bodies", meta: payloadOn("full") ? "always included in the full brief" : "off by default — compact sends byte counts and similarity instead", on: payloadOn("full") ? true : State.obsDialogue, locked: payloadOn("full"), onClick: () => setState({ obsDialogue: !State.obsDialogue, obsPending: null }) },
    ],
  });

  blocks.push({
    type: "ask", label: `Stage a request about turn ${summary ? summary.n : "?"}`, note: "review the gate below, then Send",
    status: (State.obs && State.obs.message) || "",
    statusTone: State.obs && State.obs.ok ? TONE.ok : TONE.warn,
    body: "",
    buttons: Object.keys(OBS_ASKS).map((k) => ({ label: OBS_ASKS[k].label, active: State.obsAsk === k, onClick: () => stageObserverAsk(k) })),
  });

  if (State.obsPending) {
    const pend = State.obsPending;
    const d = pend.disclosure || {};
    blocks.push({
      type: "gate", label: "Ready to send — nothing has left yet", note: "cloud request",
      rows: [
        { k: "destination", v: d.destination || NA, tone: TONE.warn, meta: "cloud, outside this machine" },
        { k: "payload", v: d.payload_kind || NA, tone: "var(--text-body-1)", meta: `${isNil(d.byte_count) ? NA : d.byte_count} bytes total` },
        { k: "current user message", v: d.includes_current_user_message ? "included" : "withheld", tone: "var(--text-body-1)", meta: t ? JSON.stringify(t.user_input) : "" },
        { k: "prior dialogue bodies", v: d.includes_prior_dialogue_bodies ? "included" : "withheld", tone: d.includes_prior_dialogue_bodies ? TONE.warn : TONE.ok, meta: d.includes_prior_dialogue_bodies ? "stored turns sent in full" : "byte counts and similarity figures only" },
        { k: "full packet JSON", v: d.includes_full_packet_json ? "included" : "withheld", tone: d.includes_full_packet_json ? TONE.warn : TONE.ok, meta: d.includes_full_packet_json ? "every field the kernel received" : "composition figures only" },
        { k: "file paths", v: d.includes_file_paths ? "included" : "withheld", tone: "var(--text-dim)", meta: "source mapping is what makes the answer useful" },
        { k: "writes back", v: d.persists_nothing ? "nothing" : "unconfirmed", tone: d.persists_nothing ? TONE.ok : TONE.bad, meta: "state, memory, logs and operator_feedback are untouched" },
      ],
      onSend: () => sendObserverAsk(),
      onCancel: () => setState({ obsPending: null }),
    });
    blocks.push({ type: "code", label: "Staged payload", body: pend.payload || NA, note: `${pend.ask_label || pend.ask} · not sent yet` });
    blocks.push({ type: "code", label: "System prompt", body: pend.system_prompt || NA, note: "verbatim from brief.OBSERVER_SYSTEM_PROMPT" });
  }

  blocks.push({
    type: "kv", label: "Working with Claude Code alongside", rows: [
      { k: "Copy debug brief", v: "the button under the operator notebook", meta: "stays on this machine · markdown with stage paths, byte census, both passes, persistence" },
      { k: "what it is aimed at", v: "paste into Claude Code as the whole context for one turn", meta: "no screenshots, no guessing at values" },
    ],
  });
  blocks.push({
    type: "kv", label: "Feed contract for this dashboard", note: "see README §12 and this build's server.py routing",
    rows: [
      { k: "GET /api/session", v: "runtime config + turn list", meta: "header and conversation column" },
      { k: "POST /api/turn", v: "{ text } → TurnTrace", meta: "calls pipeline.run_turn once" },
      { k: "GET /api/turn/:id/trace", v: "TurnTrace", meta: "the object this whole view is built from" },
      { k: "GET /api/turn/:id/brief", v: "text/markdown", meta: "full debug brief", tone: TONE.ok },
      { k: "GET /api/stream", v: "text/event-stream", meta: "event: stage, event: turn_complete" },
      { k: "POST /api/feedback", v: "{ turn_id, marks[], note }", meta: "appends to operator_feedback.jsonl" },
      { k: "POST /api/observer/stage", v: "{ turn_id, ask, payload_kind, include_prior_dialogue }", meta: "returns the disclosure this gate renders" },
      { k: "POST /api/observer/send", v: "same body", meta: "this build's cloud call is a stub — ok:false always", tone: TONE.warn },
    ],
  });
  return { title: "Claude observer", sub: "build-time debugging · nothing leaves this machine until you press Send", srcStatic: "build-time only · not part of the shipped runtime", blocks };
}

async function stageObserverAsk(kind) {
  if (!State.currentTurnId) return;
  setState({ obsAsk: kind, obsPending: null });
  try {
    const staged = await Api.postObserverStage(State.currentTurnId, kind, State.obsPayloadKind, State.obsDialogue);
    setState({ obsPending: staged, obs: null });
  } catch (e) {
    setState({ ops: `failed to stage observer request: ${e.message}`, opsErr: true });
  }
}

async function sendObserverAsk() {
  const pend = State.obsPending;
  if (!pend || !State.currentTurnId) return;
  setState({ obsPending: null });
  try {
    const res = await Api.postObserverSend(State.currentTurnId, pend.ask, State.obsPayloadKind, State.obsDialogue);
    setState({ obs: res });
  } catch (e) {
    setState({ obs: { ok: false, message: `send failed: ${e.message}` } });
  }
}

// ---- -3 REPLAY TURN --------------------------------------------------------

function panelReplay() {
  const t = State.trace;
  const blocks = [];
  const sectionOn = (key) => (key in State.exp ? State.exp[key] : key !== "recent");

  if (!State.replayResult && !State.replayLoading) {
    fetchReplay();
  }

  blocks.push({ type: "note", kind: "info", body: "Toggling a section re-POSTs /api/replay, which rebuilds the model input by the same rules as compile, edge.enforce_packet_budget and build_model_input, and re-runs the checks whose inputs actually change. It cannot produce a new answer — that needs a live call to pipeline.run_turn with the modified input. Model, seed, temperature and your message are held fixed and are not toggleable, because varying them would answer a different question." });

  if (State.replayLoading && !State.replayResult) {
    blocks.push({ type: "note", kind: "info", body: "Requesting POST /api/replay…" });
    return { title: "Replay this turn", sub: "build-time inspection · which sections the kernel would see", srcStatic: "POST /api/replay", blocks };
  }
  if (!State.replayResult) {
    blocks.push({ type: "note", kind: "warn", body: "No replay result yet — POST /api/replay has not returned successfully for this turn." });
    return { title: "Replay this turn", sub: "build-time inspection · which sections the kernel would see", srcStatic: "POST /api/replay", blocks };
  }

  const r = State.replayResult;
  const hf = r.held_fixed || {};
  blocks.push({
    type: "toggles", label: "Held fixed", note: "not adjustable — this is a context experiment, not a model experiment",
    rows: [
      { label: "Same user input", meta: JSON.stringify(hf.user_input || ""), on: true, locked: true },
      { label: "Same model settings", meta: `${hf.model || NA} · temperature ${hf.temperature} · num_ctx ${hf.num_ctx} · think=${hf.think}`, on: true, locked: true },
      { label: "Same seed", meta: String(hf.seed), on: true, locked: true },
    ],
  });
  blocks.push({
    type: "toggles", label: "Model input sections", note: "uncheck to withhold from the kernel on the next replay request",
    rows: (r.sections || []).map((s) => ({
      label: s.label, meta: `${s.note} · ${s.on ? "sending" : "withheld"}`, on: s.on,
      onClick: () => { State.exp = { ...State.exp, [s.key]: !sectionOn(s.key) }; fetchReplay(); },
    })),
  });
  blocks.push({ type: "diff", label: "Model input as recorded → as configured", note: "computed by replay.replay_diff, both sides", leftLabel: "as recorded", rightLabel: "as configured", rows: (r.diff || []).map((d) => ({ k: d.field, before: d.before, after: d.after, rightTone: d.withheld ? TONE.bad : "var(--text-dim)", strike: d.withheld ? true : false })) });
  blocks.push({ type: "kv", label: "Checks whose input changed", note: "re-run by replay.replay_effects against the modified packet, not asserted", rows: (r.checks || []).map((c) => ({ k: c.check, v: `${c.before} → ${c.after}`, meta: c.source })) });
  blocks.push({ type: "note", kind: sectionOn("recent") ? "info" : "warn", body: sectionOn("recent") ? "Uncheck Recent dialogue to see what the turn looks like with memory withheld — the comparison that separates a memory attractor from a compilation attractor." : "With recent_turns emptied, stale_response_repeat cannot fire (validate.prior_accepted_answer returns an empty string). If the answer still looks shaped like the project, memory did not cause it — compilation did." });
  blocks.push({ type: "code", label: "Request body as configured", body: JSON.stringify((r.model_input_as_configured || {}).payload || r.model_input_as_configured || {}, null, 2), note: "ready to POST to Ollama, as replay.build_replay_model_input built it" });
  blocks.push({
    type: "kv", label: "To run it for real", rows: [
      { k: "endpoint", v: "POST /api/replay", meta: "{ turn_id, sections: {…} } → this response", tone: TONE.ok },
      { k: "what must not change", v: "model, seed, temperature, num_ctx, keep_alive", meta: "otherwise the comparison is meaningless" },
      { k: "what must not persist", v: String(r.persists === false ? "nothing" : "⚠ persists=" + r.persists), meta: "a replay is an inspection, not a turn", tone: r.persists === false ? TONE.ok : TONE.bad },
    ],
  });
  return { title: "Replay this turn", sub: "build-time inspection · which sections the kernel would see", srcStatic: "observatory/replay.py · run_replay", blocks };
}

async function fetchReplay() {
  if (!State.currentTurnId) return;
  const sections = {};
  REPLAY_SECTION_DEFAULT_ORDER.forEach((k) => { sections[k] = k in State.exp ? State.exp[k] : k !== "recent"; });
  setState({ replayLoading: true });
  try {
    const result = await Api.postReplay(State.currentTurnId, sections);
    setState({ replayResult: result, replayLoading: false });
  } catch (e) {
    setState({ replayLoading: false, ops: `replay failed: ${e.message}`, opsErr: true });
  }
}

// ============================================================= notebook ==

function renderNotebook() {
  const el = document.getElementById("notebook");
  const t = State.trace;
  const summary = currentTurnSummary();
  if (!t || !summary) { clear(el); return; }

  const turnKey = summary.turn_id;
  const marksRow = h("div", { class: "pills-row" }, MARKS.map(([key, label]) => {
    const on = !!State.marks[`${turnKey}:${key}`];
    const pill = h("button", { class: "pill-mark" + (on ? " active" : ""), type: "button" }, label);
    pill.onclick = () => toggleMark(turnKey, key);
    return pill;
  }));

  const textarea = h("textarea", { class: "notebook-textarea", rows: "2", placeholder: "Short note on this turn…" });
  textarea.value = State.notes[turnKey] || "";
  textarea.oninput = (e) => { State.notes[turnKey] = e.target.value; };
  textarea.onblur = () => saveFeedback(turnKey);

  const exportBtn = h("button", { class: "btn-export", type: "button" }, "Export turn trace (JSON)");
  exportBtn.onclick = () => exportTrace();
  const copyTraceBtn = h("button", { class: "btn-copy-trace", type: "button" }, "Copy full trace");
  copyTraceBtn.onclick = async () => {
    const res = await copyToClipboard(JSON.stringify(t, null, 2));
    setState({ ops: res.ok ? `copied ${res.bytes} bytes to clipboard` : "clipboard unavailable", opsErr: !res.ok });
  };
  const copyBriefBtn = h("button", { class: "btn-copy-brief", type: "button" }, "Copy debug brief for Claude Code");
  copyBriefBtn.onclick = () => copyBrief();

  mount(el, [
    h("div", { class: "notebook-label-row" }, [
      h("span", { class: "block-label" }, "Operator notebook"),
      h("span", { class: "block-note" }, `turn ${summary.n} · logs/operator_feedback.jsonl`),
    ]),
    marksRow,
    textarea,
    h("div", { class: "notebook-actions" }, [
      exportBtn, copyTraceBtn, copyBriefBtn, h("span", { class: "spacer" }),
      h("span", { class: "ops-status mono" + (State.opsErr ? " err" : "") }, State.ops),
    ]),
    h("p", { class: "footnote-note" }, "Writes to logs/operator_feedback.jsonl · observation only — no validator, packet, or weight is changed by these marks"),
  ]);
}

async function toggleMark(turnId, key) {
  const k = `${turnId}:${key}`;
  State.marks[k] = !State.marks[k];
  render();
  await saveFeedback(turnId);
}

async function saveFeedback(turnId) {
  const activeMarks = MARKS.map(([key]) => key).filter((key) => State.marks[`${turnId}:${key}`]);
  try {
    await Api.postFeedback(turnId, activeMarks, State.notes[turnId] || "");
    setState({ ops: "saved to logs/operator_feedback.jsonl", opsErr: false });
  } catch (e) {
    setState({ ops: `feedback not saved: ${e.message}`, opsErr: true });
  }
}

function exportTrace() {
  try {
    const t = State.trace;
    const summary = currentTurnSummary();
    const blob = new Blob([JSON.stringify(t, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `turn_${summary ? summary.n : t.turn_id}_${t.session_id}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    setState({ ops: `exported ${a.download}`, opsErr: false });
  } catch (e) {
    setState({ ops: `export failed: ${e.message}`, opsErr: true });
  }
}

async function copyBrief() {
  if (!State.currentTurnId) return;
  setState({ ops: "fetching debug brief…", opsErr: false });
  try {
    const brief = State.brief != null ? State.brief : await Api.getBrief(State.currentTurnId);
    const res = await copyToClipboard(brief);
    setState({ brief, ops: res.ok ? `copied ${res.bytes} bytes to clipboard` : "clipboard unavailable", opsErr: !res.ok });
  } catch (e) {
    setState({ ops: `failed to fetch debug brief: ${e.message}`, opsErr: true });
  }
}

// ================================================================ send ===

async function doSend() {
  const text = State.draft.trim();
  if (!text || State.sending) return;
  setState({ sending: true, draft: "", sendBad: false, sendNote: "Sending to pipeline.run_turn…", play: 1 });
  openLiveStream();
  try {
    const trace = await Api.postTurn(text);
    State.traceCache.set(trace.turn_id, trace);
    closeLiveStream();
    await refreshSession();
    if (isFlowTurn(trace, null)) {
      setState({
        sending: false, play: -1, stage: null, flowPanel: null, currentTurnId: trace.turn_id, trace,
        sendNote: `Turn ${trace.turn_id} complete — reply_status=${trace.reply_status}.`,
        sendBad: !(trace.reply_status === "completed" || trace.reply_status === "dry_run"),
      });
    } else {
      setState({
        sending: false, play: -1, stage: null, currentTurnId: trace.turn_id, trace,
        sendNote: `Turn ${trace.turn_id} complete — ${trace.final_decision ? trace.final_decision.label : trace.final_decision}.`,
        sendBad: trace.final_decision && trace.final_decision.decision !== "accept",
      });
    }
  } catch (e) {
    closeLiveStream();
    setState({ sending: false, play: -1, sendBad: true, sendNote: `Send failed: ${e.message}` });
  }
}

function openLiveStream() {
  if (typeof EventSource === "undefined") return;
  try {
    const es = new EventSource("/api/stream");
    // server.py publishes real `event: stage` / `event: turn_complete`
    // named events (Dashboard._broadcast_turn), back-to-back right after
    // run_traced_turn finishes — not a default unnamed `message` event, and
    // not genuinely concurrent with the in-flight POST (the module's own
    // docstring says so). Every index/status here is real; this file only
    // paces their reveal client-side so the rail is not a single instant
    // jump, exactly the presentational pacing the ▶ replay walkthrough
    // already does over already-known statuses.
    //
    // For a Flow-mode session, `_broadcast_flow_turn` publishes
    // `field_before` / `traveled` / `field_after` (then `turn_complete`)
    // instead — the flow-shaped turn this spec describes. This file reuses
    // the same numeric `State.play` pacing mechanism for them (mapped to
    // 1/2/3) rather than building a second reveal pipeline.
    const revealQueue = [];
    let draining = false;
    const drain = () => {
      if (draining) return;
      draining = true;
      const step = () => {
        if (!revealQueue.length) { draining = false; return; }
        setState({ play: revealQueue.shift() });
        setTimeout(step, 120);
      };
      step();
    };
    es.addEventListener("stage", (ev) => {
      try {
        const data = JSON.parse(ev.data);
        const stage = data && data.stage;
        if (stage && typeof stage.index === "number") { revealQueue.push(stage.index); drain(); }
      } catch (e) { /* ignore malformed event */ }
    });
    es.addEventListener("turn_complete", () => { /* POST /api/turn resolves independently with the full trace */ });
    const FLOW_EVENT_ORDER = { field_before: 1, traveled: 2, field_after: 3 };
    Object.keys(FLOW_EVENT_ORDER).forEach((name) => {
      es.addEventListener(name, () => { revealQueue.push(FLOW_EVENT_ORDER[name]); drain(); });
    });
    es.onerror = () => { /* fall back silently to waiting on the POST response */ };
    State.sse = es;
  } catch (e) { /* SSE unavailable; POST /api/turn alone still completes the turn */ }
}
function closeLiveStream() {
  if (State.sse) { try { State.sse.close(); } catch (e) {} State.sse = null; }
}

async function refreshSession() {
  try {
    const session = await Api.getSession();
    setState({ session, connected: true });
  } catch (e) {
    setState({ connected: false });
  }
}

// ------------------------------------------------------- replay walkthrough

let walkTimer = null;
function doReplayWalkthrough() {
  if (walkTimer) { clearInterval(walkTimer); walkTimer = null; }
  if (!State.trace) return;
  let n = 1;
  setState({ play: 1, stage: 1, ops: "", opsErr: false });
  walkTimer = setInterval(() => {
    n += 1;
    if (n > 12) { clearInterval(walkTimer); walkTimer = null; setState({ play: -1, stage: null }); return; }
    setState({ play: n, stage: n });
  }, 260);
}

// ================================================================= init ==

async function init() {
  try {
    const session = await Api.getSession();
    setState({ session, connected: true });
    const turns = turnsList();
    if (turns.length) {
      const last = turns[turns.length - 1];
      await selectTurn(last.turn_id);
    }
  } catch (e) {
    setState({
      session: { session_id: null, connection: null, observer_enabled: false, runtime_config: null, config: { layout: "rail", defaultStage: "Final decision", showObservations: true }, turns: [] },
      connected: false,
      ops: `could not reach /api/session: ${e.message}`,
      opsErr: true,
    });
  }
}

document.addEventListener("DOMContentLoaded", init);
