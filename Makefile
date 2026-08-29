.PHONY: fmt lint test unit integration regression golden compatibility playground build release-check tensor-manifest tensor-manifest-check benchmark-tensor benchmark-relation-matrix

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

tensor-manifest:
	./reason tensor-manifest --json --out docs/reports

tensor-manifest-check:
	./reason tensor-manifest --check

benchmark-tensor:
	python3 scripts/benchmark_tensor.py

benchmark-relation-matrix:
	python3 scripts/benchmark_relation_matrix.py --check
