"""Gradio UI: creative brief form -> campaign bundle."""
from __future__ import annotations

import os

import gradio as gr

from src.graph.pipeline import run_studio
from src.services.llm_factory import provider_status

_LAST_BUNDLE: str = ""


def do_run(product: str, description: str, audience: str, tone: str,
           variants: int) -> tuple[str, list[str], str]:
    global _LAST_BUNDLE
    if not product.strip() or not description.strip() or not audience.strip():
        return "Please fill in product, description and audience.", [], ""
    result = run_studio(product.strip(), description.strip(),
                        audience.strip(), tone, int(variants))
    if result.get("blocked"):
        reason = (result.get("block_reason")
                  or "Blocked: injection patterns detected.")
        return f"🚫 {reason}", [], ""
    _LAST_BUNDLE = result["bundle_dir"]
    crit = result["critique"]
    gallery = [v["path"] for v in result["visuals"]]
    labels = [f"({v['provider']})" for v in result["visuals"]]
    md = (f"## 🎉 Campaign for **{result['brief']['product']}**\n"
          f"Critic: copy {crit['copy_score']}/10 · visual "
          f"{crit['visual_score']}/10 · "
          f"{'approved ✅' if crit['approved'] else 'not approved ⚠️'}\n\n")
    for c in result["copies"]:
        md += f"**{c['tagline']}**\n{c['ad_copy']}\n*{c['cta']}*\n\n---\n\n"
    md += "### Critique notes\n" + "\n".join(f"- {n}" for n in crit["notes"])
    md += f"\n\n### Campaign plan\n{result['campaign_plan']}"
    return md, gallery, " · ".join(f"{i+1}: {p}" for i, p in
                                   enumerate(gallery)) + "\n" + "\n".join(labels)


def do_download() -> list[str] | None:
    if not _LAST_BUNDLE or not os.path.isdir(_LAST_BUNDLE):
        return None
    return [os.path.join(_LAST_BUNDLE, f) for f in os.listdir(_LAST_BUNDLE)
            if f.endswith((".json", ".md"))]


def status_line() -> str:
    provider, model, key_present, reason = provider_status()
    llm = f"LLM: {provider}/{model} — live" if key_present else \
        f"LLM: offline ({reason}) — template copy + deterministic critic"
    return llm + " · images: Pollinations (free) → DALL-E → labelled placeholder"


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Creative Studio") as app:
        gr.Markdown("# 🎨 Multi-Agent Creative Studio\n"
                    "Brief → copywriter + visual designer → critic → campaign plan.")
        gr.Markdown(value=status_line())
        with gr.Row():
            product = gr.Textbox(label="Product",
                                 placeholder="e.g. Aura smart water bottle")
            audience = gr.Textbox(label="Audience",
                                  placeholder="e.g. urban fitness enthusiasts")
        description = gr.Textbox(
            label="Description", lines=3,
            placeholder="What is it and why does it matter?")
        with gr.Row():
            tone = gr.Dropdown(["friendly", "bold", "playful",
                                "professional", "luxury"],
                               value="friendly", label="Tone")
            variants = gr.Slider(1, 6, value=3, step=1, label="Copy variants")
        btn = gr.Button("Generate campaign", variant="primary")
        out = gr.Markdown()
        gallery = gr.Gallery(label="Visuals", columns=3)
        paths = gr.Markdown()
        dl_btn = gr.Button("Download bundle (JSON + Markdown)")
        dl = gr.Files()
        btn.click(do_run, [product, description, audience, tone, variants],
                  [out, gallery, paths])
        dl_btn.click(do_download, outputs=dl)
    return app


if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0",
                       server_port=int(os.environ.get("PORT", 7863)))
