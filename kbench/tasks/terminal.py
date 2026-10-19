"""Terminal tasks: the everyday jobs that people ask a terminal agent to do.

Each task has a prompt, `setup` (bash that runs in the empty work folder before the agent starts), `tests` (Python
that runs in the work folder after the agent stops and prints one FAIL line for each problem) and `ref` (bash that
does the task; only `kbench validate` uses it, to prove that the tests pass on a correct result and fail on the
untouched folder). When the task asks for an answer, the agent writes it to answer.txt, so the check is mechanical."""

TASKS = []


def task(id, prompt, setup, tests, ref, file="answer.txt"):
    TASKS.append({"id": id, "category": "terminal", "tier": "terminal", "kind": "terminal", "prompt": prompt,
                  "setup_cmd": setup, "tests": tests, "solution_cmd": ref, "file": file})


ANS = r'''
import os
def ans():
    if not os.path.exists("answer.txt"):
        print("FAIL answer.txt does not exist"); return None
    return open("answer.txt").read().strip()
'''

# ------------------------------------------------------------------ files and disk
task("largest3",
     "Find the 3 largest files anywhere under the data folder. Write them to answer.txt, largest first, one per line, "
     "as: <size in bytes> <path relative to the working folder>",
     "mkdir -p data/a data/b/c; head -c 5000 /dev/zero > data/a/x.bin; head -c 12000 /dev/zero > data/b/c/y.log; "
     "head -c 300 /dev/zero > data/z.txt; head -c 8000 /dev/zero > data/b/w.dat; head -c 7000 /dev/zero > data/v.csv",
     ANS + r'''
a = ans()
if a is not None:
    rows = [l.split() for l in a.splitlines() if l.strip()]
    got = [(r[0], r[-1].replace("./", "", 1)) for r in rows]
    want = [("12000", "data/b/c/y.log"), ("8000", "data/b/w.dat"), ("7000", "data/v.csv")]
    if got != want: print("FAIL answer.txt = %r, expected %r" % (got, want))
''', "find data -type f -printf '%s %p\\n' | sort -rn | head -3 > answer.txt")

task("diskfree",
     "How much space is free on the filesystem that holds the working folder? Write only the number of available "
     "1K-blocks (the 'Available' column of df -k for this folder) to answer.txt.",
     "true",
     ANS + r'''
import subprocess
a = ans()
if a is not None:
    real = int(subprocess.run(["df", "-k", "--output=avail", "."], stdout=subprocess.PIPE, universal_newlines=True).stdout.split()[-1])
    try:
        v = int(a.replace(",", ""))
        if abs(v - real) > max(2000000, real * 0.02): print("FAIL answer %d, df says %d" % (v, real))
    except ValueError: print("FAIL answer.txt is not a number: %r" % a[:80])
''', "df -k --output=avail . | tail -1 | tr -d ' ' > answer.txt")

task("countpy",
     "How many lines are there in total in all the .py files under the src folder (as wc -l counts them)? Write only "
     "the number to answer.txt.",
     "mkdir -p src/pkg; printf 'a=1\\nb=2\\n' > src/m.py; printf 'x\\ny\\nz\\n\\n' > src/pkg/n.py; printf 'q\\n' > src/pkg/o.py; "
     "printf 'not python\\nnot\\n' > src/readme.txt",
     ANS + r'''
a = ans()
if a is not None and a != "7": print("FAIL answer.txt = %r, expected 7" % a)
''', "find src -name '*.py' -exec cat {} + | wc -l > answer.txt")

task("todos",
     "List every file under the src folder that contains the word TODO. Write their paths relative to the working "
     "folder to answer.txt, sorted, one per line.",
     "mkdir -p src/a src/b; echo 'x = 1  # TODO fix' > src/a/one.py; echo 'clean' > src/a/two.py; "
     "printf 'line\\nTODO: later\\n' > src/b/three.js; echo 'todo lowercase' > src/b/four.py; echo TODO > src/five.md",
     ANS + r'''
a = ans()
if a is not None:
    got = sorted(l.strip().replace("./", "", 1) for l in a.splitlines() if l.strip())
    want = ["src/a/one.py", "src/b/three.js", "src/five.md"]
    if got != want: print("FAIL answer.txt = %r, expected %r" % (got, want))
''', "grep -rl 'TODO' src | sort > answer.txt")

