# Mesh → Workflow Mapping Reference

Translation table, routing semantics, lossy features, and bridge tactics for compiling
a tx mesh into a Claude Code Workflow script.

## Contents
- Topology → script structure
- Routing translation (the core transform)
- Prompt adaptation (mandatory rewrites)
- HITL bridging
- Lossy features + bridge tactics
- Emitted script conventions

## Topology → script structure

| Normalizer `topology` | Mesh mechanism | Script structure |
|---|---|---|
| `linear` | routing chain A→B→C | Sequential `await agent(...)` calls, each feeding the next |
| `branching` | agent-mode status routing with multi-destination maps | `while` loop over `current` agent + `switch` on returned `status` (see below) |
| `dispatcher` | flat `{agent: next}` table | Sequential calls in table order; encode table as a const for readability |
| `fanout` | `parallelism` blocks | `parallel([...])` for the block, sequential around it; prefer `pipeline()` if items flow through stages |
| `ensemble` | `ensemble` config (coordinator + aggregation) | `parallel()` over member agents → one aggregator/judge `agent()` applying the aggregation strategy |
| `fsm` | states, gates, transitions | Explicit state loop: `let state = fsm.initial; while (state !== 'done') { ... switch ... }` — transitions become case arms |
| `free` | agents pick targets in output | Include `next` in every agent's schema (enum of agent names + `done`); route in a bounded while loop |

## Routing translation (the core transform)

Mesh agents signal `status` in message frontmatter; routing maps status → destination.
In a workflow, force the same contract through structured output:

1. For each agent, derive a schema whose `status` enum is exactly its routing keys
   (e.g. `["complete", "needs-more-data", "blocked"]`), plus a `payload`/domain fields
   for the actual work product, and `question` when any route targets core.
2. Compile the routing table into a `switch (result.status)` inside a bounded loop:

```javascript
const MAX_HOPS = 16  // guardrail stand-in: bound every routing loop
let current = 'interviewer', carry = args, hops = 0
while (current !== 'done' && ++hops <= MAX_HOPS) {
  const r = await runAgent(current, carry)
  switch (`${current}:${r.status}`) {
    case 'interviewer:complete':    current = 'sourcer'; break
    case 'analyst:needs-more-data': current = 'sourcer'; break   // loops are fine — bounded by MAX_HOPS
    case 'writer:complete':         current = 'done'; break
    default: return { status: 'blocked', at: current, question: r.question ?? r.summary }
  }
  carry = r
}
```

3. Routes to `core` (blocked/ask) become `return { status: 'blocked', ... }` — never
   swallowed, never AskUserQuestion (unavailable inside workflows). See HITL bridging.
4. `iteration` config (quality loops) → `for (let i = 0; i < maxIterations; i++)` with
   the judge's verdict as the break condition; `onFail: 'halt'` → return a failure object.
5. Carry state between hops explicitly. Meshes pass context via message files; the
   workflow must thread prior results into the next prompt (interpolate the relevant
   fields, not the whole blob).

## Prompt adaptation (mandatory rewrites)

Mesh prompts are written for the file-message runtime. Compiling them verbatim breaks
the workflow (agents will try to write `.ai/tx/msgs/` files). For each prompt:

- **Strip**: message-writing protocol sections (frontmatter formats, `.ai/tx/msgs/`
  paths, routing/status instructions, references to messaging other agents or core).
- **Replace with**: "Your final output is returned directly via structured output.
  Set `status` to one of [...routing keys...] and put your work product in the fields
  provided." (The schema enforces it; the sentence aligns the prompt.)
- **Keep**: role, method, quality bars, domain instructions. Agents that do their
  own file I/O (Read/Write to a workspace dir) keep those instructions verbatim —
  subagents have the same tools. Only the inter-agent messaging protocol is stripped;
  disk artifacts are a feature, not a mesh mechanic.
- **Inline**: `command` fields — resolve to the skill/command file and open the
  prompt with "Read <path>/SKILL.md and follow it with args {...}" (subagents cannot
  execute slash commands). `load` fields become "Read these files first: ..." lines.
