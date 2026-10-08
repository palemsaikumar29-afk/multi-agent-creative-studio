"""Regression tests for the grader-feedback rework (capstone-6).

Covers: model-based critic scoring with deterministic fallback, directed
rewrites (critic notes flow into the copywriter's next prompt), and the
placeholder-majority approval gate.
"""
import os

from src.agents import nodes
from src.services import images
from src.services.config import settings
from src.services.copywriter import _rewrite_prompt, write_copies


def _brief():
    return {"product": "Aura",
            "description": "A smart water bottle that tracks hydration.",
            "audience": "urban fitness enthusiasts",
            "tone": "bold",
            "variants": 3}


def _copies():
    return [{"tagline": "Aura: powers fitness life, beautifully.",
             "ad_copy": "Meet Aura — smart hydration tracking. Built for "
                        "urban fitness enthusiasts. Try it free today.",
             "cta": "Try it free today."}]


# --- placeholder-majority gate -------------------------------------------

def test_placeholder_majority_not_approved():
    visuals = [{"provider": "pollinations"},
               {"provider": "placeholder"},
               {"provider": "placeholder"}]
    score, notes = nodes.score_visuals(visuals)
    assert score < 7.0
    assert any("placeholder" in n.lower() for n in notes)
    assert any("2 of 3" in n for n in notes)


def test_placeholder_minority_can_still_pass():
    visuals = [{"provider": "pollinations"},
               {"provider": "pollinations"},
               {"provider": "placeholder"}]
    score, _ = nodes.score_visuals(visuals)
    assert score >= 7.0


def test_all_placeholder_still_flagged():
    score, notes = nodes.score_visuals([{"provider": "placeholder"}] * 3)
    assert score < 7.0
    assert any("placeholder" in n.lower() for n in notes)


def test_critique_node_rejects_placeholder_majority_campaign():
    state = {"brief": _brief(), "copies": _copies(), "round": 1,
             "visuals": [{"provider": "pollinations"},
                         {"provider": "placeholder"},
                         {"provider": "placeholder"}]}
    crit = nodes.critique_node(state)["critique"]
    assert crit["approved"] is False
    assert crit["visual_score"] < 7.0
    assert any("placeholder" in n.lower() for n in crit["notes"])


# --- directed rewrites ----------------------------------------------------

def test_rewrite_prompt_includes_critic_notes():
    notes = ["Variant 1 tagline is generic; tie it to hydration tracking.",
             "Variant 2 CTA is weak."]
    prompt = _rewrite_prompt("Aura", "desc", "runners", "bold", 2, notes)
    assert "DIRECTED REVISION" in prompt
    for n in notes:
        assert n in prompt


def test_rewrite_prompt_without_notes_has_no_critic_section():
    prompt = _rewrite_prompt("Aura", "desc", "runners", "bold", 2, None)
    assert "CRITIC NOTES" not in prompt
    prompt2 = _rewrite_prompt("Aura", "desc", "runners", "bold", 2, [])
    assert "CRITIC NOTES" not in prompt2


def test_copy_node_passes_critic_notes_to_writer(monkeypatch):
    captured = {}

    def fake_write(product, description, audience, tone, variants,
                   seed=7, revision_notes=None):
        captured["revision_notes"] = revision_notes
        return [{"tagline": "t", "ad_copy": "a", "cta": "c"}], True

    monkeypatch.setattr(nodes, "write_copies", fake_write)
    state = {"brief": _brief(), "round": 1,
             "critique": {"notes": ["Variant 1 tagline is generic."],
                          "copy_score": 6.0}}
    out = nodes.copy_node(state)
    assert captured["revision_notes"] == ["Variant 1 tagline is generic."]
    assert out["revision_notes"] == ["Variant 1 tagline is generic."]
    assert out["round"] == 2


def test_copy_node_first_round_passes_no_notes(monkeypatch):
    captured = {}

    def fake_write(product, description, audience, tone, variants,
                   seed=7, revision_notes=None):
        captured["revision_notes"] = revision_notes
        return [{"tagline": "t", "ad_copy": "a", "cta": "c"}], True

    monkeypatch.setattr(nodes, "write_copies", fake_write)
    out = nodes.copy_node({"brief": _brief(), "round": 0})
    assert captured["revision_notes"] is None
    assert out["round"] == 1


def test_write_copies_offline_ignores_notes_but_stays_honest():
    # No API key in this environment: template mode cannot act on notes,
    # so it must report offline=True rather than pretend otherwise.
    copies, offline = write_copies(
        "Aura", "a smart water bottle that tracks hydration well",
        "runners", "bold", 2, revision_notes=["make it punchier"])
    assert offline is True
    assert len(copies) == 2