task("renamejpeg",
     "In the photos folder, rename every file that ends in .jpeg so that it ends in .jpg instead. Do not change any "
     "other file.",
     "mkdir -p photos; for n in a b c; do echo $n > photos/$n.jpeg; done; echo d > photos/d.png; echo e > photos/e.jpg",
     r'''
import os
got = sorted(os.listdir("photos")) if os.path.isdir("photos") else []
want = ["a.jpg", "b.jpg", "c.jpg", "d.png", "e.jpg"]
if got != want: print("FAIL photos contains %r, expected %r" % (got, want))
elif open("photos/a.jpg").read().strip() != "a": print("FAIL a.jpg lost its content")
''', "cd photos && for f in *.jpeg; do mv \"$f\" \"${f%.jpeg}.jpg\"; done", file="photos")

task("tarbackup",
     "Make a gzip-compressed tar archive named backup.tar.gz in the working folder that contains the docs folder "
     "(with its files).",
     "mkdir -p docs/sub; echo one > docs/a.txt; echo two > docs/sub/b.txt",
     r'''
import tarfile
try:
    with tarfile.open("backup.tar.gz", "r:gz") as t:
        names = sorted(n.lstrip("./") for n in t.getnames())
    need = {"docs/a.txt", "docs/sub/b.txt"}
    if not need <= set(names): print("FAIL backup.tar.gz holds %r, needs %r" % (names, sorted(need)))
except Exception as e: print("FAIL cannot read backup.tar.gz as tar.gz: %r" % e)
''', "tar czf backup.tar.gz docs", file="backup.tar.gz")

task("unzipcount",
     "Extract archive.zip into a folder named out, then write the number of files it contained to answer.txt.",
     "mkdir -p z/in; for i in 1 2 3 4; do echo $i > z/in/f$i.txt; done; (cd z && python3 -c \"import zipfile,os; zf=zipfile.ZipFile('../archive.zip','w'); [zf.write(os.path.join('in',f)) for f in sorted(os.listdir('in'))]; zf.close()\"); rm -rf z",
     ANS + r'''
import os
a = ans()
files = [os.path.join(r, f) for r, _, fs in os.walk("out") for f in fs] if os.path.isdir("out") else []
if len(files) != 4: print("FAIL out holds %d files, expected 4" % len(files))
if a is not None and a != "4": print("FAIL answer.txt = %r, expected 4" % a)
''', "mkdir -p out && python3 -c \"import zipfile; zipfile.ZipFile('archive.zip').extractall('out')\" && echo 4 > answer.txt")

task("execrun",
     "Make run.sh executable, run it, and save everything it prints into out.txt.",
     "printf '#!/bin/bash\\necho started\\necho done-42\\n' > run.sh",
     r'''
import os
if not os.access("run.sh", os.X_OK): print("FAIL run.sh is not executable")
if not os.path.exists("out.txt"): print("FAIL out.txt does not exist")
elif open("out.txt").read().split() != ["started", "done-42"]: print("FAIL out.txt = %r" % open("out.txt").read()[:100])
''', "chmod +x run.sh && ./run.sh > out.txt", file="out.txt")

# ------------------------------------------------------------------ logs and text
task("counterrors",
     "logs/app.log is an application log. How many lines in it have the level ERROR? Write only the number to "
     "answer.txt.",
     "mkdir -p logs; python3 -c \"import random; random.seed(5); L=['INFO','WARN','ERROR','DEBUG']; f=open('logs/app.log','w'); [f.write('2026-10-18 10:%02d:%02d %s worker-%d: event %d\\n' % (i//60, i%60, random.choice(L), i%4, i)) for i in range(400)]; f.write('2026-10-18 11:00:00 INFO message mentions ERROR in text\\n')\"",
     ANS + r'''
import re
a = ans()
want = sum(1 for l in open("logs/app.log") if l.split()[2] == "ERROR")
if a is not None and a != str(want): print("FAIL answer.txt = %r, expected %d" % (a, want))
''', "awk '$3==\"ERROR\"' logs/app.log | wc -l > answer.txt")

