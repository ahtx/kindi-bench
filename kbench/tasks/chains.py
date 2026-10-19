"""Chain variants of three terminal tasks (topip, counterrors, largest3).

  *_steps     the same job as a chain of small prompts; each step is a fresh pi session in the same folder
  *_cmd       the single prompt, plus the instruction to use shell commands
  *_stepscmd  the chain, plus the instruction to use one shell command for each step

Each variant keeps the setup files, the hidden test and the reference solution of its base task."""
from . import terminal

BY = {t["id"]: t for t in terminal.TASKS}
T = []


def chain(base, steps):
    t = dict(BY[base])
    t.update(id=base + "_steps", category="chain", base=base, steps=steps, prompt=" / ".join(steps))
    T.append(t)


chain("topip", [
    "access.log is a web server log. The first field of each line is the client IP address. Write only that first "
    "field of every line to ips.txt, one per line.",
    "ips.txt has one IP address per line. Count how many times each address occurs. Write counts.txt with one line per "
    "address as: <count> <address>, highest count first.",
    "Write only the address from the first line of counts.txt to answer.txt.",
])
chain("counterrors", [
    "logs/app.log is an application log. The third field of each line is the level. Write every line whose third "
    "field is exactly ERROR to errors.txt.",
    "How many lines does errors.txt have? Write only the number to answer.txt.",
])
CMD = " Use shell commands (for example find, sort, head, awk, wc, uniq) to do it. Do not count or copy the data by hand."


def single_cmd(base):
    t = dict(BY[base])
    t.update(id=base + "_cmd", category="chain", base=base, prompt=BY[base]["prompt"] + CMD)
    T.append(t)


def chain_cmd(base, steps):
    t = dict(BY[base])
    steps = [s + " Use one shell command for this step. Do not copy the data by hand." for s in steps]
    t.update(id=base + "_stepscmd", category="chain", base=base, steps=steps, prompt=" / ".join(steps))
    T.append(t)


for b in ("topip", "counterrors", "largest3"):
    single_cmd(b)

chain("largest3", [
    "Write the size in bytes and the path of every file under the data folder to sizes.txt, one file per line, as: "
    "<size> <path>",
    "Sort the lines of sizes.txt by the size number, largest first, and write the result to sorted.txt.",
    "Copy the first 3 lines of sorted.txt to answer.txt.",
])

for t in list(T):
    if t["id"].endswith("_steps"):
        chain_cmd(t["id"][:-len("_steps")], t["steps"])


_WHAT = {
    "topip": "the client IP address with the most requests",
    "counterrors": "the number of ERROR lines in a log",
    "largest3": "the 3 largest files under a folder",
}
WHAT = {}
for _t in T:
    _b = _t["base"]
    if _t["id"].endswith("_stepscmd"):
        WHAT[_t["id"]] = "Chain of %d prompts with one shell command each: %s." % (len(_t["steps"]), _WHAT[_b])
    elif _t["id"].endswith("_steps"):
        WHAT[_t["id"]] = "Chain of %d small prompts: %s." % (len(_t["steps"]), _WHAT[_b])
    else:
        WHAT[_t["id"]] = "One prompt that asks for shell commands: %s." % _WHAT[_b]
TASKS = T
REQUIRES = {}
