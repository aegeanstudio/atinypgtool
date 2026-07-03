.PHONY: compile-deps install-deps clean lint format dist

install-deps:
	@echo "Installing dependencies..."
	@uv sync --all-extras

compile-deps:
	@echo "Compiling dependencies..."
	@uv lock --upgrade
	@uv pip compile pyproject.toml --universal --upgrade --output-file=requirements.txt
	@make install-deps

clean:
	@rm -f dist/*
	@find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
	@find . -type d -name '__pycache__' -delete
	@find . -type d -empty -delete
	@rm -rf dist
	@rm -rf *.egg-info
	@rm -f .coverage
	@rm -f coverage.xml
	@rm -rf htmlcov

lint:
	@uv run ruff check --output-format=concise atinypgtool
	@uv run ty check

format:		# ruff format 命令需要执行两次，第一次会修复大部分问题，但可能会引入一些新的问题（折行场景最为常见），第二次执行可以修复这些新问题。
	@uv run ruff format
	@uv run ruff check --fix
	@uv run ruff format
	@uv run ruff check --fix

dist:
	@echo "Building distribution..."
	@uv build
