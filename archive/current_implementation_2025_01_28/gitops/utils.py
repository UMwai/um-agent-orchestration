from __future__ import annotations

import os
import re
import subprocess


def apply_patchlike_text(workdir: str, text: str) -> None:
    """
    Accepts either unified diffs or a simple annotated format:

    === file:path ===
    ```lang
    ...content...
    ```
    """
    # naive approach: detect unified diff markers first
    if re.search(r"^diff --git a/", text, flags=re.M):
        _apply_unified_diff(workdir, text)
        return
    # otherwise parse blocks
    blocks = re.split(r"^===\s*file:(.+?)\s*===\s*$", text, flags=re.M)
    if len(blocks) <= 1:
        # nothing to do
        return
    for i in range(1, len(blocks), 2):
        if i + 1 >= len(blocks):
            break
        path = blocks[i].strip()
        content = blocks[i + 1]
        # strip fences if present
        m = re.search(r"```.*?\n(.*?)```", content, flags=re.S)
        body = m.group(1) if m else content
        abs_path = os.path.join(workdir, path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(body)


def _apply_unified_diff(workdir: str, diff_text: str) -> None:
    p = subprocess.Popen(
        ["git", "apply", "-p0", "--whitespace=fix"], cwd=workdir, stdin=subprocess.PIPE
    )
    p.communicate(input=diff_text.encode("utf-8"))
    if p.returncode != 0:
        raise RuntimeError("git apply failed")


def run_checks_and_tests(workdir: str) -> dict:
    logs = []
    # ruff
    r1 = subprocess.run(["ruff", "check", "."], cwd=workdir, capture_output=True, text=True)
    logs.append(r1.stdout + "\n" + r1.stderr)
    # mypy
    r2 = subprocess.run(["mypy", "."], cwd=workdir, capture_output=True, text=True)
    logs.append(r2.stdout + "\n" + r2.stderr)
    # pytest
    r3 = subprocess.run(["pytest", "-q"], cwd=workdir, capture_output=True, text=True)
    logs.append(r3.stdout + "\n" + r3.stderr)
    status = (
        "pass" if (r1.returncode == 0 and r2.returncode == 0 and r3.returncode == 0) else "fail"
    )
    return {"status": status, "combined": "\n\n".join(logs)}
