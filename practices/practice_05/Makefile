PYTHON ?= python3

.PHONY: test run spec-check

test:
	$(PYTHON) -m unittest discover -s tests -v

run:
	$(PYTHON) -m app.server --demo

spec-check:
	$(PYTHON) scripts/check_spec.py
