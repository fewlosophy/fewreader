.PHONY: install dev test build-css

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

dev:
	uvicorn app.main:app --reload --port 8000

test:
	pytest tests/

build-css:
	npm run build:css
