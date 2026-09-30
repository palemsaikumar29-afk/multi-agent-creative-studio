"""LangGraph pipeline: brief -> copy -> visual -> critique -\
> (revise copy|visual up to 2 rounds) -> plan -> END."""
from __future__ import annotations

import json
import os
import time
from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from ..agents.nodes import (
    APPROVAL_THRESHOLD,
    MAX_REVISION_ROUNDS,
    brief_node,
    copy_node,
    critique_node,
    plan_node,
    visual_node,
)
from ..services.config import settings


class StudioState(TypedDict, total=False):
    product: str
    description: str
    audience: str
    tone: str
    variants: int
    run_id: str
    brief: dict
    blocked: bool
    block_reason: str
    injection_patterns: list[str]
    pii_kinds: list[str]
    copies: list[dict]
    copy_offline: bool
    round: int
    visuals: list[dict]
    critique: dict
    campaign_plan: str
    plan_offline: bool


def _route_after_critique(state: dict) -> str:
    if state.get("blocked"):
        return END
    critique = state.get("critique", {})
    if critique.get("approved"):
        return "plan"
    if state.get("round", 1) > MAX_REVISION_ROUNDS:
        return "plan"
    if critique.get("copy_score", 0) < APPROVAL_THRESHOLD:
        return "copy"
    return "plan"  # visuals only fail on placeholder mode; plan anyway


def build_pipeline():
    g = StateGraph(StudioState)
    g.add_node("brief", brief_node)
    g.add_node("copy", copy_node)
    g.add_node("visual", visual_node)
    g.add_node("critique", critique_node)
    g.add_node("plan", plan_node)
    g.set_entry_point("brief")
    g.add_conditional_edges("brief", lambda s: END if s.get("blocked") else "copy")
    g.add_edge("copy", "visual")
    g.add_edge("visual", "critique")
    g.add_conditional_edges("critique", _route_after_critique,
                            {"copy": "copy", "plan": "plan"})
    g.add_edge("plan", END)
    return g.compile()


def write_bundle(result: dict) -> str:
    """Write the campaign bundle (JSON + Markdown) to the output dir."""
    run_id = result["run_id"]
    outdir = os.path.join(settings.studio_output_dir, run_id)
    os.makedirs(outdir, exist_ok=True)
    bundle_path = os.path.join(outdir, "campaign_bundle.json")
    with open(bundle_path, "w") as f:
        json.dump({k: result[k] for k in
                   ("brief", "copies", "visuals", "critique",
                    "campaign_plan") if k in result}, f, indent=2)
    brief = result["brief"]
    lines = [f"# Campaign: {brief['product']}\n",
             f"**Audience:** {brief['audience']} · **Tone:** {brief['tone']}\n",
             "## Copy variants\n"]
    for i, c in enumerate(result.get("copies", []), 1):
        lines += [f"### Variant {i}\n",
                  f"**Tagline:** {c['tagline']}\n",
                  f"{c['ad_copy']}\n",
                  f"*{c['cta']}*\n"]
    lines.append("## Visuals\n")
    for i, v in enumerate(result.get("visuals", []), 1):
        lines.append(f"- Visual {i} ({v['provider']}): `{v['path']}`\n"
                     f"  Prompt: {v['prompt'][:120]}…\n")
    crit = result.get("critique", {})
    lines += ["\n## Critique\n",
              (f"Copy score: {crit.get('copy_score')}/10 · "
               f"Visual score: {crit.get('visual_score')}/10\n"),
              *[f"- {n}\n" for n in crit.get("notes", [])],
              "\n## Campaign plan\n", result.get("campaign_plan", "")]
    with open(os.path.join(outdir, "campaign.md"), "w") as f:
        f.writelines(lines)
    return outdir


def run_studio(product: str, description: str, audience: str,
               tone: str = "friendly", variants: int = 3) -> dict[str, Any]:
    run_id = time.strftime("%Y%m%d-%H%M%S")
    app = build_pipeline()
    result = app.invoke({"product": product, "description": description,
                         "audience": audience, "tone": tone,
                         "variants": variants, "run_id": run_id,
                         "round": 0})
    result["run_id"] = run_id
    if result.get("blocked"):
        return result
    result["bundle_dir"] = write_bundle(result)
    return result
