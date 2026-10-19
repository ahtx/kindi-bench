"""kbench run: the pi coding agent does each task in a fresh work folder; the hidden test then grades the folder.

Record of each run (under --runs, default ./runs):
  runs/RUNID/manifest.json                       versions, settings, server /health and /v1/models
  runs/RUNID/pi-agent/                           the generated pi config (models.json, settings.json, SYSTEM.md)
  runs/RUNID/watchdog.log                        every process that the watchdog or the sweep killed
  runs/RUNID/<cond>/<task>/s<k>/events.jsonl     pi's JSON event stream (the full transcript)
  runs/RUNID/<cond>/<task>/s<k>/tests.txt        the hidden test's output
  runs/RUNID/<cond>/<task>/s<k>/result.json      outcome, time, turns, tokens, tool use
  runs/RUNID/<cond>/<task>/s<k>/workdir/         the agent's final files (caches and files over 10 MB left out)
The agents work in --work/RUNID (default ~/kbench-work/RUNID), outside this tree, so they cannot find the hidden
tests. A run that already has result.json is skipped, so the same command continues a stopped run."""
import hashlib
import json
import os
import platform
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import Counter

from . import __version__, piconfig, sandbox, server
from .tasks import TASK

PKG = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(PKG)

CONDS = {
    # name: output cap per reply, pi thinking level, load the --extension
    "base":      {"max_tokens": 2048, "thinking": "off",    "ext": False},
    "think":     {"max_tokens": 4096, "thinking": "medium", "ext": False},
    "base8k":    {"max_tokens": 8192, "thinking": "off",    "ext": False},
    "ext":       {"max_tokens": 8192, "thinking": "off",    "ext": True},
    "ext_think": {"max_tokens": 8192, "thinking": "medium", "ext": True},
}
DEFAULT_CONDS = ["base", "think", "base8k"]
MAX_REQUEUE = 5


class InfraError(Exception):
    pass


def find_pi(path=None):
    p = path or shutil.which("pi")
    if not p or not os.path.exists(p):
        raise SystemExit("pi not found: install it with `npm install -g @earendil-works/pi-coding-agent` or pass --pi")
    return os.path.abspath(p)


def pi_env(pi, agent_dir, extra=None):
    """pi's environment: its own bin folder first in PATH (an nvm install has node next to pi)."""
    env = dict(os.environ, PI_CODING_AGENT_DIR=agent_dir, PI_OFFLINE="1")
    env["PATH"] = os.path.dirname(pi) + os.pathsep + env.get("PATH", "")
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid())
    env.update(extra or {})
    return env


def prompt_for(t, wd, text=None):
    text = t["prompt"] if text is None else text
    if t["kind"] == "terminal":
        return "Your working folder is %s. Do the task in this folder.\n\n%s" % (wd, text)
    target = os.path.join(wd, t["file"])
    if t["setup_files"]:
        return "Your working folder is %s. The file to fix is %s\n\n%s Run it to check it before you finish." % (
            wd, target, text)
    return ("Your working folder is %s. Write the file at exactly this path: %s\n\n%s Run it on the examples to check "
            "it before you finish." % (wd, target, text))


def classify(fails):
    if not fails:
        return "pass"
    j = " ".join(fails)
    if "does not exist" in j:
        return "nofile"
    if "timeout" in j:
        return "timeout"
    if "crashed" in j:
        return "crash"
    return "wrong"


def transcript_stats(events_path, wd, peek_re):
    s = Counter()
    last_stop = None
    outside = []
    with open(events_path, errors="replace") as ev:
        for line in ev:
            if len(line) > 5_000_000:                   # a tool result with runaway output: skip, do not parse
                s["huge_event_lines"] += 1
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") != "message_end":
                continue
            m = e.get("message") or {}
            if m.get("role") == "assistant":
                s["turns"] += 1
                last_stop = m.get("stopReason")
                s["stop_" + str(last_stop)] += 1
                s["output_tokens"] += (m.get("usage") or {}).get("output") or 0
                for c in m.get("content") or []:
                    if c.get("type") == "toolCall":
                        s["tool_" + str(c.get("name"))] += 1
                        args = c.get("arguments") or {}
                        if peek_re.search(json.dumps(args)):
                            s["peeked_at_bench"] += 1
                        p = args.get("path") if isinstance(args, dict) else None
                        if isinstance(p, str) and c.get("name") in ("write", "edit"):
                            ap = os.path.normpath(os.path.join(wd, os.path.expanduser(p.split("\n")[0])))
                            if not sandbox.under(ap, wd):
                                outside.append(ap)
                    elif c.get("type") == "thinking":
                        s["thinking_chars"] += len(c.get("thinking") or "")
            elif m.get("role") == "toolResult" and m.get("isError"):
                s["tool_errors"] += 1
    return dict(s), last_stop, sorted(set(outside))


