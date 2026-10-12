"""
Runs only the dependency-free unit tests (currently tests/unit/test_rbac_core.py)
with nothing but the standard library — no pytest, no FastAPI, no Mongo
required. Useful for a quick sanity check in any environment, including one
with no network access. The full suite (tests/unit/test_security.py,
tests/unit/test_state_machine.py once Phase 2 adds it, and everything under
tests/integration/) requires `pip install -r requirements.txt` and should be
run with `pytest` instead — see TESTING_GUIDE.md.

Run with:  python3 scripts/run_offline_unit_tests.py
"""
import sys
import traceback

import tests.unit.test_rbac_core as rbac_core_tests

MODULES = [rbac_core_tests]


def main() -> int:
    total_passed = 0
    total_failed = 0

    for module in MODULES:
        test_names = [name for name in dir(module) if name.startswith("test_")]
        for name in test_names:
            try:
                getattr(module, name)()
                print(f"PASSED  {module.__name__}.{name}")
                total_passed += 1
            except Exception:
                print(f"FAILED  {module.__name__}.{name}")
                traceback.print_exc()
                total_failed += 1

    print(f"\n{total_passed} passed, {total_failed} failed out of {total_passed + total_failed}")
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
