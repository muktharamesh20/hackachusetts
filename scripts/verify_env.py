"""Import-check the heavy robotics dependencies and print versions.

Run with: `python scripts/verify_env.py` (or `make verify`).
Exits non-zero if a required package is missing so CI can gate on it.
"""

from __future__ import annotations

import importlib
import sys

CHECKS = [
    ("numpy", "numpy"),
    ("pydantic", "pydantic"),
    ("drake (pydrake)", "pydrake"),
    ("lerobot", "lerobot"),
]


def main() -> int:
    ok = True
    print(f"Python: {sys.version.split()[0]}")
    for label, module in CHECKS:
        try:
            mod = importlib.import_module(module)
            version = getattr(mod, "__version__", "unknown")
            print(f"  ✓ {label:<18} {version}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"  ✗ {label:<18} NOT importable: {exc}")

    # Always confirm the project package imports.
    try:
        import pantrysort

        print(f"  ✓ {'pantrysort':<18} {pantrysort.__version__}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"  ✗ {'pantrysort':<18} NOT importable: {exc}")

    print("\nEnvironment OK." if ok else "\nEnvironment INCOMPLETE — see failures above.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
