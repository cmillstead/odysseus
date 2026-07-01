# Odysseus — Implementation Spec (from BB Gap Analysis)

**Source:** `AI/output/bb-gap-odysseus.md`
**Target repo:** `/Users/cevin/src/odysseus` (`cmillstead/odysseus`, hermes-enhanced fork)
**Date:** 2026-06-30
**Status:** spec — not yet routed to `/coding-team`
**Grounding:** every insertion point below was read in current source (line refs are live as of this date). New code is illustrative (marked *proposed*), not tested.

> **How to use this doc.** Each workstream (WS-n) is a self-contained `/coding-team` brief: goal, files, change, schema/migration, tests, acceptance, flag, risk. Phases are ordered by dependency + value. Ship phase-by-phase; do not batch across phases (each phase has a verification gate). Suggested model routing: **sonnet** for implementation WSs, **opus** for the Phase-1 design reviews (they touch the learning substrate).

> **House rules that bind every WS:** (1) tests use **real** implementations — temp SQLite, real temp dirs, real in-process FastAPI/`httpx` — never mocks. (2) Every new capability sits behind a **setting/flag**, default chosen per-WS. (3) No destructive schema edits — memory changes are **additive** and back-compatible with existing `memory.json`. (4) Nothing ships known-broken; a smaller correct slice beats a larger flaky one.

---

## Phasing & dependency graph

```
Phase 0  Foundations (schema + flags)         ──┐
                                                 ├─► Phase 1 depends on 0
Phase 1  Self-learning safety  (WS-1..WS-5)   ◄─┘
Phase 2  Security tail          (WS-6..WS-9)   (independent of 1; can parallelize)
Phase 3  Context output leverage (WS-10..WS-13)(independent; can parallelize)
Phase 4  Med/low tail           (WS-14..WS-20) (after 1–3)
```

**Critical path for the differentiator (Hermes safety):** WS-0 → WS-2 (origin) → WS-3 (supersession) → WS-1 (verifier) → WS-4 (compaction) → WS-5 (plan-pin). WS-2 and WS-3 share the `memory.py` write path — build them as one coding-team run.

---

# Phase 0 — Foundations

## WS-0 · Memory entry schema v2 (additive) + settings scaffold

**Goal:** add the fields Phase 1 needs, without breaking the flat `memory.json` store or existing readers.

**Files:** `src/memory.py` (`_validate_entries:150`, `save:196`, `add_entry:215`), plus a one-time in-place migration on load.

**Current entry shape** (grounded, `memory.py:220-227`):
```python
{"id", "text", "timestamp", "source", "category", "uses", "owner"?}
```

**New additive fields** (all optional, defaulted so old entries stay valid):
| Field | Type | Default | Purpose | WS |
|-------|------|---------|---------|----|
| `origin` | str enum | `"unknown"` | immutable authority label: `user_direct \| tool_output \| fetched_page \| imported \| learning_review \| unknown` | WS-2 |
| `valid_from` | int (epoch) | = `timestamp` | event-time validity start | WS-3 |
| `valid_to` | int \| null | `null` | set when retired | WS-3 |
| `retired` | bool | `false` | supersession tombstone (never hard-deleted) | WS-3 |
| `supersedes` | str \| null | `null` | id of the entry this one retired | WS-3 |
| `sro` | obj \| null | `null` | `{subject, relation, object}` extraction key | WS-3 |
| `complete` | bool \| null | `null` | completeness bit for consolidated/compacted entries | WS-4 |

**Change (proposed):** extend `_validate_entries` to backfill `origin="unknown"`, `valid_from=timestamp`, `retired=false` when absent; make `add_entry(text, source, category, owner, *, origin="unknown", valid_from=None, sro=None)`. Keep `source` (display/provenance string) — `origin` is the *non-malleable authority* label, distinct from the free-text `source`.

**Migration:** on first `load_all()` after upgrade, if any entry lacks `origin`, backfill + `save()` once. Idempotent (guard on a `_schema_v` marker file or a sentinel entry). Existing `owner`, `uses`, `session_id`, `metadata` untouched.

