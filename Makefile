.PHONY: fmt lint test unit integration regression golden compatibility playground build release-check

fmt:
	python3 scripts/test_platform.py fmt

lint:
	python3 scripts/test_platform.py lint

test:
	python3 scripts/test_platform.py test

unit:
	python3 scripts/test_platform.py unit

integration:
	python3 scripts/test_platform.py integration

regression:
	python3 scripts/test_platform.py regression

golden:
	python3 scripts/test_platform.py golden

compatibility:
	python3 scripts/test_platform.py compatibility

playground:
	python3 scripts/test_platform.py playground

build:
	python3 scripts/test_platform.py build

release-check:
	python3 scripts/test_platform.py release-check
