# Multi-Agent Creative Studio

Capstone Agent 6 (Interview Kickstart Applied Agentic AI). A team of
specialist agents turns a short product brief into a campaign bundle:
copywriter writes ad-copy variants, visual designer generates hero
imagery, a critic scores both and can demand revisions, and a
strategist wraps it in a launch plan.

## Pipeline

```
brief
  │
  ▼  (injection detection + PII redaction; thin or hostile briefs blocked)
┌─ copywriter ── taglines + ad copy + CTAs
├─ visual designer ── hero images per variant
├─ critic ── scores copy & visuals 0-10; approved >= 7.0
│    └─ revision loop: copy re-generated with a new seed, up to 2 rounds
├─ strategist ── 5-channel launch plan
└─ bundle ── campaign_bundle.json + campaign.md (+ images) in outputs/<run>
```

Agents are LLM-backed when an API key is configured; without one the
pipeline runs in clearly-labelled offline mode (deterministic template
copy + deterministic critic scoring), so every run is testable.

## Image provider chain

`IMAGE_PROVIDER` controls image generation:

- `auto` (default): **Pollinations.ai → DALL-E → labelled placeholder**
- `pollinations`: free, no key or signup (generations marked private)
- `dalle`: needs `LLM_PROVIDER=openai` with a key that has image access
- `placeholder`: clearly-labelled placeholders for offline runs

Every asset records the provider actually used, so a placeholder is never
presented as a generation. Honest caveat: Pollinations stamps a small logo
watermark (removal needs a free account).

## Quickstart

```bash
make install          # create .venv and install pinned requirements
cp .env.example .env  # fill in at least one LLM API key (optional)
make test             # 12 unit + e2e tests (no network, no keys needed)
make lint             # ruff
make run              # launch the Gradio app on 127.0.0.1:7863
```

Or run headless:

```python
from src.graph.pipeline import run_studio
result = run_studio("Aura",
    "A smart water bottle that tracks hydration and glows as a reminder.",
    "urban fitness enthusiasts", tone="bold", variants=3)
print(result["bundle_dir"])   # outputs/20260930-.../campaign.md + images
```

## LLM providers

One env var switches providers — OpenAI, Gemini 2.0 Flash, or Groq
`openai/gpt-oss-20b`. Provider, model, key, and timeout all come from the
environment (see `.env.example`); nothing is hardcoded. Retries use
exponential backoff (3 attempts).

## Test evidence

- `make test`: **12 passed** — brief blocking (too thin, injection, PII
  redaction), template copy variant count + uniqueness, deterministic
  critic scoring, placeholder labelling, provider-chain fallback to
  placeholder, e2e studio runs (offline), revision-loop termination,
  bundle file export.
- `make test-all` additionally runs live Pollinations generation checks
  (opt-in, skipped by default) and a Gradio app startup smoke test.
- `make lint`: ruff clean.

## Honest limits

- In offline mode the copy is template-generated and images are labelled
  placeholders — the pipeline shape, critic loop, and bundle export are
  what is verified; real creative quality needs the LLM + image providers.
- Built from the published capstone brief for this project; the UpLevel
  portal spec was not re-fetched during this build.
