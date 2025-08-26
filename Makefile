# Makefile for SpongeKit v1.0


# ===== User-tunable variables (safe defaults) =====
PYTHON := python3
PIP := $(PYTHON) -m pip

# ===== Convenience targets =====

.PHONY: install
install: ## Install runtime dependencies from requirements.txt
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

.PHONY: dev
dev: ## Install dev tools (formatters, pytest) in addition to runtime deps
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt
	$(PIP) install pytest black isort mypy

.PHONY: run-app
run-app: ## Launch the Streamlit app
	streamlit run app.py

.PHONY: test
test: ## Run unit tests quietly
	pytest -q

.PHONY: fmt
fmt: ## Auto-format code with black + isort
	black .
	isort .

.PHONY: lint
lint: ## Type-check core package (non-fatal)
	-mypy spongekit_core

.PHONY: build
build: ## Build the package (wheel + sdist)
	$(PIP) install --upgrade build
	$(PYTHON) -m build

.PHONY: clean
clean: ## Remove build/coverage caches
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache htmlcov .coverage

# Show help if you just type `make`
.DEFAULT_GOAL := help
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' Makefile | sed 's/:.*## /: /' | sort
