"""All benchmark tasks, in one list with one schema.

Fields of every task:
  id             short name, unique
  category       programming | repair | terminal | chain
  tier           easy | medium | hard | terminal
  kind           file (the agent writes or fixes one file) | terminal (the agent does a job in the folder)
  file           the file the agent must write or fix (for terminal tasks: the result the test looks at)
  what           one line that says what the task asks
  prompt         the task text given to the agent
  steps          (chains only) the list of prompts; each step runs as a fresh pi session in the same folder
  setup_files    files that are in the work folder before the agent starts {name: text}
  setup_cmd      bash that runs in the work folder before the agent starts ("" for none)
  tests          the hidden test: Python that runs in the work folder after the agent stops; it prints one line
                 that starts with FAIL for each problem
  solution_files the reference solution as files {name: text}   (used only by `kbench validate`)
  solution_cmd   the reference solution as bash                 (used only by `kbench validate`)
  requires       commands that the task or its test needs (for example node, git, nvidia-smi)
"""
from . import chains, programming, terminal

_FIELDS = ("id", "category", "tier", "kind", "file", "what", "prompt", "steps", "setup_files", "setup_cmd", "tests",
           "solution_files", "solution_cmd", "requires")


def _normal(t, what, requires):
    out = {
        "id": t["id"], "category": t["category"], "tier": t["tier"], "kind": t["kind"], "file": t["file"],
        "what": what[t["id"]], "prompt": t["prompt"], "steps": list(t.get("steps") or []),
        "setup_files": dict(t.get("setup_files") or {}), "setup_cmd": t.get("setup_cmd") or "",
        "tests": t["tests"], "solution_files": dict(t.get("solution_files") or {}),
        "solution_cmd": t.get("solution_cmd") or "", "requires": ["python3"] + list(requires.get(t["id"], [])),
    }
    if t["category"] == "chain":
        out["requires"] += [r for r in terminal.REQUIRES.get(t["base"], []) if r not in out["requires"]]
    return out


TASKS = ([_normal(t, programming.WHAT, programming.REQUIRES) for t in programming.TASKS] +
         [_normal(t, terminal.WHAT, terminal.REQUIRES) for t in terminal.TASKS] +
         [_normal(t, chains.WHAT, chains.REQUIRES) for t in chains.TASKS])
TASK = {t["id"]: t for t in TASKS}
TIERS = ["easy", "medium", "hard", "terminal"]
CATEGORIES = ["programming", "repair", "terminal", "chain"]

assert len(TASK) == len(TASKS), "duplicate task id"
for _t in TASKS:
    assert _t["tier"] in TIERS and _t["category"] in CATEGORIES, _t["id"]
    assert _t["solution_files"] or _t["solution_cmd"], "no reference solution: " + _t["id"]


def select(spec):
    """'all', a comma list of ids, or category/tier names (for example 'terminal,chain' or 'easy')."""
    if not spec or spec == "all":
        return [t["id"] for t in TASKS]
    out = []
    for part in [p.strip() for p in spec.split(",") if p.strip()]:
        if part in TASK:
            ids = [part]
        elif part in CATEGORIES:
            ids = [t["id"] for t in TASKS if t["category"] == part]
        elif part in TIERS:
            ids = [t["id"] for t in TASKS if t["tier"] == part]
        else:
            raise SystemExit("unknown task, category or tier: %s (see `kbench list`)" % part)
        out += [i for i in ids if i not in out]
    return out
