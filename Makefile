.PHONY: install test test-all lint format run seed clean

install:
	python -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

seed:
	.venv/bin/python -m src.database.db --seed

test:
	.venv/bin/python -m pytest tests/ -p no:cacheprovider -q \
		--ignore=tests/test_live_llm.py --ignore=tests/test_app_startup.py

test-all: test
	.venv/bin/python -m pytest tests/test_live_llm.py tests/test_app_startup.py \
		-p no:cacheprovider -q

lint:
	.venv/bin/python -m ruff check src tests app.py

format:
	.venv/bin/python -m ruff format src tests app.py

run:
	.venv/bin/python app.py

clean:
	rm -rf .pytest_cache .ruff_cache
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
