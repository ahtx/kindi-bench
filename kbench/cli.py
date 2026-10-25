"""Command line: python3 -m kbench <command> ...   (or `kbench <command>` after `pip install .`)"""
import argparse
import json
import os
import sys

from . import __version__
from .tasks import TASK, select

DEFAULT_URL = "http://127.0.0.1:8093/v1"


def cmd_list(a):
    ids = select(a.tasks)
    if a.markdown:
        print("| id | category | tier | what |")
        print("|---|---|---|---|")
        for i in ids:
            t = TASK[i]
            print("| `%s` | `%s` | `%s` | %s |" % (i, t["category"], t["tier"], t["what"].replace("|", "\\|")))
    else:
        for i in ids:
            t = TASK[i]
            print("%-20s %-11s %-8s %s" % (i, t["category"], t["tier"], t["what"]))
        print("%d tasks" % len(ids))
    return 0


def cmd_show(a):
    t = TASK.get(a.task)
    if not t:
        raise SystemExit("unknown task %s" % a.task)
    keys = ["id", "category", "tier", "kind", "file", "what", "prompt", "steps", "requires"]
    if a.all:
        keys += ["setup_files", "setup_cmd", "tests", "solution_files", "solution_cmd"]
    print(json.dumps({k: t[k] for k in keys}, indent=1))
    return 0


def cmd_run(a):
    from .runner import Run
    a.tasks_list = select(a.tasks)
    Run(a).run()
    return 0


def cmd_report(a):
    from .report import report
    report(a.runs, a.runid)
    return 0


def cmd_collect(a):
    from .report import collect
    json.dump(collect(a.runs, a.runids), sys.stdout, indent=1)
    print()
    return 0


def cmd_validate(a):
    from . import validate
    if not sys.platform.startswith("linux"):
        print("warning: the tasks are written for Linux (bash, GNU find/sed/df)", file=sys.stderr)
    return validate.main(select(a.tasks), a.strict)


def cmd_textjobs(a):
    from . import textjobs
    textjobs.main(a.url, a.out, a.model, a.parallel, a.only, a.limit)
    return 0


def cmd_breakdown(a):
    from . import breakdown
    breakdown.main(a.url, a.out, a.model, a.agent_runs, a.api_runs, a.only, a.pi, a.work, a.timeout, a.prompts)
    return 0


