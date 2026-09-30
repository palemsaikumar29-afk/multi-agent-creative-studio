"""Copywriter: taglines + ad copy + CTAs.

LLM-backed when a key is configured; deterministic template engine in
offline mode so the pipeline is fully testable without network or keys.
"""
from __future__ import annotations

import random

from ..services.llm_factory import call_llm_with_retry, provider_status

_TONE_OPENERS = {
    "friendly": ["Meet", "Say hello to", "Discover"],
    "bold": ["Unleash", "Own", "Conquer with"],
    "playful": ["Psst — meet", "Say hi to", "Get ready for"],
    "professional": ["Introducing", "Experience", "Trust"],
    "luxury": ["Indulge in", "Behold", "Savor"],
}

_TONE_VERBS = {
    "friendly": ["makes", "brings", "gives"],
    "bold": ["dominates", "rewrites", "powers"],
    "playful": ["sprinkles", "supercharges", "jazzes up"],
    "professional": ["delivers", "ensures", "optimizes"],
    "luxury": ["elevates", "curates", "refines"],
}

_TAGLINE_FLAIR = [
    "beautifully.", "effortlessly.", "every single day.", "like never before.",
    "without compromise.", "from day one.", "the smart way.",
    "and then some.", "with zero hassle.", "you'll actually love.",
    "built to last.", "ready when you are.",
]

_CTAS = [
    "Try it free today.",
    "Get started in minutes.",
    "See it in action — book a demo.",
    "Join thousands of happy customers.",
    "Start your free trial now.",
]


def _template_copies(product: str, description: str, audience: str,
                     tone: str, variants: int, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    tone = tone.lower() if tone.lower() in _TONE_OPENERS else "friendly"
    openers = _TONE_OPENERS[tone]
    verbs = _TONE_VERBS[tone]
    kw = description.split()[:8]
    kw_str = " ".join(kw)
    copies = []
    for i in range(variants):
        opener = rng.choice(openers)
        verb = rng.choice(verbs)
        cta = rng.choice(_CTAS)
        flair = rng.choice(_TAGLINE_FLAIR)
        tagline = f"{product}: {verb} {audience} life, {flair}"
        ad_copy = (
            f"{opener} {product} — {kw_str}. Built for {audience}, "
            f"it {verb} every day a little better. {cta}"
        )
        copies.append({"tagline": tagline, "ad_copy": ad_copy, "cta": cta})
    return copies


def write_copies(product: str, description: str, audience: str, tone: str,
                 variants: int, seed: int = 7) -> tuple[list[dict], bool]:
    """Return (copies, offline)."""
    _, _, key_present, _ = provider_status()
    if key_present:
        prompt = (
            f"Write {variants} distinct ad-copy variants for a product.\n"
            f"Product: {product}\nDescription: {description}\n"
            f"Audience: {audience}\nTone: {tone}\n\n"
            "For each variant reply in this exact block format:\n"
            "TAGLINE: <short tagline>\nAD: <2-3 sentence ad copy>\n"
            "CTA: <call to action>\n---\n"
        )
        try:
            raw = call_llm_with_retry(prompt)
            blocks = [b.strip() for b in raw.split("---") if b.strip()]
            copies = []
            for block in blocks[:variants]:
                tag, ad, cta = "", "", ""
                for line in block.splitlines():
                    head, _, body = line.partition(":")
                    head = head.strip().upper()
                    if head == "TAGLINE":
                        tag = body.strip()
                    elif head == "AD":
                        ad = body.strip()
                    elif head == "CTA":
                        cta = body.strip()
                if tag and ad:
                    copies.append({"tagline": tag, "ad_copy": ad, "cta": cta})
            if copies:
                return copies, False
        except Exception:  # noqa: BLE001 - fall through to templates
            copies = []  # discarded; template fallback below
    return _template_copies(product, description, audience, tone,
                            variants, seed), True