- **Escape**: backticks and `${` in prompt text when embedding as template literals —
  prefer plain single-quoted concat or `String.raw` if a prompt is full of them.

## HITL bridging

Workflows cannot suspend for human input. Compile HITL as a two-layer protocol:

- **Inside the script**: any route to core (blocked, ask, gate-exit) returns
  `{ status: 'blocked'|'ask', at: <agent>, question, state: <carry> }` immediately.
- **In SKILL.md contract (the invoking Claude)**: on an `ask`/`blocked` return, use
  AskUserQuestion in the main loop, then re-invoke the workflow with
  `args = { resume_at: <agent>, answer, state }`. The script's entry must honor
  `args.resume_at` (start the loop at that agent with `carry = {...state, answer}`).

Meshes with `interaction: [none]` skip all of this — no resume plumbing, keep it lean.

**Capability/prompt conflict policy**: the config's capability declaration wins. If
`interaction: [none]` but a prompt contains a human-confirmation gate ("wait for
approval before proceeding"), strip the gate from the adapted prompt and add a
`// LOSSY: <agent> prompt had a HITL gate contradicting interaction:[none] — stripped`
comment. The inverse (capability declares interaction but no prompt asks) needs no
action beyond keeping the blocked/ask return path.

## Lossy features + bridge tactics

The normalizer emits a `lossy` list. For each entry, add ONE loud comment block near
the top of the emitted script (`// LOSSY: <field> — <note>`) and apply the bridge:

| Mesh feature | Bridge |
|---|---|
| `guardrails` / `max_mesh_messages` | `MAX_HOPS` loop bounds; `budget.remaining()` checks in long loops |
| `rearmatter` | Fold fields (`confidence`, `gotchas`, `learnings`) into agent output schemas |
| `checkpoint` / `fork_from` | Serialize state as structured return; pass into branches as input (no true conversation forking) |
| `load` (preload) | "Read these files first: ..." line in the prompt |
| `workspace` | Keep mesh-level output path as a const; instruct writer agents to Write there |
| `fragments` | Resolve at compile time (read fragment YAMLs, compose, inline the result) |
| FSM file-gates | Scripts have NO fs access — gate checks become micro-agents (`model: 'haiku', effort: 'low'`, schema `{passed: boolean}`); near-deterministic, pennies per gate |
| `persistence` / `continuation` | UNSUPPORTED — each agent() is fresh. `resumeFromRunId` gives crash-resume of a run, not session continuity |
| `max_turns` | UNSUPPORTED — no per-agent turn cap; rely on budget + prompt scoping |

## Compiled transforms (NOT lossy — generate these)

**`manifest` / `manifest_enforcement`** — compile into enforcement, don't drop:
- Post-validation: after the producing stage, a verify step confirms each declared
  artifact (agent checks paths, returns `{validated, errors: []}`), or fold booleans
  into the producer's own output schema for cheap cases.
- Retry: wrap producer+verify in `for (let i = 0; i < max_retry; i++)`, feeding
  `errors` back into the retry prompt. `strict` → return a failure object on
  exhaustion; `warning` → `log()` and continue.
- Pre-validation (`reads`) becomes a "Read these files first; report if missing"
  prompt line on the consuming agent.

**per-agent `mcpServers`** — full fidelity via custom subagents. Compile as:
- Emit `.claude/agents/<mesh>-<agent>.md` with the mesh agent's servers translated
  into `mcpServers:` frontmatter (inline stdio/http definitions). Inline servers
  auto-connect when the subagent spawns and auto-disconnect when it finishes —
  scoped to that agent only, independent of the main session. A bare string entry
  (`- github`) instead reuses a parent-session server.
- Call it from the script with `agent(prompt, { agentType: '<mesh>-<agent>' })`.
- Per-agent `permissions` ride along: the same agent file takes a `tools:` field
  for allowlisting.
- Caveats: OAuth-requiring servers must be pre-authenticated interactively (`/mcp`)
  or use static bearer tokens; enterprise `--strict-mcp-config` policies still apply.
- VERIFIED (Claude Code 2.1.187, live echo test) — with two hard-won gotchas:
  1. `mcpServers:` MUST be a YAML **list** of single-key maps (`- name: {type, ...}`).
     A plain mapping fails `Array.isArray` in the parser and is dropped SILENTLY —
     the agent spawns fine with zero extra MCP tools.
  2. The agent registry is cached: a newly emitted or edited agent file is not
     spawnable immediately. After emitting agent files, have the user run
     `/reload-skills` (refreshes agents too) or wait a turn boundary, and verify the
     agentType resolves before launching the workflow.
- Fallback when a custom agent file is unwanted: session-connected servers
  (`.mcp.json`) are reachable by every workflow agent via ToolSearch — add a prompt
  line "load the <server> tools via ToolSearch" instead.
Doc: https://code.claude.com/docs/en/subagents.md ("Scope MCP servers to a subagent").

**`chrome`** — same mechanism: emit an agentType whose frontmatter declares a browser
MCP server (e.g. playwright inline stdio).

**`thinking`** — map to `opts.effort`: `thinking: false` → `effort: 'low'`;
default/true → omit (inherit session); explicitly heavy reasoning roles → `'high'`.

**`lifecycle` hooks** — `worktree:create` → `isolation: 'worktree'` on the relevant
`agent()` calls (fresh worktree, auto-removed if unchanged). `commit:auto` → commit
instruction on the final writing agent or a dedicated teardown stage. Other hooks →
explicit setup/teardown `agent()` calls around the main flow.

**`brain: true`** — the mesh runtime just injects a brain-access prompt fragment;
workflow agents have the same filesystem access, so inline the identical fragment
into each agent prompt at compile time.

**`command` (slash prefix)** — subagents CANNOT execute slash commands. Resolve the
command to its skill/command file at compile time and open the prompt with:
"Read <path>/SKILL.md and follow its instructions with arguments: {...}". If the
file can't be resolved, surface it to the user rather than emitting a dead `/cmd` line.

**`intents` patterns** — becomes `meta.whenToUse`: the invoking model consults
workflow descriptions when choosing what to run, which reproduces intent routing.
Translate the mesh's patterns into natural-language trigger phrasing.

## Emitted script conventions

- File header comment block: name, one-line description, responsibilities list,
  `Source mesh:` absolute path, `Compiled by: mesh-to-workflow`.
- `export const meta = {...}` pure literal; `phases` roughly one per pipeline stage
  or FSM state cluster; `whenToUse` from mesh description + capability.domain.
- Phase assignment: inside a routing loop or `runAgent()` helper, use `opts.phase`
  on each `agent()` call (same string → same progress group, safe when an agent is
  revisited on loop-back). Bare `phase()` calls are only for straight-line scripts.
- `const PROMPTS = { agentName: \`...\` }` — one entry per agent, original agent
  names preserved. Human-scale rule: a reader must be able to see the whole control
  flow in ~40 lines without scrolling through prompts.
- `const MODELS = { agentName: 'haiku'|'sonnet'|'opus' }` from config; pass as
  `opts.model`. Omit for agents with no model set (inherit session).
- Schemas as named consts (`const ANALYST_OUT = {...}`) next to PROMPTS.
- `log()` at every hop: `log(\`interviewer → sourcer (complete)\`)` — the live
  trace replaces `tx spy`.
- No `Date.now()`, `Math.random()`, argless `new Date()` — forbidden by the runtime.
- Output location: `.claude/workflows/<mesh>.js` in the target project (default),
  `~/.claude/workflows/<mesh>.js` if the user asks for global.
- Validate before handing over with the bundled checker (NOT `node --check`, which
  rejects the top-level `return`s the runtime allows):
  `node <skill-dir>/scripts/check_workflow.js <file>`.
