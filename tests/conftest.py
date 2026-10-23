"""conftest.py -- make src/ and the repository root importable for the suite.

The simulation spine (sglsim.py, expcommon.py) uses flat imports
(``import sglsim as S``), so ``src/`` must be on sys.path.  The top-level
reproduction entry point lives at the repository root, so ``ROOT`` goes on the
path too -- ``python3 -m reproduce_all`` is a documented, tested command.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
