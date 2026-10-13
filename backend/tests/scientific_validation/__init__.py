"""Scientific validation suite for Sprint 9 s9-2.

Sources: PowerLight, Xidian, Overview Energy, DARPA POWER, Han et al.
Each test module states its error bound in the assertion message.

Location note: the roadmap names this directory as ``tests/scientific_validation/``
at the repository root. It lives under ``backend/tests/`` because
``backend/pyproject.toml`` sets ``testpaths = ["tests"]`` relative to itself,
and both the ``backend`` CI job and ``tests/master_test.py`` invoke pytest
from ``backend/``. A suite at the repository root would not be collected.
The directory name matches the roadmap; only its parent differs.
"""