task("topip",
     "access.log is a web server log. Which client IP address made the most requests? Write only that IP to answer.txt.",
     "python3 -c \"import random; random.seed(9); ips=['10.0.0.%d'%i for i in range(1,9)]; w=[3,9,4,2,7,1,5,2]; f=open('access.log','w'); [f.write('%s - - [18/Oct/2026:10:00:%02d +0000] \\\"GET /p%d HTTP/1.1\\\" 200 512\\n' % (random.choices(ips,w)[0], i%60, i)) for i in range(600)]\"",
     ANS + r'''
from collections import Counter
a = ans()
want = Counter(l.split()[0] for l in open("access.log")).most_common(1)[0][0]
if a is not None and a != want: print("FAIL answer.txt = %r, expected %r" % (a, want))
''', "awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -1 | awk '{print $2}' > answer.txt")

task("dedupenames",
     "names.txt has one name per line with repeats. Write unique.txt with each name once, sorted alphabetically.",
     "printf 'carol\\nalice\\nbob\\nalice\\ndave\\ncarol\\nbob\\nerin\\n' > names.txt",
     r'''
import os
if not os.path.exists("unique.txt"): print("FAIL unique.txt does not exist")
elif open("unique.txt").read().split() != ["alice", "bob", "carol", "dave", "erin"]: print("FAIL unique.txt = %r" % open("unique.txt").read()[:120])
''', "sort -u names.txt > unique.txt", file="unique.txt")

task("emails",
     "contacts.txt is free text. Extract every e-mail address in it, remove duplicates, and write them to emails.txt "
     "sorted, one per line.",
     "printf 'Call ann@example.com or bob.smith@example.org.\\nCC: ann@example.com; zed+test@mail.example.net\\nno address here\\n' > contacts.txt",
     r'''
import os
want = ["ann@example.com", "bob.smith@example.org", "zed+test@mail.example.net"]
if not os.path.exists("emails.txt"): print("FAIL emails.txt does not exist")
elif sorted(open("emails.txt").read().split()) != want or open("emails.txt").read().split() != want: print("FAIL emails.txt = %r, expected %r" % (open("emails.txt").read()[:200], want))
''', "grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}' contacts.txt | sort -u > emails.txt", file="emails.txt")

task("wordcount",
     "How many words are in essay.txt (as wc -w counts them)? Write only the number to answer.txt.",
     "python3 -c \"import random; random.seed(2); w='the quick brown fox jumps over a lazy dog and runs away'.split(); open('essay.txt','w').write('\\n'.join(' '.join(random.choice(w) for _ in range(random.randint(3,15))) for _ in range(40)))\"",
     ANS + r'''
a = ans()
want = len(open("essay.txt").read().split())
if a is not None and a != str(want): print("FAIL answer.txt = %r, expected %d" % (a, want))
''', "wc -w < essay.txt | tr -d ' ' > answer.txt")

task("replaceall",
     "In every .txt file under the notes folder, replace the word foo with bar. Do not touch other files.",
     "mkdir -p notes/x; echo 'foo and foo' > notes/a.txt; echo 'no match' > notes/b.txt; echo 'foo deep' > notes/x/c.txt; echo 'foo keep' > notes/keep.md",
     r'''
import os
exp = {"notes/a.txt": "bar and bar", "notes/b.txt": "no match", "notes/x/c.txt": "bar deep", "notes/keep.md": "foo keep"}
for p, w in exp.items():
    g = open(p).read().strip() if os.path.exists(p) else None
    if g != w: print("FAIL %s = %r, expected %r" % (p, g, w))
''', "find notes -name '*.txt' -exec sed -i 's/foo/bar/g' {} +", file="notes")

