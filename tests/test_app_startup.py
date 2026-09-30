"""App startup smoke test (excluded from default `make test`)."""
import app


def test_build_app():
    assert app.build_app() is not None