class Run:
    def __init__(self, a):
        if not sys.platform.startswith("linux"):
            raise SystemExit("kbench run needs Linux (the safety watchdog reads /proc)")
        self.a = a
        self.runid = a.runid
        self.url = server.base(a.url)
        self.model = a.model
        self.runs = os.path.abspath(os.path.join(a.runs, a.runid))
        self.work = os.path.realpath(os.path.join(os.path.expanduser(a.work), a.runid))
        for inside in (REPO, os.path.abspath(a.runs)):
            if sandbox.under(self.work, os.path.realpath(inside)):
                raise SystemExit("--work must be outside %s: the agents must not find the hidden tests" % inside)
        self.pi = find_pi(a.pi)
        self.ext = os.path.abspath(a.extension) if a.extension else None
        names = [c for c in (a.conds.split(",") if a.conds else DEFAULT_CONDS + (["ext", "ext_think"] if self.ext else []))
                 if c]
        self.conds = {}
        for n in names:
            if n not in CONDS:
                raise SystemExit("unknown condition %s (known: %s)" % (n, ", ".join(CONDS)))
            c = dict(CONDS[n])
            if c["ext"] and not self.ext:
                raise SystemExit("condition %s needs --extension PATH" % n)
            if a.thinking:
                c["thinking"] = a.thinking
            if a.max_tokens:
                c["max_tokens"] = a.max_tokens
            self.conds[n] = c
        self.tasks = a.tasks_list
        self.seeds = a.seeds
        self.agent_dir = os.path.join(self.runs, "pi-agent")
        self.peek = re.compile("|".join(re.escape(p) for p in (PKG, os.path.realpath(PKG), self.runs,
                                                                os.path.abspath(a.runs))) + r"|kbench/tasks")
        self.watchdog = None
        self.requeues = Counter()

    # ------------------------------------------------------------------ one job
    def run_one(self, job):
        cond, tid, k = job
        t, c = TASK[tid], self.conds[cond]
        rdir = os.path.join(self.runs, cond, tid, "s%d" % k)
        if os.path.exists(os.path.join(rdir, "result.json")):
            return None
        wd = os.path.join(self.work, cond, tid, "s%d" % k)
        shutil.rmtree(wd, ignore_errors=True)
        shutil.rmtree(rdir, ignore_errors=True)
        os.makedirs(wd)
        os.makedirs(rdir)
        sandbox.prepare(t, wd)
        ext_log = os.path.join(rdir, "extension.jsonl")
        # older extensions read PI_GUARD_LOG; new ones can read KBENCH_EXTENSION_LOG
        env = pi_env(self.pi, self.agent_dir, {"KBENCH_EXTENSION_LOG": ext_log, "PI_GUARD_LOG": ext_log})
        cmd = [self.pi, "-p", "--no-session", "--mode", "json", "--provider", piconfig.provider_name(cond),
               "--model", self.model, "--thinking", c["thinking"]]
        if c["ext"]:
            cmd += ["-e", self.ext]
        # a task with steps runs as a chain: one fresh pi session per step, all in the same work folder
        prompts = [prompt_for(t, wd, s) for s in t["steps"]] if t["steps"] else [prompt_for(t, wd)]
        if not server.wait_healthy(self.url):
            raise InfraError("server not healthy")
        t0 = time.time()
        timed_out = False
        swept = 0
        with open(os.path.join(rdir, "events.jsonl"), "w") as out:
            for prompt in prompts:
                pr = subprocess.Popen(cmd + [prompt], cwd=wd, env=env, stdout=out, stderr=subprocess.STDOUT,
                                      stdin=subprocess.DEVNULL, start_new_session=True,
                                      preexec_fn=lambda: sandbox.limit(sandbox.AGENT_FSIZE))
                self.watchdog.add(pr.pid)
                try:
                    pr.wait(timeout=self.a.timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                try:
                    os.killpg(pr.pid, signal.SIGKILL)   # the agent and anything it left running in its session
                except OSError:
                    pass
                pr.wait()
                self.watchdog.discard(pr.pid)
                swept += sandbox.sweep(wd, self.watchdog.log)
                out.flush()
                if timed_out:
                    break
        secs = time.time() - t0
        conn_err = False
        with open(os.path.join(rdir, "events.jsonl"), errors="replace") as ev:     # streamed: it can be large
            for line in ev:
                if '"Connection error' in line or "ECONNREFUSED" in line:
                    conn_err = True
                    break
        if conn_err:
            # the server was unreachable: not the model's failure - requeue instead of recording a result
            raise InfraError("connection error during %s/%s/s%d" % (cond, tid, k))
        if not os.path.exists(os.path.join(wd, t["file"])):
            raw, fails = "", ["FAIL %s does not exist" % t["file"]]
        else:
            raw, rc = sandbox.run_tests(t["tests"], wd, self.watchdog)
            fails = sandbox.failures(raw, rc)
        swept += sandbox.sweep(wd, self.watchdog.log)
        with open(os.path.join(rdir, "tests.txt"), "w") as f:
            f.write(raw + ("\n" if raw else "") + "\n".join(fails) + "\n")
        stats, last_stop, outside = transcript_stats(os.path.join(rdir, "events.jsonl"), wd, self.peek)
        ext_events = Counter()
        if os.path.exists(ext_log):
            for line in open(ext_log, errors="replace"):
                try:
                    ext_events[json.loads(line)["kind"]] += 1
                except (ValueError, KeyError, TypeError):
                    pass
        res = {"cond": cond, "task": tid, "tier": t["tier"], "category": t["category"], "seed": k, "model": self.model,
               "max_tokens": c["max_tokens"], "thinking": c["thinking"], "secs": round(secs, 1),
               "memory_kills": self.watchdog.kills.get(wd, 0), "swept_processes": swept, "timed_out": timed_out,
               "passed": not fails, "outcome": classify(fails), "failures": fails[:20], "last_stop": last_stop,
               "writes_outside_workdir": outside, "extension_events": dict(ext_events), **stats}

        def skip(d, names):                             # caches, and any file over 10 MB (runaway output)
            return [n for n in names if n in ("__pycache__", "node_modules") or
                    (os.path.isfile(os.path.join(d, n)) and os.path.getsize(os.path.join(d, n)) > 10 << 20)]
        shutil.copytree(wd, os.path.join(rdir, "workdir"), ignore=skip, symlinks=True)
        with open(os.path.join(rdir, "result.json"), "w") as f:
            json.dump(res, f, indent=1)
        shutil.rmtree(wd, ignore_errors=True)
        return res

    # ------------------------------------------------------------------ manifest
    def manifest(self):
        env = pi_env(self.pi, self.agent_dir)

        def sh(cmd):
            try:
                return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                                      timeout=30, env=env, stdin=subprocess.DEVNULL).stdout.strip()
            except Exception as e:  # noqa: BLE001
                return repr(e)
        ok, health = server.health(self.url)
        ext = None
        if self.ext:
            files = [self.ext] if os.path.isfile(self.ext) else sorted(
                os.path.join(r, f) for r, _, fs in os.walk(self.ext) if "node_modules" not in r for f in fs)
            ext = {"name": os.path.basename(self.ext),
                   "sha256": {os.path.relpath(f, os.path.dirname(self.ext)): hashlib.sha256(open(f, "rb").read()).hexdigest()
                              for f in files}}
        u = platform.uname()
        with open(os.path.join(self.agent_dir, "models.json")) as f:
            models = json.load(f)
        with open(os.path.join(self.agent_dir, "settings.json")) as f:
            settings = json.load(f)
        with open(os.path.join(self.agent_dir, "SYSTEM.md")) as f:
            system = f.read()
        m = {"runid": self.runid, "kbench": __version__, "started_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
             "url": piconfig.public_url(self.url), "model": self.model, "conds": self.conds, "seeds": self.seeds,
             "tasks": self.tasks, "workers": self.a.workers, "timeout_s": self.a.timeout,
             "test_timeout_s": sandbox.TEST_TIMEOUT, "rss_limit_gb": self.a.rss_limit_gb,
             "max_procs_per_session": self.a.max_procs, "server_health_ok": ok, "server_health": health,
             "server_models": server.models(self.url), "pi_version": sh([self.pi, "--version"]),
             "node_version": sh(["node", "--version"]), "python": platform.python_version(),
             "os": "%s %s %s" % (u.system, u.release, u.machine), "extension": ext,
             "gpus": sh(["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total", "--format=csv,noheader"])
             if shutil.which("nvidia-smi") else None,
             "pi_models": piconfig.redact(models), "pi_settings": settings, "system_prompt": system}
        with open(os.path.join(self.runs, "manifest.json"), "w") as f:
            json.dump(m, f, indent=1)

    # ------------------------------------------------------------------ all jobs
    def run(self):
        os.makedirs(self.runs, exist_ok=True)
        os.makedirs(self.work, exist_ok=True)
        piconfig.write(self.agent_dir, self.url, self.model, self.conds, self.a.context, self.a.request_timeout)
        missing = sorted({r for tid in self.tasks for r in TASK[tid]["requires"] if not shutil.which(r)})
        if missing:
            print("warning: not installed: %s (tasks that need them will fail)" % ", ".join(missing), flush=True)
        ok, h = server.health(self.url)
        print("server %s: %s" % ("ok" if ok else "NOT REACHABLE", json.dumps(h)[:200]), flush=True)
        self.manifest()
        q = queue.Queue()
        # seed-major order: every condition gets seed 1 of every task before any seed 2, so a partial run is balanced
        for k in range(1, self.seeds + 1):
            for tid in self.tasks:
                for cond in self.conds:
                    q.put((cond, tid, k))
        total = q.qsize()
        done = [0]
        lock = threading.Lock()
        t0 = time.time()

        def worker():
            while True:
                try:
                    job = q.get_nowait()
                except queue.Empty:
                    return
                try:
                    r = self.run_one(job)
                except InfraError as e:
                    with lock:
                        self.requeues[job] += 1
                        again = self.requeues[job] <= MAX_REQUEUE
                        print("[infra] %s - %s" % (e, "requeued" if again else "given up"), flush=True)
                    if again:
                        q.put(job)
                        time.sleep(30)
                        continue
                    r = {"error": repr(e)}
                except Exception as e:  # noqa: BLE001
                    r = {"error": repr(e)}
                with lock:
                    done[0] += 1
                    if r:
                        print("[%5.0fs %3d/%d] %-9s %-20s s%d %-7s %6.1fs %s" % (
                            time.time() - t0, done[0], total, job[0], job[1], job[2], r.get("outcome", "ERROR"),
                            r.get("secs", 0), r.get("error", "")), flush=True)

        self.watchdog = sandbox.Watchdog(self.work, os.path.join(self.runs, "watchdog.log"), self.a.rss_limit_gb,
                                         self.a.max_procs)
        self.watchdog.start()
        threads = [threading.Thread(target=worker) for _ in range(max(1, self.a.workers))]
        try:
            for th in threads:
                th.start()
            for th in threads:
                th.join()
        finally:
            self.watchdog.stop()
            n = sandbox.sweep(self.work, self.watchdog.log)
            if n:
                print("end-of-run sweep killed %d processes" % n)
            if not self.a.keep_work:
                shutil.rmtree(self.work, ignore_errors=True)
                try:
                    os.rmdir(os.path.dirname(self.work))     # the parent, only when it is empty
                except OSError:
                    pass
        print("done in %.0fs" % (time.time() - t0))
