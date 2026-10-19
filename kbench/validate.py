"""kbench validate: prove every hidden test.

For each task, in a fresh temporary folder:
  1. set up the folder as the agent gets it, and run the hidden test: it must FAIL;
  2. apply the reference solution, and run the hidden test again: it must PASS (no output, exit status 0).
A task whose required command (for example node or nvidia-smi) is missing is reported as SKIP."""
import os
import shutil
import subprocess
import tempfile

from . import sandbox
from .tasks import TASK


def apply_solution(t, wd):
    for name, content in t["solution_files"].items():
        p = os.path.join(wd, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(content)
    if t["solution_cmd"]:
        subprocess.run(["bash", "-c", t["solution_cmd"]], cwd=wd, check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def check(t):
    """-> (status, detail) with status OK, BROKEN or SKIP."""
    missing = [r for r in t["requires"] if not shutil.which(r)]
    if missing:
        return "SKIP", "needs " + ", ".join(missing)
    wd = tempfile.mkdtemp(prefix="kbench-validate-")
    try:
        sandbox.prepare(t, wd)
        out0, rc0 = sandbox.run_tests(t["tests"], wd)
        untouched_fails = bool(out0.strip()) or rc0 != 0
        apply_solution(t, wd)
        out1, rc1 = sandbox.run_tests(t["tests"], wd)
        solved_passes = not out1.strip() and rc1 == 0
    except subprocess.CalledProcessError as e:
        return "BROKEN", "setup or solution command failed: %s" % e
    finally:
        sandbox.sweep(wd)
        shutil.rmtree(wd, ignore_errors=True)
    if untouched_fails and solved_passes:
        return "OK", ""
    detail = []
    if not untouched_fails:
        detail.append("the test PASSES on the untouched folder")
    if not solved_passes:
        detail.append("the test fails on the reference solution: %r (exit %s)" % (out1.strip()[:300], rc1))
    return "BROKEN", "; ".join(detail)


def main(ids, strict=False):
    counts = {"OK": 0, "BROKEN": 0, "SKIP": 0}
    for tid in ids:
        t = TASK[tid]
        status, detail = check(t)
        counts[status] += 1
        print("%-20s %-11s %-8s %-6s %s" % (tid, t["category"], t["tier"], status, detail), flush=True)
    print("tasks %d: %d OK, %d BROKEN, %d SKIP" % (len(ids), counts["OK"], counts["BROKEN"], counts["SKIP"]))
    return 1 if counts["BROKEN"] or (strict and counts["SKIP"]) else 0