# ------------------------------------------------------------------ data formats
task("csv2json",
     "Convert people.csv to people.json: a JSON list with one object per row, using the header names as keys and "
     "every value as a string.",
     "printf 'name,age,city\\nAnn,34,Austin\\nBob,29,Boston\\nCy,41,\"Salt Lake City\"\\n' > people.csv",
     r'''
import json, os
want = [{"name": "Ann", "age": "34", "city": "Austin"}, {"name": "Bob", "age": "29", "city": "Boston"}, {"name": "Cy", "age": "41", "city": "Salt Lake City"}]
try:
    got = json.load(open("people.json"))
    if got != want: print("FAIL people.json = %r" % (got,))
except Exception as e: print("FAIL people.json: %r" % e)
''', "python3 -c \"import csv,json; json.dump(list(csv.DictReader(open('people.csv'))), open('people.json','w'))\"",
     file="people.json")

task("jsonvalue",
     "config.json is a nested settings file. Write the value of database.port to answer.txt (only the value).",
     "printf '{\"app\": {\"name\": \"demo\", \"port\": 8000}, \"database\": {\"host\": \"db\", \"port\": 5432, \"user\": \"app\"}}' > config.json",
     ANS + r'''
a = ans()
if a is not None and a != "5432": print("FAIL answer.txt = %r, expected 5432" % a)
''', "python3 -c \"import json; print(json.load(open('config.json'))['database']['port'])\" > answer.txt")

task("sortcsv",
     "scores.csv has a header row. Write sorted.csv with the same header and the rows sorted by the score column, "
     "highest first.",
     "printf 'name,score\\nann,72\\nbob,95\\ncy,8\\ndee,100\\neve,72\\n' > scores.csv",
     r'''
import csv, os
if not os.path.exists("sorted.csv"): print("FAIL sorted.csv does not exist")
else:
    rows = list(csv.reader(open("sorted.csv")))
    if not rows or rows[0] != ["name", "score"]: print("FAIL header is %r" % (rows[:1],))
    sc = [int(r[1]) for r in rows[1:] if len(r) > 1]
    if sc != [100, 95, 72, 72, 8] or sorted(r[0] for r in rows[1:]) != ["ann", "bob", "cy", "dee", "eve"]: print("FAIL rows = %r" % rows[1:])
''', "(head -1 scores.csv; tail -n +2 scores.csv | sort -t, -k2,2nr) > sorted.csv", file="sorted.csv")

task("editport",
     "settings.ini has a line port=8080. Change it to port=9090 and leave every other line exactly as it is.",
     "printf '[server]\\nhost=0.0.0.0\\nport=8080\\n# keep this comment\\n[client]\\nretries=3\\n' > settings.ini",
     r'''
import os
want = "[server]\nhost=0.0.0.0\nport=9090\n# keep this comment\n[client]\nretries=3\n"
g = open("settings.ini").read() if os.path.exists("settings.ini") else ""
if g.rstrip("\n") != want.rstrip("\n"): print("FAIL settings.ini = %r" % g)
''', "sed -i 's/^port=8080$/port=9090/' settings.ini", file="settings.ini")

# ------------------------------------------------------------------ system and tools
task("pyversion",
     "Which version of python3 is installed? Write only the version number (for example 3.9.7) to answer.txt.",
     "true",
     ANS + r'''
import subprocess
a = ans()
real = subprocess.run(["python3", "-c", "import platform; print(platform.python_version())"], stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()
if a is not None and a.replace("Python", "").strip() != real: print("FAIL answer.txt = %r, expected %r" % (a, real))
''', "python3 -c 'import platform; print(platform.python_version())' > answer.txt")

task("gpuname",
     "What is the name of the first NVIDIA GPU in this machine, as nvidia-smi reports it? Write only the name to "
     "answer.txt.",
     "true",
     ANS + r'''
import subprocess
a = ans()
real = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader", "-i", "0"], stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()
if a is not None and a != real: print("FAIL answer.txt = %r, expected %r" % (a, real))
''', "nvidia-smi --query-gpu=name --format=csv,noheader -i 0 > answer.txt")

task("cronline",
     "Write one crontab line to cron.txt that runs /opt/backup.sh every day at 02:30.",
     "true",
     r'''
import os
if not os.path.exists("cron.txt"): print("FAIL cron.txt does not exist")
else:
    lines = [l for l in open("cron.txt").read().splitlines() if l.strip() and not l.strip().startswith("#")]
    f = lines[0].split() if lines else []
    if len(lines) != 1 or f[:5] != ["30", "2", "*", "*", "*"] or f[5:] != ["/opt/backup.sh"]: print("FAIL cron.txt = %r" % lines)
''', "echo '30 2 * * * /opt/backup.sh' > cron.txt", file="cron.txt")

