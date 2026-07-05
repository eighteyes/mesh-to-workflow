#!/usr/bin/env python3
# mesh_to_json.py
# Normalize a tx mesh directory into a single JSON document for workflow compilation.
# Responsibilities:
#   - Load and parse <mesh-dir>/config.yaml
#   - Resolve each agent's prompt file relative to the mesh dir and inline its text
#   - Classify topology shape (linear | fanout | ensemble | fsm | dispatcher | free)
#   - Flag config features with no Workflow-tool equivalent (lossy list, per feature)
#   - Emit normalized JSON to stdout; exit non-zero with a message on malformed input

import json
import sys
from pathlib import Path

import yaml

# Mesh/agent fields with no Workflow equivalent. Value = short note the compiler
# surfaces as a loud comment in the emitted script.
LOSSY_MESH_FIELDS = {
    "persistence": "sessions do not persist across workflow runs",
    "continuation": "no cross-call session reuse; each agent() is fresh",
    "manifest": "COMPILED TRANSFORM: generate verify stage + retry loop (see mapping.md)",
    "manifest_enforcement": "COMPILED TRANSFORM: honor max_retry/strict in the generated loop",
    "lifecycle": "COMPILED TRANSFORM: worktree:create -> isolation:'worktree'; commit:auto -> teardown stage (see mapping.md)",
    "guardrails": "no runtime guardrails; encode limits as loop bounds / budget checks",
    "rearmatter": "fold rearmatter fields into agent output schemas",
    "brain": "COMPILED TRANSFORM: inline the brain-access prompt fragment (see mapping.md)",
    "intents": "COMPILED TRANSFORM: translate patterns into meta.whenToUse trigger phrasing",
}
LOSSY_AGENT_FIELDS = {
    "checkpoint": "no session forking; serialize state as a structured return value",
    "fork_from": "no session forking; pass prior stage output as input instead",
    "load": "no file preload; Read files in-script or instruct the agent to read them",
    "workspace": "no per-agent workspace schema; use structured output schema",
    "mcpServers": "COMPILED TRANSFORM: emit .claude/agents/<mesh>-<agent>.md with mcpServers frontmatter, call via opts.agentType (see mapping.md)",
    "permissions": "COMPILED TRANSFORM: tools: field on the generated custom agent file (see mapping.md)",
    "postconditions": "no tool-call validation; add a verify stage if needed",
    "cli": "no external CLI wrapper",
    "chrome": "COMPILED TRANSFORM: agentType with browser MCP in frontmatter (see mapping.md)",
    "thinking": "COMPILED TRANSFORM: map to opts.effort (false -> 'low')",
    "max_turns": "per-agent turn caps not controllable",
    "max_messages": "message caps not applicable; agents return once",
    "fragments": "resolve fragments at compile time and inline the composed prompt",
}


def classify_topology(cfg: dict) -> str:
    if cfg.get("fsm"):
        return "fsm"
    if cfg.get("ensemble"):
        return "ensemble"
    if cfg.get("parallelism"):
        return "fanout"
    mode = cfg.get("routing_mode", "agent")
    if mode == "dispatcher":
        return "dispatcher"
    if mode == "free":
        return "free"
    routing = cfg.get("routing")
    if isinstance(routing, list):
        return "linear"
    if isinstance(routing, dict):
        # Agent-mode routing with any multi-destination status map is branching.
        for dests in routing.values():
            if isinstance(dests, dict) and len(dests) > 1:
                return "branching"
        return "linear"
    return "linear"


def _completion_agents(cfg: dict) -> list | None:
    # Configs use both singular and plural forms; normalize to a list.
    val = cfg.get("completion_agents", cfg.get("completion_agent"))
    if val is None:
        return None
    return val if isinstance(val, list) else [val]


def normalize(mesh_dir: Path) -> dict:
    config_path = mesh_dir / "config.yaml"
    if not config_path.is_file():
        sys.exit(f"error: {config_path} not found")
    cfg = yaml.safe_load(config_path.read_text()) or {}

    lossy = []
    for field, note in LOSSY_MESH_FIELDS.items():
        if field in cfg:
            lossy.append({"scope": "mesh", "field": field, "note": note})

    agents = []
    for a in cfg.get("agents", []):
        entry = dict(a)
        prompt_rel = a.get("prompt")
        if prompt_rel:
            prompt_path = mesh_dir / prompt_rel
            if prompt_path.is_file():
                entry["prompt_text"] = prompt_path.read_text()
            else:
                entry["prompt_text"] = None
                lossy.append({
                    "scope": f"agent:{a.get('name')}",
                    "field": "prompt",
                    "note": f"prompt file missing: {prompt_rel}",
                })
        for field, note in LOSSY_AGENT_FIELDS.items():
            if field in a:
                lossy.append({"scope": f"agent:{a.get('name')}", "field": field, "note": note})
        agents.append(entry)

    return {
        "mesh": cfg.get("mesh"),
        "description": cfg.get("description"),
        "source_dir": str(mesh_dir.resolve()),
        "topology": classify_topology(cfg),
        "routing_mode": cfg.get("routing_mode", "agent"),
        "entry_point": cfg.get("entry_point"),
        "completion_agents": _completion_agents(cfg),
        "routing": cfg.get("routing"),
        "parallelism": cfg.get("parallelism"),
        "ensemble": cfg.get("ensemble"),
        "fsm": cfg.get("fsm"),
        "iteration": cfg.get("iteration"),
        "hitl": cfg.get("capability", {}).get("interaction"),
        "agents": agents,
        "lossy": lossy,
    }


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: mesh_to_json.py <mesh-dir>")
    print(json.dumps(normalize(Path(sys.argv[1])), indent=2))


if __name__ == "__main__":
    main()
