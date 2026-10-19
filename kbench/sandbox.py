"""Safety limits for code that the model writes and runs. Linux only (the watchdog reads /proc).

The agent runs shell commands and programs that the model wrote. During our own runs, such programs:
  - took 26 GB of memory and stopped the model server   -> the memory watchdog (per process, default 2 GB)
  - started themselves 42,592 times                     -> the process watchdog (default 200 per session)
  - printed without end and grew the harness to 22.8 GB -> test output goes to a file with a size limit
  - kept running after the agent stopped                 -> each run's process group is killed, then a sweep
                                                            kills every process whose cwd is in the work folder
These limits reduce the risk. They are not a sandbox. Run the benchmark in a VM, a container or as a throwaway user.
"""
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter

AGENT_FSIZE = 1 << 30          # an agent (and its children) may write files of up to 1 GB
TEST_FSIZE = 20 << 20          # hidden-test output is capped at 20 MB
NPROC = 6000                   # RLIMIT_NPROC counts all processes of the user: a backstop above the normal total
TEST_TIMEOUT = 90              # seconds for one hidden test
KEEP_OUTPUT = 1 << 20          # at most 1 MB of test output is kept


def limit(nbytes):
    """preexec_fn for each agent / test child: a file-size cap and a process cap."""
    resource.setrlimit(resource.RLIMIT_FSIZE, (nbytes, nbytes))
    soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
    cap = NPROC if hard == resource.RLIM_INFINITY else min(NPROC, hard)
    resource.setrlimit(resource.RLIMIT_NPROC, (cap, cap))


def session_of(pid):
    try:
        with open("/proc/%s/stat" % pid) as f:
            return int(f.read().rsplit(")", 1)[1].split()[3])      # field 6: session id
    except (OSError, ValueError, IndexError):
        return None


def cwd_of(pid):
    try:
        return os.readlink("/proc/%s/cwd" % pid)
    except OSError:
        return None


def under(path, root):
    return path is not None and (path == root or path.startswith(root.rstrip("/") + "/"))


class Watchdog(threading.Thread):
    """Every 2 s: kill any session in `sessions` that has more than max_procs processes (fork bomb), and kill any
    process past rss_limit_kb resident memory whose cwd is in work_root or whose session is in `sessions` (an agent
    program can cd to /tmp; its session id still ties it to the run)."""

    def __init__(self, work_root, log_path, rss_limit_gb=2.0, max_procs=200):
        super().__init__(daemon=True)
        self.work_root = os.path.realpath(work_root)
        self.log_path = log_path
        self.rss_limit_kb = int(rss_limit_gb * 1024 * 1024)
        self.max_procs = max_procs
        self.sessions = set()
        self.kills = Counter()                 # work dir (or "session-N") -> processes killed
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

    def add(self, sid):
        with self.lock:
            self.sessions.add(sid)

    def discard(self, sid):
        with self.lock:
            self.sessions.discard(sid)

    def log(self, text):
        with open(self.log_path, "a") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), text))

    def stop(self):
        self.stop_event.set()

    def run(self):
        me = os.getpid()
        while not self.stop_event.is_set():
            with self.lock:
                sessions = set(self.sessions)
            pids = [p for p in os.listdir("/proc") if p.isdigit() and int(p) != me]
            per_session = Counter(session_of(p) for p in pids)
            for sid in sessions:
                if per_session.get(sid, 0) > self.max_procs:
                    try:
                        os.killpg(sid, signal.SIGKILL)
                    except OSError:
                        pass
                    self.kills["session-%d" % sid] += 1
                    self.log("killed session %d: %d processes (fork bomb)" % (sid, per_session[sid]))
            for pid in pids:
                try:
                    cwd = cwd_of(pid)
                    if not under(cwd, self.work_root) and session_of(pid) not in sessions:
                        continue
                    with open("/proc/%s/status" % pid) as f:
                        rss = next((int(l.split()[1]) for l in f if l.startswith("VmRSS:")), 0)
                    if rss > self.rss_limit_kb:
                        with open("/proc/%s/cmdline" % pid, "rb") as f:
                            cmd = f.read().replace(b"\0", b" ")[:200].decode("utf-8", "replace")
                        os.kill(int(pid), signal.SIGKILL)
                        parts = (cwd or "")[len(self.work_root):].strip("/").split("/")
                        wd = os.path.join(self.work_root, *parts[:3]) if len(parts) >= 3 else (cwd or "?")
                        self.kills[wd] += 1
                        self.log("killed pid %s rss %.1f GB cwd %s cmd %s" % (pid, rss / 1048576, cwd, cmd))
                except (OSError, StopIteration, ValueError):
                    continue
            self.stop_event.wait(2)


def sweep(root, log=None):
    """Kill every process whose cwd is in root (programs that left the agent's session, for example with setsid or
    nohup). Returns the number of processes killed."""
    root = os.path.realpath(root)
    me = os.getpid()
    n = 0
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == me:
            continue
        if under(cwd_of(pid), root):
            try:
                os.kill(int(pid), signal.SIGKILL)
                n += 1
                if log:
                    log("sweep killed pid %s (cwd in %s)" % (pid, root))
            except OSError:
                pass
    return n


def run_tests(tests, wd, watchdog=None, timeout=TEST_TIMEOUT):
    """Run a hidden test in wd. The test file lives outside wd; PYTHONPATH=wd so that `import calc` finds the agent's
    file. Output goes to a capped file, never into a pipe of this process. Returns (output, returncode or None on
    timeout)."""
    tdir = tempfile.mkdtemp(prefix="kbench-test-")
    try:
        tf = os.path.join(tdir, "hidden_test.py")
        with open(tf, "w") as f:
            f.write(tests)
        outf = os.path.join(tdir, "out.txt")
        env = dict(os.environ, PYTHONPATH=wd, PYTHONDONTWRITEBYTECODE="1")
        with open(outf, "w") as o:
            pr = subprocess.Popen([sys.executable, tf], cwd=wd, env=env, stdout=o, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, start_new_session=True,
                                  preexec_fn=lambda: limit(TEST_FSIZE))
            if watchdog:
                watchdog.add(pr.pid)
            try:
                rc = pr.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                rc = None
            finally:
                try:
                    os.killpg(pr.pid, signal.SIGKILL)       # the test and anything it started
                except OSError:
                    pass
                pr.wait()
                if watchdog:
                    watchdog.discard(pr.pid)
        with open(outf, errors="replace") as o:
            raw = o.read(KEEP_OUTPUT)
        return raw, rc
    finally:
        shutil.rmtree(tdir, ignore_errors=True)


def failures(raw, rc, timeout=TEST_TIMEOUT):
    lines = [l for l in raw.splitlines() if l.strip()]
    fails = [l for l in lines if l.startswith("FAIL")]
    if rc is None:
        fails.append("FAIL timeout: the tests did not finish in %d s" % timeout)
    elif rc != 0:
        fails.append("FAIL crashed: " + (lines[-1][:300] if lines else "exit %d" % rc))
    return fails


def prepare(task, wd):
    """Write the task's setup files and run its setup command in an empty folder."""
    for name, content in task["setup_files"].items():
        p = os.path.join(wd, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(content)
    if task["setup_cmd"]:
        subprocess.run(["bash", "-c", task["setup_cmd"]], cwd=wd, check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