def cmd_speed(a):
    from .speed import speed
    speed(a)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kbench", description="kbench %s - agent benchmark for small models with the "
                                 "pi coding agent and an OpenAI-compatible server" % __version__)
    ap.add_argument("--version", action="version", version="kbench " + __version__)
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True

    p = sub.add_parser("list", help="list the tasks")
    p.add_argument("--tasks", default="all", help="ids, categories or tiers, comma-separated (default: all)")
    p.add_argument("--markdown", action="store_true", help="print a Markdown table")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("show", help="print one task")
    p.add_argument("task")
    p.add_argument("--all", action="store_true", help="also print the setup, the hidden test and the solution")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("run", help="run the agent on the tasks and grade the results")
    p.add_argument("runid")
    p.add_argument("--url", default=DEFAULT_URL, help="OpenAI-compatible base URL (default %s)" % DEFAULT_URL)
    p.add_argument("--model", required=True, help="the model id that the server expects (see URL/models)")
    p.add_argument("--conds", default="", help="conditions, comma-separated: base, think, base8k, ext, ext_think "
                   "(default: base,think,base8k; with --extension also ext,ext_think)")
    p.add_argument("--tasks", default="all", help="ids, categories or tiers, comma-separated (default: all)")
    p.add_argument("--seeds", type=int, default=3, help="runs per task and condition (default 3)")
    p.add_argument("--workers", type=int, default=1, help="agents in parallel (default 1; Kindi serves one request "
                   "at a time)")
    p.add_argument("--timeout", type=int, default=600, help="seconds for each pi session (default 600)")
    p.add_argument("--thinking", choices=["off", "minimal", "low", "medium", "high"],
                   help="override the thinking level of every condition")
    p.add_argument("--max-tokens", type=int, help="override the output cap per reply of every condition")
    p.add_argument("--context", type=int, default=24576, help="context window that pi assumes (default 24576)")
    p.add_argument("--request-timeout", type=int, default=1800, help="seconds that pi waits for one reply")
    p.add_argument("--extension", help="a pi extension (file or folder) for the ext and ext_think conditions")
    p.add_argument("--pi", help="path of the pi binary (default: pi in PATH)")
    p.add_argument("--work", default="~/kbench-work", help="parent folder of the agent work folders, outside this "
                   "repository (default ~/kbench-work)")
    p.add_argument("--runs", default="runs", help="where the records go (default ./runs)")
    p.add_argument("--keep-work", action="store_true", help="keep the work folders after the run")
    p.add_argument("--rss-limit-gb", type=float, default=2.0, help="kill a process past this resident memory")
    p.add_argument("--max-procs", type=int, default=200, help="kill a session that has more processes than this")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("report", help="print a summary table of one run")
    p.add_argument("runid")
    p.add_argument("--runs", default="runs")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("collect", help="print a JSON summary of one or more runs")
    p.add_argument("runids", nargs="+")
    p.add_argument("--runs", default="runs")
    p.set_defaults(fn=cmd_collect)

    p = sub.add_parser("validate", help="prove the hidden tests: fail on the untouched folder, pass on the solution")
    p.add_argument("--tasks", default="all")
    p.add_argument("--strict", action="store_true", help="exit with an error when a task is skipped")
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("textjobs", help="short text jobs through the chat API")
    p.add_argument("out", help="output JSON file")
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--model", help="model id to send (optional for Kindi and llama.cpp)")
    p.add_argument("--parallel", type=int, default=1)
    p.add_argument("--only", default="", help="jobs, comma-separated: sentiment, escalate, spam, topic, spell, "
                   "grammar, table, notes, news")
    p.add_argument("--limit", type=int, default=0, help="at most this many items per job")
    p.set_defaults(fn=cmd_textjobs)

    p = sub.add_parser("breakdown", help="mixed jobs done three ways: agent, one prompt, and one item per call")
    p.add_argument("out", help="output JSON file")
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--model", help="model id (required for the agent mode)")
    p.add_argument("--agent-runs", type=int, default=3)
    p.add_argument("--api-runs", type=int, default=3)
    p.add_argument("--only", default="", help="jobs, comma-separated: tally, spam, urgent, topic, orders")
    p.add_argument("--pi", help="path of the pi binary (default: pi in PATH)")
    p.add_argument("--work", default="~/kbench-work", help="parent folder of the agent work folders")
    p.add_argument("--timeout", type=int, default=900, help="seconds for each agent session")
    p.add_argument("--prompts", choices=["tested", "first"], default="tested",
                   help="per-item prompts: tested (default) or the first ones, which failed on spam and orders")
    p.set_defaults(fn=cmd_breakdown)

    p = sub.add_parser("speed", help="read (prefill) and write (decode) throughput of an OpenAI-compatible server")
    p.add_argument("--url", default=DEFAULT_URL, help="OpenAI-compatible base URL (default %s)" % DEFAULT_URL)
    p.add_argument("--model", default=None, help="model id (default: first of GET /models)")
    p.add_argument("--sizes", default="128,512,2048", help="prompt sizes in words, comma-separated")
    p.add_argument("--gen", type=int, default=128, help="tokens to generate per call")
    p.add_argument("--repeat", type=int, default=1, help="repeat each size and average")
    p.add_argument("--timeout", type=float, default=600)
    p.add_argument("--save", action="store_true", help="write results/speed-*.json")
    p.set_defaults(fn=cmd_speed)

    a = ap.parse_args(argv)
    if getattr(a, "runs", None):
        a.runs = os.path.abspath(a.runs)
    return a.fn(a)