**Tests** (real temp `memory.json`):
- old-format entry loads → gets `origin="unknown"`, `retired=False`, `valid_from==timestamp`.
- round-trip save/load preserves all v2 fields.
- migration runs once (second load does not re-write).

**Acceptance:** existing memory endpoints/tests green; new fields present on read; no field renamed or removed.
**Flag:** none (schema is always-on but inert until WS-2/3 use it).
**Risk:** low. Additive only. The only trap is `save()` (`:196`) re-defaulting `source="user"` — leave that; add the new backfills alongside.

---

# Phase 1 — Self-Learning Safety (the differentiator)

## WS-1 · Turn the verifier ON + measure its discrimination

**BB:** `agents/the-harness-loop-who-verifies-the-verifier`
**Goal:** the loop's independent completion gate must (a) actually run on effectful turns, and (b) have its accuracy *measured*, not trusted.

**Files:** `src/agent_loop.py` — verifier subagent `_run_verifier_subagent:1880`, gate `:2979-3012`; new verdict log via `services/runs/registry.py` (or a JSONL sidecar under the data dir).

**Current state (grounded):** gate at `:2986` is `get_setting("agent_verifier_subagent", False)` — default **OFF**. The subagent (`:1880`) returns a list of failure reasons and swallows errors to empty (can't block a valid completion). No verdict is persisted.

**Change:**
1. **Default-on for strong models only.** Do NOT globally flip the default (the `:2982-2985` comment is right — weak local models false-reject from the action-snapshot). Instead gate on a capability signal:
   ```python
   # proposed, replacing the bare get_setting at :2986
   _verifier_on = get_setting("agent_verifier_subagent", None)
   if _verifier_on is None:  # unset → auto: on for strong/remote models, off for small local
       _verifier_on = _model_is_strong(model, endpoint_url)  # new helper: reuse model_context tier hints
   ```
   Keep the explicit setting as an override (True/False wins over auto).
2. **Persist every verdict** for discrimination measurement. At the gate, after `_run_verifier_subagent` returns, append one record:
   ```python
   {"ts", "session_id", "round": round_num, "model",
    "verdict": "fail" if _vfail else "pass",
    "reasons": _vfail, "instruction_hash": sha1(_verifier_instruction)}
   ```
   Write to `data/verifier_log.jsonl` (atomic append) keyed so a later ground-truth signal can join on `session_id`.
3. **Ground-truth join (v1, offline).** A scheduled task (`task_scheduler.py`, sibling of `audit_skills`) correlates each `pass` verdict against a downstream negative signal within N turns: a user-correction/frustration phrase (reuse `teacher_escalation._REPLY_GIVE_UP_PATTERNS`) or a re-run of the same task. Emit a rolling `verifier_agreement_rate` to the diagnostics surface. **v1 only measures + surfaces; it does not auto-weight.**
4. **Invariant check (cheap add).** Add checklist item 5 to the verifier prompt (`:1899-1904`): *"5. The change touched ONLY what was requested — no protected files/paths modified, no unrelated edits."* This catches correct-by-outcome-but-wrong-scope completions.

**Tests** (real, in-process):
- `_model_is_strong` returns True for a configured remote/strong model id, False for a small local tag.
- verdict log: a forced `_vfail` path writes one well-formed JSONL line; append is atomic under two concurrent turns (temp dir).
- prompt includes the scope-invariant line.
- agreement-rate task: seed a `pass` verdict + a following frustration phrase → correlation counted as a disagreement.

**Acceptance:** on a strong model, an effectful turn runs the verifier without the setting being manually enabled; every verdict produces exactly one log line; diagnostics shows a non-null agreement rate after the scheduled task runs.
**Flag:** `agent_verifier_subagent` becomes tri-state (`None`=auto / `True` / `False`); default `None`.
**Risk:** med. Flipping default-on can add a round on effectful turns — bounded by `_VERIFIER_MAX_ROUNDS=2` (`:1859`) and the `_effectful_used=False` re-arm (`:3011`). The auto-gate keeps weak models unaffected. **v2 (out of this WS):** weight verifier blocking authority by measured agreement.

## WS-2 · Origin-bound memory authority

**BB:** `security/memory-poisoning-origin-bound-authority`
**Goal:** bind each memory's authority to its origin at write time, non-malleably, so injected content can't be laundered into a trusted instruction later.

**Files:** `src/memory.py` (`add_entry:215`), all call sites that create memories, and the injection path (`chat_processor.py` retrieval-into-context).

**Change:**
1. **Set `origin` at every write, immutably.** Thread an `origin` arg through `add_entry` (WS-0 added the param). Set it at each call site by *provenance of the text*, not caller convenience:
   - direct user "remember X" → `user_direct`
   - `learning_review` proposals (`learning_review.py:552`) → `learning_review`
   - anything distilled from tool output / fetched pages → `tool_output` / `fetched_page`
2. **Never rewrite `origin`.** In `_validate_entries`/`save`, if an entry already has `origin`, do not overwrite it (summarization/consolidation must preserve it). Add a test asserting `audit_memories` merge (WS-3) keeps the *most authoritative* origin of the merged set.
3. **Read-side fence for non-user origin.** At the injection site, wrap recalled memories whose `origin != user_direct` in `untrusted_context_message(...)` (the same helper already used for tool output at `agent_loop.py:1776`), with `source=origin`. `user_direct` memories inject as trusted.
4. **Elevation gate.** Any pathway that would treat a memory as an *instruction* (not reference data) must require `origin == user_direct` OR corroboration (≥2 independent entries agreeing). For v1, the read-side fence (#3) is the enforcement; the elevation gate is documented as the invariant WS-16 (preview→commit) also relies on.

**Tests** (real temp store + real prompt assembly):
- entry created from a fetched-page distillation gets `origin="fetched_page"` and is wrapped as untrusted at injection.
- `user_direct` memory injects unwrapped.
- `origin` survives an `edit` and a consolidation merge.

**Acceptance:** grep confirms no call site sets `origin` from a mutable request field; injection of a `tool_output` memory is fenced; existing memory recall behavior for `user_direct` unchanged.
**Flag:** `memory_origin_fence` (default **on** — this is a safety fix).
**Risk:** med. Mislabeling origin is the failure mode → default any uncertain path to the *less* authoritative label (`tool_output`), never `user_direct`.

## WS-3 · Temporal validity + `(S,R,O)` supersession (retire-not-delete)

**BB:** `memory/memstrata-…`, `memory/graphiti-…`, `memory/convmemory-…` (single-store lightweight adoption — odysseus is flat JSON, not a graph)
**Goal:** newer facts retire older conflicting ones instead of overwriting/deleting; recall surfaces only currently-valid rows; a non-destructive read layer annotates superseded hits.

**Files:** `src/memory.py` (write path, `load`/recall filters), `services/memory/learning_review.py` (`_apply_memory:564` edit, `:576` delete), `services/memory/memory_extractor.py` (`audit_memories:487`).

**Change:**
1. **`(S,R,O)` extraction at write.** In the learning-review/extractor write path (which already runs an LLM), extract a normalized `sro` key for fact-category entries. Store on the entry (WS-0 field).
2. **Supersession on conflict.** When adding a fact whose `(subject,relation)` matches an active entry with a *different* `object`:
   - stamp the old entry `retired=true, valid_to=now`
   - set the new entry `supersedes=<old id>, valid_from=now`
   - **do not delete** the old row.
3. **Rewrite the destructive edit** (`learning_review.py:568`): instead of `entry["text"] = payload["text"]`, retire the old entry and add a new one carrying `supersedes`. Same for the destructive merge in `audit_memories` (currently drops originals) — merge → retire losers, keep a canonical winner with `supersedes` list.
4. **Recall filter.** `MemoryManager.load()`/`get_relevant_memories`/vector recall return `retired != true` by default. Add an opt-in `include_retired` for audit/history views.
5. **Read-path validity annotation (convmemory).** A non-destructive stage tags each recalled hit `possibly_superseded` + surfaces `valid_to`, keeping rank order identical. Demotion is opt-in (for current-state queries). **Two-signal rule:** only mark superseded when the deterministic `(S,R)` key matches AND an LLM/NLI agreement fires — guards against similarity-only false demotes.

**Migration:** existing entries get `retired=false, valid_from=timestamp` (WS-0). No `sro` backfill required (computed lazily on next touch).

**Tests** (real temp store):
- add "user lives in Portland" then "user lives in Seattle" (same S,R) → first `retired=true` with `valid_to`, second active with `supersedes`; recall returns only Seattle.
- `include_retired=True` returns both.
- `audit_memories` merge retires losers, never returns fewer *total* rows (tombstones retained); the existing over-deletion safety net (`memory_extractor.py:620-625`) still holds.
- read-path: superseded hit is annotated, rank order unchanged; demotion only when both signals agree.

**Acceptance:** no code path hard-overwrites `text` or drops a fact row on conflict; recall excludes retired by default; a contradiction test converges to the newest fact.
**Flag:** `memory_supersession` (default **on**).
**Risk:** med-high. This is the deepest change to the learning substrate. Mitigations: retire-not-delete means every mistake is recoverable (nothing lost); two-signal demote avoids false retirement; ship behind the flag and dogfood on your own vault-adjacent memory first.

## WS-4 · Source-first compaction + completeness bit

**BB:** `memory/reclaim-brittle-memory-source-first-compaction`
**Goal:** compaction preserves recomputable source over re-derivable conclusions; consolidated entries carry a `complete?` bit; recall treats incomplete-but-confident as a reason to abstain/re-fetch.

**Files:** `src/context_compactor.py` (`maybe_compact:312`, `SELF_SUMMARY_SYSTEM_PROMPT:44`), `services/memory/memory_extractor.py` (`audit_memories`).

**Change:**
1. **Compaction prompt** (`SELF_SUMMARY_SYSTEM_PROMPT`): instruct the summarizer to preserve answer-determining source (file paths, commands, exact values, IDs, URLs) verbatim and drop *derived conclusions* that can be recomputed from that source. It already asks for "Pending/Next Steps"; add explicit "Preserve exact source tokens; do not paraphrase file paths, commands, numbers."
2. **Completeness bit.** When `maybe_compact` (`:312`) summarizes the older half, stamp the resulting summary_msg (`:397`) with `complete = (older_fit_within_budget)` — i.e. false if the older half was itself truncated at the `[:2000]` per-message cap (`:354`). Carry `complete` on consolidated *memory* entries too (WS-0 field).
3. **Recall/injection use.** Treat `complete == false` context as low-authority: the injection note says "this summary may be incomplete — re-read source before asserting."

**Tests:**
- a compaction where an older message exceeds the 2000-char cap → summary_msg `complete=false`.
- summary prompt output retains an exact file path / command token present in the input (assert substring survives).

**Acceptance:** compaction never silently claims completeness; source tokens survive summarization in the test fixture.
**Flag:** none (prompt + metadata change; low blast radius). Keep the graceful-degrade path at `:390-395` intact.
**Risk:** low-med. Prompt changes can regress summary quality on weak models — keep the change minimal and validate on a small-model fixture.

## WS-5 · Pin the active plan through compaction

**BB:** `context/plans-dont-persist-load-bearing-context`
**Goal:** the approved plan / acceptance-criteria / critic-contract survives compaction verbatim, not folded into the lossy summary.

**Files:** `src/context_compactor.py` (`maybe_compact:312`, `_protected` handling at `:231-244`).

**Current state (grounded):** `_protected` messages are honored by `trim_for_context` (`:236`) but `maybe_compact` (`:312`) splits older/recent purely by index (`:348`) and summarizes the older half **without** checking `_protected`. The `build_active_plan_note` (`agent_loop.py:1976`) plan note is a system message re-sent each turn — but if it lands in the "older half" it gets summarized away between resends.

**Change:** in `maybe_compact`, exclude `_protected` messages (and any message whose content starts with `## ACTIVE PLAN`) from the `older` summarize set — carry them verbatim into `compacted` alongside `recent`. Concretely, partition `convo_msgs` into `protected` / `older` / `recent`; summarize only `older`; result = `system_msgs + protected + [summary_msg] + recent`.

**Tests:**
- a `_protected`-flagged plan message in the older half survives compaction verbatim (present in output, not in the summarized text).
- non-protected older messages are still summarized.

**Acceptance:** an approved-plan turn that triggers compaction still shows the full plan in the post-compaction message list.
**Flag:** none.
**Risk:** low. Pure message-list partition. Watch the `_update_session_history` offset math (`:404-409`) — protected messages kept out of the summarized span change `split_point`; adjust the offset accordingly and cover with a test.

---

# Phase 2 — Security Tail (parallelizable with Phase 1)

## WS-6 · Sandbox the shell (highest absolute security gap)

**BB:** `security/nvidia-agent-security-mandatory-controls`, `security/agent-sandboxing-comparison-2026`
**Goal:** bash/python subprocesses run under OS-level confinement — file tools are already path-confined, but the shell spawns on the host (RCE/exfil surface).

**Files:** `src/agent_tools/subprocess_tools.py` (`BashTool` spawn `:108` `create_subprocess_shell`, `PythonTool`), `services/shell/service.py`.

**Change:** wrap the spawn in a platform sandbox profile bounding: (a) writes to `agent_cwd()`, (b) network egress to an allowlist (default deny), (c) unconditional deny of `~/.ssh`, `~/.aws`, `~/.config` and odysseus's own config/secret files.
- **macOS:** `sandbox-exec` (Seatbelt) profile.
- **Linux:** `bwrap` (Bubblewrap) with bind-mounts; fall back to `firejail`.
- **Docker deployments:** document that the container is the boundary; still apply write-confinement.
- **No sandbox binary available:** fail *safe* — refuse shell execution with a clear message, or run only when an explicit `shell_unsandboxed_ok` admin override is set (default off).

**Tests** (real, skip-guarded by platform):
- inside sandbox: write to `agent_cwd()` succeeds; write to `$HOME/.ssh/x` is denied; read of a secret file is denied; egress to a non-allowlisted host fails.
- no-sandbox path: execution refused unless override set.

**Acceptance:** a command attempting `cat ~/.aws/credentials` or `curl evil.tld` from the agent shell is blocked on macOS and Linux; workspace writes still work.
**Flag:** `shell_sandbox` (default **on** where a profile is available); `shell_unsandboxed_ok` admin override (default off).
**Risk:** med-high — sandbox profiles break legitimate commands (compilers, package managers). Ship with a permissive-but-safe default profile + an allowlist setting; dogfood heavily. This is the single most valuable security WS.

## WS-7 · Close the MCP untrusted-wrapper bypass

**BB:** `mcp/mcp-security-vulnerability-taxonomy`
**Goal:** MCP tool results and descriptions are attacker-controlled context; the native function-calling path must fence them like the code-block path already does.

**Files:** `src/agent_loop.py` native fn-call result branch (`~:1756-1762`; code-block path wraps at `:1776`), `src/mcp_manager.py` (description injection `:562,664`).

**Change:**
1. Wrap MCP-sourced tool output in `untrusted_context_message(source="mcp:<server_id>")` in the **native** branch, matching `:1776`. (This is the exact hole `THREAT_MODEL.md` says to close but the native path skips.)
2. Sanitize/length-bound MCP tool **descriptions** the way params already are (`mcp_manager.py:44-92`) before they enter the schema/prompt — not just the 120-char truncation at `:664`.

**Tests:** a mock-free local stub MCP server (real stdio subprocess) returning an injection string → result reaches the model wrapped as untrusted; a description containing instruction-like text is neutralized.
**Acceptance:** MCP results in native mode carry the untrusted wrapper; description sanitization applied.
**Flag:** none (safety fix, default on).
**Risk:** low. Reuses an existing helper on a second code path.

## WS-8 · MCP result provenance

**BB:** `mcp/provenanceguard-source-aware-factuality`
**Goal:** each MCP result carries `{server_id, tool_name}` so downstream attribution/audit is possible.
**Files:** `src/mcp_manager.py` (`_do_call:476` flattens + drops identity parsed at `:443-444`), `src/agent_loop.py` result assembly (`~:1756-1776`).
**Change:** thread the already-known `server_id`/`tool_name` into each result dict and carry as typed fields via `untrusted_context_message`'s `source`/metadata channel (WS-7 already routes MCP results through it). Preserve per-source attribution instead of a single concatenated blob.
**Tests:** two MCP servers called in one turn → each result labeled with its own `server_id`.
**Acceptance:** result messages are per-source attributable; no single merged blob.
**Flag:** none.
**Risk:** low. Identity is already computed; this stops discarding it. Build with WS-7 (same code region).

## WS-9 · MCP fail-closed allowlist + manifest pin

**BB:** `security/mcpfw-mcp-kill-chain-runtime-firewall`
**Goal:** per-task tool allowlist (fail closed) + pin the tool set observed at connect to detect mid-session rug-pull.
**Files:** `src/mcp_manager.py` (connect/refresh), `src/tool_security.py` (denylist `:166`).
**Change:** (1) record the tool manifest at `connect_server` time; on refresh, reject/flag any *added* tool not in the pinned set. (2) Add an opt-in per-session `allowed_mcp_tools` whitelist; when set, unknown MCP tools are blocked (fail closed). Keep the existing denylist as the floor.
**Tests:** a stub server that adds `execute_shell` on a second `tools/list` → flagged/blocked; whitelist mode blocks an un-listed tool.
**Acceptance:** mid-session manifest mutation is detected; whitelist mode fails closed.
**Flag:** `mcp_manifest_pin` (default on), `mcp_tool_allowlist` (opt-in, default empty=off).
**Risk:** low-med. Legit servers that legitimately update tools need a re-pin path (surface a "tools changed — approve?" prompt).

---

# Phase 3 — Context Output Leverage (parallelizable)

> odysseus nails the **input** side (dynamic tool retrieval, progressive skill disclosure). Every gap here is **output**-side. Answers the ROADMAP's #1 "context bloat" item; near-zero-infra.

## WS-10 · CCR store — reversible tool-output compression

**BB:** `context/headroom-tool-output-compression-proxy`
**Goal:** replace lossy char-truncation with compress-cache-retrieve.
**Files:** `src/tool_execution.py` (result handling), `src/tool_utils.py` (`_truncate:29`), new store (reuse SQLite via `chroma_client`/`rag`).
**Change:** when a tool result exceeds `MAX_OUTPUT_CHARS` (`constants.py:71`, 10k), store the full payload keyed by content hash, return a dense summary + a `<<ref:hash>>` marker, and add a builtin `retrieve_output(hash, [regex])` tool. Truncation becomes reversible.
**Tests:** a 50k-char tool output → context gets summary + ref; `retrieve_output` returns the full payload; regex slice works.
**Acceptance:** large outputs no longer lost to truncation; agent can retrieve on demand.
**Flag:** `tool_output_ccr` (default on above a size threshold).
**Risk:** low-med. Store growth → add TTL/size cap eviction. **Anchors WS-11.**

## WS-11 · Virtual-filesystem compaction (reversible tiering)

**BB:** `context/context-compaction-virtual-filesystem`
**Goal:** the older half that `maybe_compact` currently drops becomes a retrievable virtual file.
**Files:** `src/context_compactor.py` (`maybe_compact:312`).
**Change:** after summarizing the older half (`:349`), persist the raw slice into the WS-10 CCR store and add a line to `summary_msg` telling the agent it can retrieve it. Optionally inject a per-turn token-accounting system message (used/available).
**Depends on:** WS-10.
**Tests:** post-compaction, the raw older slice is retrievable by ref; summary references it.
**Acceptance:** compaction is reversible; no silent loss.
**Flag:** `compaction_virtual_fs` (default on when CCR available).
**Risk:** low.

## WS-12 · Last-N tool-pair pruning + rolling summary

**BB:** `context/pruning-vs-summarization-enterprise-mcp`
**Goal:** keep only the last ~N assistant-tool_call/tool-response pairs verbatim; replace older pairs with a short rolling summary. Stale verbose tool state actively misleads small-context models.
**Files:** `src/context_compactor.py` (new pre-inference pass) / `src/agent_loop.py` message assembly.
**Change:** a pure message-list transform run before inference: retain last ~5 tool pairs, fold older ones into a rolling summary. Complements the 85% half-summary; targets the 4k/8k/16k models the ROADMAP calls out.
**Tests:** a session with 12 tool pairs → only last 5 verbatim + one rolling summary; assistant text messages untouched.
**Acceptance:** tool-pair count in-context bounded; no infra needed.
**Flag:** `context_last_n_tool_pairs` (default N=5, off for large-context models).
**Risk:** low. Zero-infrastructure.

## WS-13 · Per-command output filters (RTK)

**BB:** `context/rtk-proxy-context-filter`
**Goal:** command-specific compression for the noisiest bash uses.
**Files:** `src/tool_execution.py` bash/python result handling.
**Change:** lightweight post-filters for test runners / `git status|log` / build output: one-line stats summary on success, keep error blocks on failure. Applied inside odysseus's own bash tool (not an external proxy). Stacks with WS-12.
**Tests:** a passing pytest run → collapsed to a stats line; a failing run → error block retained.
**Acceptance:** high-noise commands shrink by meaning, not bytes.
**Flag:** `bash_output_filters` (default on).
**Risk:** low.

---

# Phase 4 — Medium / Low Tail (after 1–3)

Concise specs; each is a small coding-team run. Detail expands on request.

| WS | BB | File(s) | Change | Flag / default |
|----|----|---------|--------|----------------|
| **WS-14** | `agents/semantic-early-stopping-agent-loops` | `agent_loop.py` round loop `~:2970`, helper by `context_budget.py` | embed each round's draft (local lane `embeddings.py`), early-stop refine loops when last-2 cosine distances `<~0.06`; keep `MAX_AGENT_ROUNDS=50` (`agent_tools/__init__.py:70`) as failsafe. Do **not** gate on a per-round LLM judge. | `agent_semantic_stop` (opt-in) |
| **WS-15** | `context/rag-layering-long-context-negotiable` | `rag_vector.py:343` (k=5), `tool_index` (k=8) | make top-k a function of effective window via `model_context.budget_context_for_model`; tight-k for small local, wide for long-context | default keeps current k |
| **WS-16** | `security/context-fractured-…` + `agents/12-factor` (Factor 8) | `agent_tools/admin_tools.py` effectful handlers, `tool_execution.py` `execute_tool_block` (PEP) | preview→commit on irreversible sinks (send_email, manage_mcp add, webhooks): handler returns canonicalized (intent,args) preview; separate step (HMAC-bound or human-confirm) commits. `agent_runs` already supports pause/resume. | `effect_preview_commit` (on for irreversible tools) |
| **WS-17** | `security/pauth-task-scoped-authorization` | `tool_policy.py` `build_effective_tool_policy` | derive allowed-tool set from the task (start zero, enable what's needed); generalize plan-mode's allowlist-as-inverse-denylist | opt-in |
| **WS-18** | `mcp/cmtf-causal-minimal-tool-filtering` | `mcp_manager.py:105-130` (`readOnlyHint`/`destructiveHint`) | risk-gating slice only: withhold destructive MCP tools until causally justified (a prior read produced the handle). **Not** full STRIPS contracts (over-engineering). | opt-in |
| **WS-19** | `mcp/mcp-reliability-2181` + `july-2026-spec` | `mcp_manager.py` `call_tool:434`, `_do_call:476`, `requirements.txt` | generalize retry-then-degrade to remote servers (currently builtin-only `:504`); flag empty/degraded 200-OK results; **pin & audit the `mcp` SDK version for the 2026-07-28 spec cutover**; treat `_connect_sse` as legacy | on |
| **WS-20** | `security/skillspector` + `memory/claude-mem` + `agents/skillnb` | `tools/system.py:24` (`do_manage_skills`), `memory_provider.py` recall, skill lifecycle | (a) static pre-save scan of skill/note content (curl\|sh, base64 exec, self-write, injection markers); (b) split memory recall into index→get-by-ids progressive disclosure; (c) repair-burden **demotion** for skills, scoped to recurring automations | per-sub-item |
| **WS-21** | `context/swe-mem-agent-decided-memory-compression` | `tool_schemas.py`, `tool_execution.py`, `agent_loop.py` observation formatting | add an agent-invoked `compress(span, analysis)` builtin that folds a named span of session history into an agent-written summary; annotate each observation with `remaining_context_length`. Prompt-only (untrained) — gives the agent when/what/how control. Pairs with WS-12. Full RL recipe out of scope. | `agent_compress_tool` (opt-in) |
| **WS-22** | `context/instruction-bleed-compositional-behavioral-leakage` | test suite over `agent_loop._assemble_prompt` (`~:1636-1648`) | module-interaction regression test: hold a focal behavior fixed, add/remove an unrelated domain rule-pack or skill, assert the focal tool-selection / output distribution is stable. Guards the many co-resident rule-packs. Test-only; no runtime change. | n/a (tests) |
| **WS-23** | `agents/silent-failure-entropy-six-layer-lifecycle` | new scheduled task in `task_scheduler.py` (sibling of `tidy_sessions`/`audit_skills`) + a checker | clock-driven integrity gate: re-verify concrete artifacts the agent claims to have produced (files exist, edits applied, tasks scheduled) **independent of the model's self-report**; force a re-ground/compact when a session crosses a round/context threshold. Reuses the scheduler tick + `context_compactor`. Distinct from `bg_monitor` (which is job-completion, not drift). | `session_integrity_gate` (opt-in) |
| **WS-24** | `agents/steer-dont-solve-small-critic` | `agent_loop.py` per-round loop, after tool_blocks resolve (`~:2880`) | optional cheap mid-trajectory steer: a small/fast model reviews the last round's tool plan and injects a one-line course-correction system message when it detects a wrong strategy before it compounds. Reuse the teacher-escalation endpoint plumbing; gate like the verifier (effectful multi-round only). Complements WS-1 (post-hoc) with intra-trajectory steering. | `agent_steer_critic` (opt-in) |
| **WS-25** | `security/agenttrust-runtime-tool-interception` | `agent_tools/subprocess_tools.py` `BashTool` | pre-execution risk evaluation for the bash tool: shell deobfuscation → order-aware chain detection (data-exfil / persistence / reverse-shell sequences) → return `block`/`human-review` on critical patterns. **Complements, does not replace, WS-6** (sandbox is the containment; this is the interception verdict). Fail-closed (exception ⇒ review). | `bash_risk_intercept` (opt-in; defense-in-depth behind WS-6) |

**Also (odysseus-vulns residual, trivial):** `safe_chmod(APP_DB, 0o600)` after `create_all` in `core/database.py:1876`. One-line defense-in-depth beyond the Fernet-at-rest already present. Fold into any Phase-2 run.

---

## Cross-cutting: testing & rollout

- **Test substrate (mandatory, no mocks):** temp `memory.json` + temp SQLite for stores; real stdio subprocess for MCP stub servers; in-process FastAPI + `httpx.AsyncClient` for route tests; real temp dirs for the sandbox WS. Ollama/local-LLM steps mock **only** when the model isn't installed.
- **Every WS ships behind its flag**; Phase-1 safety flags default on, perf/context flags default on-with-threshold, security-hardening opt-ins default off until dogfooded.
- **Per-phase verification gate:** run the full suite + a manual dogfood pass before starting the next phase. `/second-opinion` (Codex) on the Phase-1 plan and diff is worth it — it touches the learning substrate.
- **Migration safety:** WS-0/2/3 are additive and reversible (retire-not-delete). Back up `memory.json` before first run on real data.

## Recommended build order (condensed)

1. **WS-0 → WS-2 + WS-3** (one run — shared `memory.py` write path) → **WS-1** → **WS-4 → WS-5**. *This is the differentiator; do it first, review with opus.*
2. **WS-6** (sandbox) standalone — highest absolute security value.
3. **WS-7 + WS-8** (one run) → **WS-9**.
4. **WS-10 → WS-11**, then **WS-12**, **WS-13** (parallel).
5. Phase-4 tail as capacity allows; **WS-19's SDK pin is time-boxed to the 2026-07-28 MCP cutover** — do that one before the deadline regardless of phase.

## Routing note

This spec is the brief source. To execute: `/coding-team` per WS (or per-phase for the tightly-coupled Phase-1 runs), or `/delegate odysseus <WS>` to fork into the repo. Implementation model **sonnet**; Phase-1 design review **opus**; mechanical one-liners (WS chmod) **haiku**.
