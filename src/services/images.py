"""Image generation with an honest provider chain.

Chain: pollinations (free, no key) -> dalle (OpenAI key with image access)
-> labelled placeholder. The provider used for every asset is recorded on
the asset itself, so nothing is ever presented as something it is not.
"""
from __future__ import annotations

import hashlib
import io
import os
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw

from ..services.config import settings
from ..services.llm_factory import provider_status

POLLINATIONS_ENDPOINT = "https://image.pollinations.ai/prompt/{prompt}"
TIMEOUT_S = 45


def _pollinations(prompt: str, seed: int, width: int = 1024,
                  height: int = 1024) -> bytes:
    params = urllib.parse.urlencode({
        "model": settings.pollinations_model,
        "width": width, "height": height,
        "seed": seed, "nologo": "false",
        "private": "true", "safe": "true",
    })
    url = POLLINATIONS_ENDPOINT.format(
        prompt=urllib.parse.quote(prompt)) + "?" + params
    # sandbox proxy quirk: bypass the broken default no_proxy
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers={"User-Agent": "muse-studio/1.0"})
    with opener.open(req, timeout=TIMEOUT_S) as resp:
        data = resp.read()
    if not data or len(data) < 1024:
        raise RuntimeError("pollinations returned an empty/short payload")
    # sanity: must be decodable as an image
    Image.open(io.BytesIO(data)).verify()
    return data


def _dalle(prompt: str) -> bytes:
    provider, _, key_present, _ = provider_status()
    if provider != "openai" or not key_present:
        raise RuntimeError("DALL-E needs LLM_PROVIDER=openai with a key")
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    gen = client.images.generate(
        model=settings.openai_image_model,
        prompt=prompt, size="1024x1024", n=1,
    )
    img_url = gen.data[0].url
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(urllib.request.Request(img_url), timeout=TIMEOUT_S) as r:
        return r.read()


def placeholder_image(prompt: str, seed: int, out_path: str,
                      width: int = 1024, height: int = 1024) -> str:
    """Clearly-labelled placeholder so offline runs stay honest."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    digest = hashlib.md5(f"{prompt}:{seed}".encode()).digest()
    bg = (digest[0], digest[1], digest[2])
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    words = (prompt[:90] + "…") if len(prompt) > 90 else prompt
    draw.text((40, height // 2 - 20),
              f"PLACEHOLDER IMAGE\n\n{words}\n\n(no image provider available)",
              fill=(255, 255, 255))
    img.save(out_path)
    return out_path


def generate_image(prompt: str, out_path: str, seed: int = 7,
                   width: int = 1024, height: int = 1024) -> str:
    """Generate an image; return the provider name used.

    Respects IMAGE_PROVIDER (auto | pollinations | dalle | placeholder).
    """
    choice = settings.image_provider
    chain = ["placeholder"] if choice == "placeholder" else (
        ["pollinations"] if choice == "pollinations" else
        ["dalle"] if choice == "dalle" else
        ["pollinations", "dalle", "placeholder"]
    )
    last_err: Exception | None = None
    for provider in chain:
        try:
            if provider == "pollinations":
                data = _pollinations(prompt, seed, width, height)
            elif provider == "dalle":
                data = _dalle(prompt)
            else:
                placeholder_image(prompt, seed, out_path, width, height)
                return "placeholder"
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(data)
            return provider
        except Exception as exc:  # noqa: BLE001 - try next provider
            last_err = exc
    raise RuntimeError(f"all image providers failed: {last_err}")
