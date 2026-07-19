---
name: create-mesh
description: Author a portable mesh (config.yaml + agent prompts) from a natural-language description of a multi-agent process — the durable, reviewable artifact that compiles to a Claude Code Workflow via mesh-to-workflow. Use when a user wants to design, describe, or create a mesh, multi-agent pipeline, or agent team as an artifact ("create a mesh", "design a mesh for X", "I want agents that do X then Y", "make me an agent pipeline"). Not for compiling existing meshes (use mesh-to-workflow) or one-off orchestration (use the Workflow tool directly).
---

# create-mesh

Turn a described process into a mesh artifact. The mesh is the durable form:
topology, routing, and status contracts pinned as reviewable YAML, agent prompts
as separate files — decided BEFORE any workflow script exists. Compilation
(mesh-to-workflow) is then mechanical. This separation exists because authoring
a workflow directly makes the LLM decide logic and prompts simultaneously in one
pass; the mesh forces the logic to be negotiated as data first.

## Workflow

1. **Elicit** — from the user's description, pin down:
   - The agents: distinct roles, not steps. Merge roles that share one skillset.
   - The shape: linear chain, branching statuses, fan-out, ensemble, or FSM.
   - Exit statuses per agent (each becomes a routing key + schema enum).
   - HITL: any point where a human must approve/answer (`__ask__` routes)?
   - Special needs: MCP servers, browser, worktree isolation, quality loops.
   Ask only what the description leaves genuinely open — one focused round of
   questions (AskUserQuestion), not an interview.

2. **Read [references/mesh-schema.md](references/mesh-schema.md)** — the
   compilable subset. Author ONLY fields in that schema so the mesh compiles
   with zero LOSSY comments. See [assets/example-mesh/](assets/example-mesh/)
   for a complete worked example.

3. **Propose the skeleton** — before writing files, show the user the routing
   graph as a compact YAML sketch (agents + statuses + destinations). This is
   the artifact's logic; get it agreed while it is cheap to change.

4. **Emit** — write `meshes/<name>/config.yaml` plus one `<agent>/prompt.md`
   per agent (structure per the schema's prompt-file section: role, method,
   quality bars, status contract, inputs, outputs). Prompts are runtime-agnostic:
   no message files, no orchestration mechanics.

5. **Validate** — run the mesh-to-workflow normalizer against the new mesh:
   ```bash
   python3 <mesh-to-workflow-skill-dir>/scripts/mesh_to_json.py meshes/<name>
   ```
   Fix anything in the `lossy` list (a clean portable mesh has none) and any
   missing prompt files it flags.

6. **Offer compilation** — the artifact is done; ask whether to compile and/or
   run it now via the mesh-to-workflow skill.

## Design rules

- Fewest agents that preserve distinct judgment. Two agents that never disagree
  should be one agent.
- Every status must be decidable by the agent emitting it. "escalate-if-unsure"
  beats a status the agent can't self-assess.
- Every path must reach `__done__`; loops must have a natural convergence
  argument (the compiler bounds them regardless).
- Judge/verifier agents get their own role — never let a producer grade itself.
- Default models: haiku for mechanical checks, sonnet for production work,
  opus only where judgment quality dominates cost.
