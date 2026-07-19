# Portable Mesh Schema (compilable subset)

The authoring target for create-mesh. Every field here has a defined translation
in mesh-to-workflow's mapping.md — a mesh using only this subset compiles with
no LOSSY comments.

## Contents
- Top-level fields
- Agent fields
- Topology structures
- Routing
- Status contract
- What NOT to author

## Top-level fields

```yaml
mesh: name                      # required, kebab-case
description: One line.          # required — becomes meta.description
capability:
  domain: [dev]                 # optional context tags
  interaction: [none]           # none | gate-exit | ask — drives HITL plumbing
entry_point: first-agent        # required
completion_agents: [last-agent] # agents allowed to end the run
routing_mode: agent             # agent (status routing) | dispatcher (linear table)
routing: {...}                  # see Routing
parallelism: {...}              # optional, see Topology
ensemble: {...}                 # optional, see Topology
fsm: {...}                      # optional, see Topology
iteration:                      # optional quality loop
  maxIterations: 3
  onFail: loop                  # loop | halt
workspace:
  path: .ai/output/{mesh}       # where writer agents put artifacts
```

## Agent fields

```yaml
agents:
  - name: analyst               # required, kebab-case
    model: sonnet               # haiku | sonnet | opus — omit to inherit session
    prompt: analyst/prompt.md   # required, path relative to mesh dir
    thinking: false             # optional — compiles to effort:'low'
    mcpServers:                 # optional — compiles to a generated agentType
      - playwright:             #   MUST be a list of single-key maps
          type: stdio
          command: npx
          args: ["-y", "@playwright/mcp@latest"]
    permissions:                # optional — compiles to tools: frontmatter
      allow: [Read, Grep, WebSearch]
    worktree: true              # optional — compiles to isolation:'worktree'
```

## Topology structures

Pick ONE shape (or plain routing):

```yaml
# Fan-out: run a set in parallel, then continue
parallelism:
  - agents: [reviewer-a, reviewer-b, reviewer-c]
    entry: splitter             # agent before the block
    exit: merger                # agent that receives all results

# Ensemble: N attempts, one judge aggregates
ensemble:
  agents: [solver-a, solver-b, solver-c]
  coordinator: judge
  aggregation_strategy: best-of # best-of | merge | vote

# FSM: explicit states and transitions
fsm:
  initial: draft
  states:
    - name: draft
      agent: writer
      transitions: { complete: review, blocked: __ask__ }
    - name: review
      agent: judge
      transitions: { accept: __done__, reject: draft }
```

## Routing (agent mode)

Map each agent's exit statuses to destinations. `__done__` ends the run,
`__ask__` suspends to the human (HITL):

```yaml
routing:
  interviewer:
    complete: { sourcer: "requirements gathered" }
    blocked:  { __ask__: "cannot proceed without clarification" }
  sourcer:
    complete: { analyst: "sources collected" }
  analyst:
    complete:        { writer: "analysis done" }
    needs-more-data: { sourcer: "insufficient sources" }
  writer:
    complete: { __done__: "report delivered" }
```

Dispatcher mode instead: `routing: { a: b, b: c, c: __done__ }` (flat chain).

Portable meshes use `__done__` / `__ask__` instead of tx's `core` destination.
(The mesh-to-workflow normalizer treats `core` and `__ask__`/`__done__`
equivalently: routes out of the mesh.)

## Status contract

Every status key under an agent's routing entry becomes an enum value in that
agent's compiled output schema. Rules:
- Statuses are kebab-case verbs of outcome: `complete`, `blocked`, `needs-more-data`
- Every agent MUST have at least one path that eventually reaches `__done__`
- Loops are allowed (they compile bounded); design them to converge
- An agent's prompt must explain when to emit each status

## Prompt files (one per agent)

Structure each prompt.md as:
1. **Role** — who this agent is, one paragraph
2. **Method** — how it works the task, imperative steps
3. **Quality bars** — what good output looks like
4. **Status contract** — "Set status to X when ..., Y when ..." matching routing keys
5. **Inputs** — what arrives in carry state from upstream agents
6. **Outputs** — fields it must produce (these become schema fields), plus any
   files it writes to the workspace

Write prompts runtime-agnostic: NEVER mention message files, frontmatter,
`.ai/tx/msgs/`, or other agents' inboxes. The agent receives input and returns
output; the orchestration layer is not its business.

## What NOT to author

These tx-runtime fields have no place in portable meshes (they compile lossily
or not at all): `checkpoint`, `fork_from`, `continuation`, `persistence`,
`max_turns`, `max_messages`, `load`, `manifest_enforcement` retry internals,
`lifecycle` beyond worktree/commit, `cli`, `chrome`, `intents`, `guardrails`.
Express limits as loop design; express preloads as prompt instructions.
