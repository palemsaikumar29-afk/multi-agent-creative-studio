"""Live tests — require API keys / network; excluded from default `make test`."""
import pytest

from src.services import images

needs_net = pytest.mark.skipif(True, reason="live image/API tests are opt-in")


@needs_net
def test_pollinations_live():
    images.settings.image_provider = "pollinations"
    provider = images.generate_image("a red bicycle on a beach at sunset",
                                     "outputs-test/live.png", seed=42)
    assert provider == "pollinations"
