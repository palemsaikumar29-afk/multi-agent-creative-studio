"""Pipeline nodes: brief -> copy -> visual -> critique -> (revise) -> plan."""
from __future__ import annotations

import os
import re

from ..services import images
from ..services.config import settings
from ..services.copywriter import write_copies
from ..services.llm_factory import call_llm_with_retry, provider_status
from ..services.safety import detect_injection, redact_pii

MAX_REVISION_ROUNDS = 2
APPROVAL_THRESHOLD = 7.0


def brief_node(state: dict) -> dict:
    raw = (f"{state['product']} {state['description']} "
           f"{state['audience']} {state.get('tone', 'friendly')}")
    is_injection, patterns = detect_injection(raw)
    if is_injection:
        return {"blocked": True, "injection_patterns": patterns}
    product, pii = redact_pii(state["product"].strip())
    description, pii2 = redact_pii(state["description"].strip())
    audience, pii3 = redact_pii(state["audience"].strip())
    tone = re.sub(r"[^a-zA-Z ]", "", state.get("tone", "friendly")).strip() or "friendly"
    try:
        variants = max(1, min(6, int(state.get("variants", 3))))
    except (TypeError, ValueError):
        variants = 3
    if len(product) < 2 or len(description) < 10 or len(audience) < 2:
        return {"blocked": True,
                "block_reason": "Brief too thin: need product (>=2 chars), "
                                "description (>=10 chars), audience (>=2 chars)."}
    return {"brief": {"product": product, "description": description,
                      "audience": audience, "tone": tone, "variants": variants},
            "blocked": False, "pii_kinds": pii + pii2 + pii3}


def copy_node(state: dict) -> dict:
    brief = state["brief"]
    round_no = state.get("round", 0)
    copies, offline = write_copies(brief["product"], brief["description"],
                                   brief["audience"], brief["tone"],
                                   brief["variants"], seed=7 + round_no * 101)
    return {"copies": copies, "copy_offline": offline, "round": round_no + 1}


def _visual_prompt(brief: dict, copy: dict) -> str:
    return (
        f"Advertising hero image for '{brief['product']}', {brief['tone']} tone. "
        f"Target audience: {brief['audience']}. "
        f"Tagline: {copy['tagline']}. "
        f"Product context: {brief['description'][:160]}. "
        "Professional marketing photography style, no text overlay."
    )


def visual_node(state: dict) -> dict:
    brief = state["brief"]
    outdir = os.path.join(settings.studio_output_dir, state["run_id"], "images")
    os.makedirs(outdir, exist_ok=True)
    assets = []
    for i, copy in enumerate(state["copies"]):
        prompt = _visual_prompt(brief, copy)
        path = os.path.join(outdir, f"visual_{i + 1}.png")
        provider = images.generate_image(
            prompt, path, seed=1000 + i + state.get("round", 1) * 77)
        assets.append({"prompt": prompt, "path": path, "provider": provider})
    return {"visuals": assets}


def score_copy(copies: list[dict], brief: dict) -> tuple[float, list[str]]:
    notes: list[str] = []
    if not copies:
        return 0.0, ["no copy variants produced"]
    taglines = [c["tagline"] for c in copies]
    score = 5.0
    if len(set(taglines)) == len(taglines):
        score += 1.0
    else:
        notes.append("duplicate taglines reduce variety")
    if any(brief["product"].lower() in t.lower() for t in taglines):
        score += 1.0
    else:
        notes.append("product name missing from taglines")
    avg_len = sum(len(c["ad_copy"]) for c in copies) / len(copies)
    if 80 <= avg_len <= 400:
        score += 1.0
    else:
        notes.append("ad copy length outside the 80-400 char sweet spot")
    if any(c["cta"].strip() for c in copies):
        score += 1.0
    else:
        notes.append("missing call to action")
    return min(10.0, score), notes


def score_visuals(visuals: list[dict]) -> tuple[float, list[str]]:
    notes: list[str] = []
    if not visuals:
        return 0.0, ["no visual assets produced"]
    providers = {v["provider"] for v in visuals}
    if providers == {"placeholder"}:
        notes.append("all visuals are labelled placeholders — connect an "
                     "image provider for real generations")
        return 4.0, notes
    if "pollinations" in providers or "dalle" in providers:
        return 9.0, notes
    return 6.0, notes


def critique_node(state: dict) -> dict:
    brief = state["brief"]
    copy_score, copy_notes = score_copy(state["copies"], brief)
    visual_score, visual_notes = score_visuals(state["visuals"])
    approved = (copy_score >= APPROVAL_THRESHOLD
                and visual_score >= APPROVAL_THRESHOLD)
    notes = copy_notes + visual_notes
    _, _, key_present, _ = provider_status()
    if key_present and not approved and state.get("round", 1) <= 1:
        # one LLM critique pass for richer notes
        try:
            raw = call_llm_with_retry(
                "You are a creative director. In 3 bullet points, critique "
                "these ad taglines for a campaign:\n"
                + "\n".join(f"- {c['tagline']}" for c in state["copies"]))
            notes = [raw.strip()] + notes
        except Exception:  # noqa: BLE001 - notes stay template-only
            notes = list(notes)
    return {"critique": {"copy_score": round(copy_score, 1),
                         "visual_score": round(visual_score, 1),
                         "notes": notes, "approved": approved}}


def plan_node(state: dict) -> dict:
    brief = state["brief"]
    _, _, key_present, _ = provider_status()
    if key_present:
        try:
            plan = call_llm_with_retry(
                "Write a compact 5-channel launch plan (<=150 words) for:\n"
                f"Product: {brief['product']}\nAudience: {brief['audience']}\n"
                f"Tone: {brief['tone']}\nTagline: {state['copies'][0]['tagline']}")
            return {"campaign_plan": plan.strip(), "plan_offline": False}
        except Exception:  # noqa: BLE001 - template plan below
            plan = ""  # replaced by the template plan below
    plan = (
        f"Launch plan for **{brief['product']}** ({brief['tone']} tone, "
        f"audience: {brief['audience']}):\n"
        "1. **Social (week 1):** teaser visuals + tagline across Instagram/"
        "TikTok; 3 posts/day.\n"
        "2. **Email (week 1-2):** launch sequence to existing list with the "
        "hero visual and CTA.\n"
        "3. **Paid search/social (week 2-4):** A/B the copy variants, kill "
        "losers after 1k impressions.\n"
        "4. **Influencers (week 3):** 5 micro-creators in the target niche.\n"
        "5. **Retargeting (week 4+):** site visitors see the winning variant.\n"
        "Measure: CTR, CAC, and signup conversion weekly."
    )
    return {"campaign_plan": plan, "plan_offline": True}