# --- model-based critic scoring -------------------------------------------

def _key_present(monkeypatch):
    monkeypatch.setattr(nodes, "provider_status",
                        lambda: ("groq", "model", True, ""))


def test_model_critic_parses_score_and_notes(monkeypatch):
    _key_present(monkeypatch)
    canned = ("SCORE: 8.5\nNOTES:\n"
              "- Variant 1 tagline is generic; tie it to hydration tracking.\n"
              "- Variant 1 CTA is weak; use a stronger verb.\n")
    monkeypatch.setattr(nodes, "call_llm_with_retry", lambda prompt: canned)
    state = {"brief": _brief(), "copies": _copies(), "round": 1,
             "visuals": [{"provider": "pollinations"}]}
    crit = nodes.critique_node(state)["critique"]
    assert crit["copy_score"] == 8.5
    assert crit["critic_mode"] == "model"
    assert any("hydration tracking" in n for n in crit["notes"])


def test_model_critic_score_clamped_to_range():
    score, _ = nodes._parse_critic_response("SCORE: 12\nNOTES:\n- too high\n")
    assert score == 10.0


def test_model_critic_garbage_reply_falls_back(monkeypatch):
    _key_present(monkeypatch)
    monkeypatch.setattr(nodes, "call_llm_with_retry",
                        lambda prompt: "looks great, nice job!")
    state = {"brief": _brief(), "copies": _copies(), "round": 1,
             "visuals": [{"provider": "pollinations"}]}
    crit = nodes.critique_node(state)["critique"]
    # deterministic fallback: template copy scores 9.0 on these inputs
    assert crit["critic_mode"] == "deterministic"
    assert crit["copy_score"] == 9.0


def test_model_critic_llm_error_falls_back(monkeypatch):
    _key_present(monkeypatch)

    def boom(prompt):
        raise RuntimeError("network down")

    monkeypatch.setattr(nodes, "call_llm_with_retry", boom)
    state = {"brief": _brief(), "copies": _copies(), "round": 1,
             "visuals": [{"provider": "pollinations"}]}
    crit = nodes.critique_node(state)["critique"]
    assert crit["critic_mode"] == "deterministic"
    assert crit["copy_score"] == 9.0


def test_critic_offline_uses_deterministic_scorer():
    # No key configured in this environment.
    state = {"brief": _brief(), "copies": _copies(), "round": 1,
             "visuals": [{"provider": "pollinations"}]}
    crit = nodes.critique_node(state)["critique"]
    assert crit["critic_mode"] == "deterministic"
    det_score, _ = nodes.score_copy(_copies(), _brief())
    assert crit["copy_score"] == round(det_score, 1)


# --- end-to-end ------------------------------------------------------------

def test_e2e_placeholder_majority_never_approved_and_terminates(
        monkeypatch, tmp_path):
    from PIL import Image

    from src.graph.pipeline import run_studio

    monkeypatch.setattr(settings, "studio_output_dir",
                        str(tmp_path / "outputs"))
    calls = {"n": 0}

    def fake_generate(prompt, out_path, seed=7, width=1024, height=1024):
        calls["n"] += 1
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        Image.new("RGB", (8, 8)).save(out_path)
        # 1 real + 2 placeholders per visual round -> majority placeholder
        return "pollinations" if calls["n"] % 3 == 1 else "placeholder"

    monkeypatch.setattr(images, "generate_image", fake_generate)
    result = run_studio("Aura",
                        "A smart water bottle that tracks hydration and "
                        "glows as a reminder.",
                        "urban fitness enthusiasts", tone="bold", variants=3)
    crit = result["critique"]
    assert crit["approved"] is False
    assert any("placeholder" in n.lower() for n in crit["notes"])
    # revision loop must stay bounded even though visuals never improve
    assert result["round"] <= 3
    assert os.path.exists(
        os.path.join(result["bundle_dir"], "campaign_bundle.json"))


def test_e2e_offline_revision_loop_still_terminates(monkeypatch, tmp_path):
    from src.graph.pipeline import run_studio

    monkeypatch.setattr(settings, "image_provider", "placeholder")
    monkeypatch.setattr(settings, "studio_output_dir",
                        str(tmp_path / "outputs"))
    result = run_studio("Aura",
                        "A smart water bottle that tracks hydration and "
                        "glows as a reminder.",
                        "urban fitness enthusiasts", tone="bold", variants=2)
    assert result.get("blocked") is not True
    assert result["round"] <= 3  # bounded despite visual failures
    assert result["critique"]["approved"] is False  # honest: all placeholders
    assert result["critique"]["critic_mode"] == "deterministic"
    assert os.path.exists(result["bundle_dir"])