task("daysbetween",
     "How many days are there from 2026-01-15 to 2026-10-18? Write only the number to answer.txt.",
     "true",
     ANS + r'''
a = ans()
if a is not None and a != "276": print("FAIL answer.txt = %r, expected 276" % a)
''', "python3 -c \"from datetime import date; print((date(2026,10,18)-date(2026,1,15)).days)\" > answer.txt")

task("gitinit",
     "Make the project folder a git repository and commit README.md in it with the commit message: initial",
     "mkdir -p project; echo '# Demo' > project/README.md",
     r'''
import subprocess
r = subprocess.run(["git", "-C", "project", "log", "--format=%s", "--name-only"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
if r.returncode != 0: print("FAIL project is not a git repository with a commit: %s" % r.stderr.strip()[:100])
elif "initial" not in r.stdout.splitlines()[:1] or "README.md" not in r.stdout: print("FAIL git log = %r" % r.stdout[:200])
''', "cd project && git init -q && git add README.md && git -c user.name=x -c user.email=x@example.com commit -q -m initial",
     file="project")

task("hellosh",
     "Write a bash script hello.sh that prints Hello, NAME! where NAME is the value of the environment variable NAME, "
     "or world when NAME is not set.",
     "true",
     r'''
import subprocess, os
def run(env):
    e = {k: v for k, v in os.environ.items() if k != "NAME"}; e.update(env)
    return subprocess.run(["bash", "hello.sh"], stdout=subprocess.PIPE, universal_newlines=True, env=e, timeout=10).stdout.strip()
if not os.path.exists("hello.sh"): print("FAIL hello.sh does not exist")
else:
    if run({}) != "Hello, world!": print("FAIL without NAME it printed %r" % run({}))
    if run({"NAME": "Sam"}) != "Hello, Sam!": print("FAIL with NAME=Sam it printed %r" % run({"NAME": "Sam"}))
''', "printf '#!/bin/bash\\necho \"Hello, ${NAME:-world}!\"\\n' > hello.sh", file="hello.sh")


WHAT = {
    "largest3": "Find the 3 largest files under a folder; write them largest first.",
    "diskfree": "Write the free space of the filesystem of the work folder, in 1K blocks.",
    "countpy": "Count the lines in all the .py files under a folder (as wc -l counts them).",
    "todos": "List every file under a folder that contains the word TODO.",
    "renamejpeg": "Rename every .jpeg file in a folder to .jpg and change nothing else.",
    "tarbackup": "Make a gzip-compressed tar archive of a folder.",
    "unzipcount": "Extract a zip archive and write how many files it held.",
    "execrun": "Make a script executable, run it and save its output.",
    "counterrors": "Count the ERROR lines in an application log.",
    "topip": "Find the client IP address with the most requests in a web log.",
    "dedupenames": "Write a list of names once each, sorted.",
    "emails": "Extract the e-mail addresses from free text, without duplicates, sorted.",
    "wordcount": "Count the words in a text file (as wc -w counts them).",
    "replaceall": "Replace foo with bar in every .txt file under a folder, and only there.",
    "csv2json": "Convert a CSV file to a JSON list of objects.",
    "jsonvalue": "Write one value from a nested JSON settings file.",
    "sortcsv": "Sort a CSV file by its score column, highest first, and keep the header.",
    "editport": "Change one line in a settings file and leave every other line as it is.",
    "pyversion": "Write the installed version of python3.",
    "gpuname": "Write the name of the GPU, as nvidia-smi reports it.",
    "cronline": "Write a crontab line that runs a script every day at 02:30.",
    "daysbetween": "Write the number of days between two dates.",
    "gitinit": "Make a folder a git repository and commit a file with a given message.",
    "hellosh": "Write a script that greets the name in an environment variable, with a default.",
}

REQUIRES = {"gpuname": ["nvidia-smi"], "gitinit": ["git"], "tarbackup": ["tar"], "diskfree": ["df"]}
