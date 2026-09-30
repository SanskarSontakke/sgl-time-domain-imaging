# src/v2_superseded/

Code from the pre-revision (v2) pipeline, kept for the audit trail and no longer runnable
against `src/sglsim.py`:

- `cad_solve_one.py` was the v2 one-method-per-process cadence worker. It refers
  to `run_experiments.CADENCE`, `TMP`, `CAD_FC`, `campaign()`, `get_F()`, `get_LtL()`
  and `KW_B2`, none of which exist in the revised driver (the cadence study is now
  `run_experiments.py cadence <arm> <i_cfg>`, and the campaign signature, resource
  arms and covariance handling all changed). It is preserved here rather than
  deleted so that the v2 cadence numbers can still be traced to the code that made
  them.

The demo "Source Code" viewer (`components/CodeViewer.tsx`) shows only live files;
this one is no longer embedded (see `src/make_app_code.py`).
