.PHONY: install compile train test lint run up down demo clean

install:        ## Install the package with dev extras
	pip install -e ".[dev]"

compile:        ## Compile the Solidity contract -> contracts/artifacts
	python -m app.chain.compile

train:          ## Train the credit-risk model and register an artifact
	python -m app.ml.train

test:           ## Run the full test suite with coverage
	pytest --cov=app --cov-report=term-missing

lint:           ## Static checks
	ruff check app tests

run:            ## Run the API locally (needs a trained model; chain optional)
	uvicorn app.main:app --reload --port 8000

up:             ## Start the full stack (Postgres + Anvil + API)
	docker compose up --build

down:
	docker compose down -v

demo:           ## End-to-end: train, score an applicant, anchor, verify
	python -m scripts.demo

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov ml/artifacts/* credittrace.db
	touch ml/artifacts/.gitkeep
