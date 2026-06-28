# Playground Repository Stabilization Audit

Specification: `repository-stabilization/1.0`

Status: Draft

| Feature | Expected | Status |
| --- | --- | --- |
| Test collection | `python -m pytest --collect-only` has no errors | PASS |
| Full pytest execution | `python -m pytest -q` passes | PASS |
| Dependency management | `requirements-dev.txt` present | PASS |
| Import normalization | `pytest.ini` fixes package root and import mode | PASS |
| Repository layout | Required directories and files present | PASS |
| CI determinism | Workflows install shared dev requirements | PASS |
| Regression verification | Language Surface v0.5 compatibility preserved | PASS |
| Documentation consistency | Specs, audit, and matrix IDs consistent | PASS |
| Frozen component policy | Language semantics and IR schemas unchanged by RS-001 | PASS |
