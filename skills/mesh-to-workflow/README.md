# mesh-to-workflow

Compile a tx mesh (config.yaml + agent prompt files) into a deterministic,
human-readable Claude Code Workflow script — and optionally run it.

## Why

The tx runtime executed meshes via the Claude Agent SDK (metered API tokens).
When the SDK pricing structure changed, running meshes that way stopped making
sense. Claude Code Workflows run on the session itself — same multi-agent
function, no per-token metering. This skill is the bridge: it treats a mesh
config as source code and the Workflow script as the compilation target.

The emitted script is the "human-scale depiction" of the mesh: agents become
named `agent()` calls, routing tables become a visible bounded loop + switch,
prompts are inlined as consts. You can read the whole control flow in one
screen, edit it, and re-run it.

## Usage

In any Claude Code session:

- "compile mesh research to a workflow"
- "run mesh research as a workflow: <task>"
- "port meshes/dev-full-ensemble"

Output lands at `.claude/workflows/<mesh>.js` in the target project
(`~/.claude/workflows/` if you ask for global). If you pass a task, the skill
launches the compiled workflow immediately after validation.

## Structure

```
mesh-to-workflow/
├── SKILL.md                    # compile workflow (normalize → map → emit → validate → run)
├── README.md                   # this file (human-facing; not loaded by the skill)
├── scripts/
│   ├── mesh_to_json.py         # deterministic normalizer: mesh dir → JSON
│   │                           #   (prompts inlined, topology classified, lossy flags)
│   └── check_workflow.js       # syntax checker that parses like the Workflow runtime
│                               #   (node --check rejects top-level return; this doesn't)
└── references/
    └── mapping.md              # translation bible: topology→structure, routing→switch,
                                #   prompt rewrites, HITL bridge, compiled transforms
```

## What compiles, what doesn't

Compiles at full or near-full fidelity:
- Topologies: linear, branching, dispatcher, fan-out, ensemble, FSM
- Status routing → bounded while/switch loop with schema-enforced statuses
- Manifest validation → generated verify stage + retry loop
- Per-agent MCP servers → generated `.claude/agents/<mesh>-<agent>.md` with
  `mcpServers` frontmatter, called via `agent(..., {agentType})` — verified live
  on Claude Code 2.1.187
- Per-agent permissions (`tools:` frontmatter), model tiers, thinking→effort,
  worktree lifecycle hooks (`isolation: 'worktree'`), brain injection,
  slash-command prefixes (resolved to "read the skill file" instructions),
  intent patterns (→ `meta.whenToUse`)
- HITL: workflow returns `{status: 'ask'|'blocked', at, question, state}`;
  the invoking session asks the human and re-invokes with `resume_at`

Genuinely lost (flagged with `// LOSSY:` comments in emitted scripts):
- Session persistence / continuation / checkpoint forking (every `agent()` is fresh)
- Per-agent `max_turns` caps
- Tmux injection and file-watcher messaging (runtime mechanics, not semantics)

## Gotchas (paid for in probes)

- Agent frontmatter `mcpServers:` must be a YAML **list** of single-key maps.
  A plain mapping is silently dropped — the agent spawns with no extra tools.
- The agent registry is cached: newly emitted agent files aren't spawnable
  until `/reload-skills` or a turn boundary. Verify the agentType resolves
  before launching the workflow.
- Validate emitted scripts with `scripts/check_workflow.js`, never `node --check`.

## Related

- `create-mesh` skill (this repo) — author a portable mesh from a description;
  the mesh is the durable artifact, this compiler is its backend. The split
  exists because authoring a workflow directly makes the LLM decide logic and
  prompts in one pass; a mesh pins the logic as reviewable YAML first.
- `workflow-author` skill — authoring workflows from scratch; carries the full
  Workflow tool spec this compiler targets
- `mesh-builder` skill — creating/editing the meshes themselves
- First compiled artifact: tx-core `.claude/workflows/research.js` (from `meshes/research`)
