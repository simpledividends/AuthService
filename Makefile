PROJECT := auth_service

VENV := .venv
COVERAGE := .coverage
BUILD := .build

export PATH := $(VENV)/bin:$(PATH)

MIGRATIONS := migrations
TESTS := tests

IMAGE_NAME := $(PROJECT)

.venv:
	poetry env use 3.8
	poetry check

.coverage:
	mkdir -p $(COVERAGE)

.build:
	mkdir -p $(BUILD)

clean:
	rm -rf .mypy_cache
	rm -rf .pytest_cache
	rm -rf $(COVERAGE)
	rm -rf $(VENV)
	rm -rf $(BUILD)

install: .venv
	poetry install

.pytest:
	pytest

test: .venv .pytest

cov: .coverage
	coverage run --source $(PROJECT) --module pytest
	coverage report
	coverage html -d $(COVERAGE)/html
	coverage xml -o $(COVERAGE)/cobertura.xml
	coverage erase

isort: .venv
	isort $(SERVICE) $(TESTS) $(MIGRATIONS)

mypy: .venv
	mypy $(PROJECT) $(TESTS)

bandit: .venv
	bandit -r $(PROJECT) $(TESTS) $(MIGRATIONS)

flake: .venv
	flake8 $(PROJECT) $(TESTS) $(MIGRATIONS)

pylint: .venv
	pylint $(PROJECT) $(TESTS) $(MIGRATIONS)

lint: isort flake bandit mypy pylint

build: .build
	docker build . -t $(IMAGE_NAME) --pull
	docker save -o $(BUILD)/$(IMAGE_NAME).tar $(IMAGE_NAME)

all: install lint cov build

.DEFAULT_GOAL = all
