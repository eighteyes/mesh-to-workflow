---
name: mesh-to-workflow
description: Compile a tx mesh (config.yaml + agent prompts) into a deterministic, human-readable Claude Code Workflow script — and optionally run it. Replaces the SDK-metered tx runtime with session-native workflows. Use when the user wants to compile, convert, or port a mesh to a workflow, run a mesh without the tx runtime, or asks "mesh to workflow", "compile mesh X", "run mesh X as a workflow", "port this mesh". Not for authoring workflows from scratch (use workflow-author) or building/editing meshes (use mesh-builder).
---

# mesh-to-workflow

Compile a tx mesh directory into a Workflow script: agents become `agent()` calls,
routing tables become explicit control flow, prompts are inlined. The emitted script
is the human-scale depiction of the mesh — readable, editable, deterministic.

Mesh locations: `meshes/<name>/` in tx-core, `.ai/tx/generated-meshes/<hash>/`,
or any directory containing a `config.yaml` with a `mesh:` key.

## Compile workflow

1. **Normalize** — run the bundled script; never parse config.yaml by hand:
   ```bash
   python3 /Users/god/ai/skills/mesh-to-workflow/scripts/mesh_to_json.py <mesh-dir>
   ```
   Output: mesh metadata, classified `topology`, routing, agents with `prompt_text`
   inlined, and a `lossy` list of features with no workflow equivalent.
   Skim the source config.yaml once after: if a field there is absent from the JSON,
   compile from the source value AND report the normalizer gap to the user.

2. **Read [references/mapping.md](references/mapping.md)** — the translation table.
   It covers topology→structure, the routing→switch transform, mandatory prompt
   rewrites, HITL bridging, and per-feature bridge tactics. Follow it exactly.

3. **Compile** — write `.claude/workflows/<mesh>.js` in the target project
   (`~/.claude/workflows/` only if the user wants it global). Structure per
   mapping.md conventions: header comment block, pure-literal `meta`, `PROMPTS` /
   `MODELS` / schema consts, control flow readable in one screen, `log()` at every
   hop, one `// LOSSY:` comment per dropped feature.
   For the Workflow tool API beyond mapping.md, consult the workflow-author spec:
   `/Users/god/ai/skills/workflow-author/references/workflow-tool-spec.md`.

4. **Validate** — do NOT use `node --check` (top-level `return` is legal in the
   workflow runtime but fails module parsing). Use the bundled checker, which
   compiles the body as an AsyncFunction exactly like the runtime:
   ```bash
   node /Users/god/ai/skills/mesh-to-workflow/scripts/check_workflow.js .claude/workflows/<mesh>.js
   ```
   Then re-read the
   script once as a reviewer: every routing destination reachable, every loop
   bounded, no prompt still instructing agents to write `.ai/tx/msgs/` files.

5. **Report** — show the user the control-flow skeleton (not the prompts), the
   lossy list, and where the file landed.

## Run mode

If the user supplied a task prompt (or said run/dispatch), after compiling invoke:
```
Workflow({ scriptPath: ".claude/workflows/<mesh>.js", args: { prompt: <task> } })
```

**HITL contract**: if the workflow returns `{ status: 'ask' | 'blocked', at, question, state }`,
relay `question` to the user with AskUserQuestion, then re-invoke with
`args: { resume_at: at, answer, state }`. Loop until a terminal return. Scripts
compiled from `interaction: [none]` meshes never return `ask` — no loop needed.

## Judgment calls (compiler discretion)

- Collapse trivial relay agents (pure pass-through, no transformation) into direct
  data flow; note the collapse in a comment.
- Identical agents differing only by name (ensemble members) → one prompt const,
  `parallel()` over instances.
- Preserve mesh semantics over mesh mechanics: the goal is the same function, not a
  simulation of the runtime.
