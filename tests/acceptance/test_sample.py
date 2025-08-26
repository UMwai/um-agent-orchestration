from __future__ import annotations
import importlib.util, os, sys

def test_health_ok():
    # The agent should create backend/app.py with FastAPI app
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    backend_app = os.path.join(root, "backend", "app.py")
    assert os.path.exists(backend_app), "backend/app.py not created"

    # do a quick import
    spec = importlib.util.spec_from_file_location("backend_app", backend_app)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    sys.modules["backend_app"] = mod
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore

    app = getattr(mod, "app", None)
    assert app is not None, "FastAPI app not found"

    # naive check: file contains 'status":"ok'
    with open(backend_app, "r", encoding="utf-8") as f:
        src = f.read()
    assert '"status":"ok"' in src.replace(" ", "")