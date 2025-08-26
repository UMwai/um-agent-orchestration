from __future__ import annotations
import os, importlib.util, sys

def test_drawdown_metrics():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    mod_path = os.path.join(root, "quant", "risk_utils.py")
    assert os.path.exists(mod_path), "quant/risk_utils.py not created"

    spec = importlib.util.spec_from_file_location("risk_utils", mod_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    sys.modules["risk_utils"] = mod
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore

    series = [100, 102, 99, 97, 105, 101]
    dd = mod.max_drawdown(series)                 # type: ignore[attr-defined]
    assert isinstance(dd, float)