# kbench 0.1.0

kbench measures how well a small language model does real work as an agent. The agent is [pi](https://pi.dev), and pi
connects to the model through an OpenAI-compatible server. Then pi gets 65 tasks: programs to write, programs to
repair, and everyday terminal jobs. pi does each task in a new, empty folder. After pi stops, a hidden test examines
the folder and gives a pass or a fail.

We made kbench to measure Ternary-Bonsai-2-2B with [Kindi](https://github.com/ahtx/kindi) on a 2014 NVIDIA
Quadro K420. kbench works with any OpenAI-compatible server, for example the
`llama-server` program of llama.cpp. The results of our runs are in [results/](results/README.md). The full report is
at [amirhusain.com/kindi](https://www.amirhusain.com/kindi).

By [Amir Husain](https://www.amirhusain.com).

- [What is in kbench](#what-is-in-kbench)
- [Safety](#safety)
- [Requirements](#requirements)
- [Install](#install)
- [Quick start with Kindi](#quick-start-with-kindi)
- [Quick start with llama.cpp](#quick-start-with-llamacpp)
- [Commands](#commands)
- [Conditions](#conditions)
- [The tasks](#the-tasks)
- [How to read the results](#how-to-read-the-results)
- [License](#license)

## What is in kbench

| Command | What it does |
|---|---|
| `kbench run` | pi does the tasks. kbench grades each work folder with the hidden test of the task. |
| `kbench report`, `kbench collect` | A table of one run, or a JSON summary of one or more runs. |
| `kbench validate` | Proves each hidden test: the test fails on the untouched folder and passes on the reference solution. |
| `kbench textjobs` | Short text jobs through the chat API: classification, spelling and grammar fixes, tables, notes and news. |
| `kbench breakdown` | Five jobs that mix language and exact work. Each job runs three ways: as an agent task, as one prompt, and as one question for each item. |
| `kbench list`, `kbench show` | The task list, or the full text of one task. |

We wrote every task, every input file and every hidden test for this benchmark. Some of the tasks are classic
problems, for example LCS, Dijkstra, an LRU cache and Roman numerals. These problems are well known, but the prompts,
the files and the tests are ours. We also wrote all the items of the text jobs and of the breakdown jobs. The names,
companies and addresses in these items are fictional.

## Safety

**The agent runs commands and programs that the model writes.** A small model makes mistakes. In our own runs, model
programs used 26 GB of memory, started themselves 42,592 times, and printed text without end. Run kbench in a
virtual machine, in a container, or as a throwaway user. That user must not have access to your files or keys.

kbench has the limits below. These limits only decrease the risk:

| Limit | What it does |
|---|---|
| Work folders | Each run gets a new folder under `~/kbench-work/RUNID`. This folder is outside the repository, so the agent cannot find the hidden tests. |
| Memory watchdog | Every 2 seconds, kbench kills a process of the run that uses more than 2 GB of resident memory (`--rss-limit-gb`). |
| Process watchdog | kbench kills the whole session of an agent or a test that has more than 200 processes (`--max-procs`). |
| File size | An agent and its child processes can write files of up to 1 GB. A hidden test can write up to 20 MB. |
| Process count | `RLIMIT_NPROC` of 6000 for each agent and test, a backstop for the process watchdog. |
| Test output | The hidden test writes to a file, and kbench keeps at most 1 MB of it. |
| Time | Each pi session stops after `--timeout` seconds (default 600). Each hidden test stops after 90 seconds. |
| Cleanup | After each session, kbench kills the process group of the session. Then a sweep kills each process that has its current folder in the work folder. |
| Server errors | Before each task, kbench waits for an answer from `/health`. After a connection error, kbench puts the task back in the queue (at most 5 times). |

`runs/RUNID/watchdog.log` lists each process that kbench killed. `result.json` also counts the kills and the writes
outside the work folder for each run.

## Requirements

| | |
|---|---|
| OS | Linux. The watchdog reads `/proc`. The tasks use bash and GNU `find`, `sed` and `df`. |
| Python | 3.8 or later. kbench uses only the Python standard library. |
| Node.js | 22.19 or later, for pi and for the three JavaScript tasks |
| pi | `npm install -g @earendil-works/pi-coding-agent@1.3.0` (we used pi 1.3.0) |
| Other tools | `git`, `tar`, and `nvidia-smi` for the `gpuname` task |
| Server | An OpenAI-compatible server with the model, for example Kindi or llama.cpp `llama-server` |

## Install

```sh
git clone https://github.com/ahtx/kindi-bench.git && cd kindi-bench
python3 -m kbench --version          # kbench runs from the repository
pip install .                        # optional: puts a kbench command in PATH
python3 -m kbench validate           # every task must show OK
```

The commands below use `kbench`. Without `pip install`, use `python3 -m kbench` in the repository folder.

## Quick start with Kindi

Install Kindi and convert the model as the [Kindi README](https://github.com/ahtx/kindi) tells you. Then start the
server:

```sh
docker run -d --name kindi --restart unless-stopped --gpus all -u $(id -u):$(id -g) \
    -p 127.0.0.1:8093:8093 -v ~/.kindi:/data kindi:0.1.0
curl -s localhost:8093/health
curl -s localhost:8093/v1/models     # the model id, bonsai2-2b by default
```

Then run a small test, and the full benchmark:

```sh
kbench run smoke --model bonsai2-2b --tasks fizz,jsonvalue --conds think --seeds 1 --timeout 1800
kbench report smoke
kbench run k420 --model bonsai2-2b --conds think --seeds 1 --timeout 1800
```

The default URL is `http://127.0.0.1:8093/v1`. Kindi serves one request at a time, so keep `--workers 1`. On the
K420, one task takes from one minute to 30 minutes. Use `--timeout 1800` there.

The text jobs and the breakdown jobs:

```sh
kbench textjobs text-k420.json
kbench breakdown breakdown-k420.json --model bonsai2-2b
```

## Quick start with llama.cpp

The model file uses Prism ML's ternary format, PTQ1_0. Use a llama.cpp build that can load this format. Download
the model from [Hugging Face](https://huggingface.co/prism-ml/Ternary-Bonsai-2-2B-gguf). We used these server
settings, with the sampling values of Kindi:

```sh
llama-server -m Ternary-Bonsai-2-2B-PTQ1_0.gguf --alias bonsai2-2b --host 127.0.0.1 --port 8095 \
    -ngl 99 -fa on --cache-reuse 256 --jinja --reasoning-format auto \
    --chat-template-kwargs '{"enable_thinking":false}' --temp 0.7 --top-p 0.8 --top-k 20 --min-p 0 \
    -c 32768 --parallel 1
```

```sh
kbench run desk --url http://127.0.0.1:8095/v1 --model bonsai2-2b --seeds 3
kbench report desk
```

For more agents in parallel, start the server with `--parallel N` and `-c` set to N x 32768. Then give kbench
`--workers N`.

## Commands

```text
kbench run RUNID --model ID [--url URL] [--conds a,b] [--tasks ...] [--seeds N] [--workers N]
                 [--timeout S] [--thinking off|medium] [--max-tokens N] [--extension PATH]
                 [--work DIR] [--runs DIR] [--pi PATH] [--keep-work]
kbench report RUNID [--runs DIR]
kbench collect RUNID [RUNID ...] [--runs DIR] > results.json
kbench validate [--tasks ...] [--strict]
kbench textjobs OUT.json [--url URL] [--model ID] [--only job,job] [--limit K] [--parallel N]
kbench breakdown OUT.json [--url URL] [--model ID] [--only job,job] [--agent-runs N] [--api-runs N] [--pi PATH]
kbench list [--tasks ...] [--markdown]
kbench show TASK [--all]
```

- `--tasks` takes task ids, categories (`programming`, `repair`, `terminal`, `chain`) or tiers (`easy`, `medium`,
  `hard`). The default is all 65 tasks.
- `--seeds N` runs each task N times for each condition. kbench runs seed 1 of all tasks before seed 2.
- `--thinking` and `--max-tokens` replace the values of all the conditions that you select.
- `--extension PATH` loads a pi extension for the `ext` and `ext_think` conditions. kbench does not include an
  extension.
- `kbench run` skips each task that already has a `result.json`. To continue a stopped run, give the same command
  again.
- When the server needs an API key, put the key in the environment variable `KBENCH_API_KEY`.

For each run, kbench writes a pi configuration to `runs/RUNID/pi-agent/`. This folder contains `models.json`, `settings.json`
and `SYSTEM.md`. `models.json` points at `--url` and uses these compatibility settings for Kindi and llama.cpp:

```json
{"supportsDeveloperRole": false, "supportsReasoningEffort": false,
 "thinkingFormat": "qwen-chat-template", "thinkingTokenBudgetField": "thinking_budget_tokens"}
```

kbench starts pi as `pi -p --no-session --mode json --provider kb-COND --model ID --thinking LEVEL "prompt"` with
`PI_CODING_AGENT_DIR` set to that folder. The system prompt is in
[kbench/agent/SYSTEM.md](kbench/agent/SYSTEM.md).

## Conditions

A condition is a set of agent settings. Each reply of the model can have at most the given number of tokens.

| Condition | Output cap per reply | Thinking | Extension |
|---|---|---|---|
| `base` | 2048 | off | no |
| `think` | 4096 | medium (a budget of 1024 thinking tokens) | no |
| `base8k` | 8192 | off | no |
| `ext` | 8192 | off | `--extension` |
| `ext_think` | 8192 | medium | `--extension` |

The default is `base,think,base8k`. With `--extension`, the default also has `ext` and `ext_think`.

## The tasks

Each task in the `programming` category names one file. The agent must write the file, and the hidden test imports it or runs it. A
repair task starts with a file that has bugs. A terminal task starts with prepared files, and the agent must do a
job in the folder. When the job has an answer, the agent writes the answer to `answer.txt`. A chain task gives the
same job as a terminal task in a different form. The forms are: several small prompts (each one a new pi session in
the same folder), an instruction to use shell commands, or both.

The tiers are `easy`, `medium`, `hard` and `terminal`. `kbench show TASK --all` prints the prompt, the setup, the
hidden test and the reference solution of a task.

| id | category | tier | what |
|---|---|---|---|
| `calc` | `programming` | `hard` | Python: evaluate an arithmetic expression with precedence and parentheses, without eval(). |
| `csvline` | `programming` | `hard` | Python: split one CSV line into fields, with quotes and escaped quotes. |
| `lru` | `programming` | `hard` | Python: an LRU cache with get, put and keys. |
| `topo` | `programming` | `hard` | Python: the smallest valid order for tasks with dependencies, or None for a cycle. |
| `wordbreak` | `programming` | `hard` | Python: every way to split a string into words from a dictionary. |
| `roman` | `programming` | `hard` | Python: convert numbers to Roman numerals and back, and reject bad input. |
| `bigmul` | `programming` | `hard` | Python: multiply two very large integers given as strings, without int(). |
| `minwindow` | `programming` | `hard` | Python: the shortest substring that contains all the characters of another string. |
| `clamp` | `programming` | `easy` | Python: limit a number to a range; reject a range whose ends are in the wrong order. |
| `fizz` | `programming` | `easy` | Python: the FizzBuzz list for 1 to n. |
| `rle` | `programming` | `easy` | Python: run-length encode and decode a string. |
| `flatten` | `programming` | `easy` | Python: flatten lists nested to any depth, in order. |
| `anagram` | `programming` | `easy` | Python: group words that are anagrams of each other. |
| `wordfreq` | `programming` | `easy` | Python: the k most common words in a text, with their counts. |
| `countlines` | `programming` | `easy` | Shell: a script that prints the number of non-empty lines in a file. |
| `slugify` | `programming` | `easy` | JavaScript: turn a title into a lowercase URL slug. |
| `firstge` | `programming` | `medium` | Python: binary search for the first element that is not less than x. |
| `spiral` | `programming` | `medium` | Python: the elements of a matrix in clockwise spiral order. |
| `brackets` | `programming` | `medium` | Python: check that the brackets ()[]{} in a string match and nest correctly. |
| `merge` | `programming` | `medium` | Python: merge intervals that overlap or touch. |
| `rpn` | `programming` | `medium` | Python: evaluate a Reverse Polish Notation expression. |
| `ini` | `programming` | `medium` | Python: parse INI text into sections of keys and values. |
| `minstack` | `programming` | `medium` | Python: a stack that also returns its minimum in constant time. |
| `deepmerge` | `programming` | `medium` | JavaScript: merge two nested objects; the values of the second object win. |
| `sumargs` | `programming` | `medium` | Shell: a script that prints the sum of its integer arguments and rejects bad arguments. |
| `dedupe` | `programming` | `medium` | Python: find files with the same content anywhere under a folder. |
| `dijkstra` | `programming` | `hard` | Python: the shortest path in a weighted graph, or None. |
| `lcs` | `programming` | `hard` | Python: one longest common subsequence of two strings. |
| `fixavg` | `repair` | `medium` | Repair: fix a crash on an empty list and a wrong median in a statistics module. |
| `fixcsvsum` | `repair` | `medium` | Repair: fix a script that adds up the amount column of a CSV file. |
| `fixjs` | `repair` | `medium` | Repair (JavaScript): fix a word counter that should count lowercase words. |
| `largest` | `programming` | `medium` | Shell: a script that prints the 3 largest files under a folder. |
| `largest3` | `terminal` | `terminal` | Find the 3 largest files under a folder; write them largest first. |
| `diskfree` | `terminal` | `terminal` | Write the free space of the filesystem of the work folder, in 1K blocks. |
| `countpy` | `terminal` | `terminal` | Count the lines in all the .py files under a folder (as wc -l counts them). |
| `todos` | `terminal` | `terminal` | List every file under a folder that contains the word TODO. |
| `renamejpeg` | `terminal` | `terminal` | Rename every .jpeg file in a folder to .jpg and change nothing else. |
| `tarbackup` | `terminal` | `terminal` | Make a gzip-compressed tar archive of a folder. |
| `unzipcount` | `terminal` | `terminal` | Extract a zip archive and write how many files it held. |
| `execrun` | `terminal` | `terminal` | Make a script executable, run it and save its output. |
| `counterrors` | `terminal` | `terminal` | Count the ERROR lines in an application log. |
| `topip` | `terminal` | `terminal` | Find the client IP address with the most requests in a web log. |
| `dedupenames` | `terminal` | `terminal` | Write a list of names once each, sorted. |
| `emails` | `terminal` | `terminal` | Extract the e-mail addresses from free text, without duplicates, sorted. |
| `wordcount` | `terminal` | `terminal` | Count the words in a text file (as wc -w counts them). |
| `replaceall` | `terminal` | `terminal` | Replace foo with bar in every .txt file under a folder, and only there. |
| `csv2json` | `terminal` | `terminal` | Convert a CSV file to a JSON list of objects. |
| `jsonvalue` | `terminal` | `terminal` | Write one value from a nested JSON settings file. |
| `sortcsv` | `terminal` | `terminal` | Sort a CSV file by its score column, highest first, and keep the header. |
| `editport` | `terminal` | `terminal` | Change one line in a settings file and leave every other line as it is. |
| `pyversion` | `terminal` | `terminal` | Write the installed version of python3. |
| `gpuname` | `terminal` | `terminal` | Write the name of the GPU, as nvidia-smi reports it. |
| `cronline` | `terminal` | `terminal` | Write a crontab line that runs a script every day at 02:30. |
| `daysbetween` | `terminal` | `terminal` | Write the number of days between two dates. |
| `gitinit` | `terminal` | `terminal` | Make a folder a git repository and commit a file with a given message. |
| `hellosh` | `terminal` | `terminal` | Write a script that greets the name in an environment variable, with a default. |
| `topip_steps` | `chain` | `terminal` | Chain of 3 small prompts: the client IP address with the most requests. |
| `counterrors_steps` | `chain` | `terminal` | Chain of 2 small prompts: the number of ERROR lines in a log. |
| `topip_cmd` | `chain` | `terminal` | One prompt that asks for shell commands: the client IP address with the most requests. |
| `counterrors_cmd` | `chain` | `terminal` | One prompt that asks for shell commands: the number of ERROR lines in a log. |
| `largest3_cmd` | `chain` | `terminal` | One prompt that asks for shell commands: the 3 largest files under a folder. |
| `largest3_steps` | `chain` | `terminal` | Chain of 3 small prompts: the 3 largest files under a folder. |
| `topip_stepscmd` | `chain` | `terminal` | Chain of 3 prompts with one shell command each: the client IP address with the most requests. |
| `counterrors_stepscmd` | `chain` | `terminal` | Chain of 2 prompts with one shell command each: the number of ERROR lines in a log. |
| `largest3_stepscmd` | `chain` | `terminal` | Chain of 3 prompts with one shell command each: the 3 largest files under a folder. |

## How to read the results

`kbench report RUNID` prints three tables:

- One line for each condition: the runs, pass@1, pass-any, the passes in each tier, and the outcomes. pass@1 is
  the passed runs divided by the runs. pass-any is the tasks that passed in at least one seed, divided by the tasks.
- One line for each task: the passes out of the seeds, for each condition.
- The mechanics of each condition: the mean time, the turns, the output tokens, the cut-off replies and the tool
  errors. The last values are the kills of the watchdog and the runs that wrote files outside the work folder.

Each run has one of these outcomes:

| Outcome | Meaning |
|---|---|
| `pass` | The hidden test found no problem. |
| `wrong` | The file or the answer exists, but the hidden test found a wrong result. |
| `crash` | The hidden test stopped with an error, for example because the agent's code does not import. |
| `timeout` | The hidden test did not finish in 90 seconds. |
| `nofile` | The file that the task asks for does not exist. |

`kbench collect` gives the same numbers as JSON. It also counts false claims. In a false claim, the last message of the
agent says that the result works, passes or is correct, but the hidden test failed.

The record of each run is in `runs/RUNID/COND/TASK/sK/`:

| File | Contents |
|---|---|
| `events.jsonl` | The JSON event stream of pi: every prompt, reply, tool call and tool result |
| `tests.txt` | The output of the hidden test |
| `result.json` | The outcome, the time, the turns, the tokens and the tool counts |
| `workdir/` | The final files of the agent (caches and files larger than 10 MB are not copied) |

`runs/RUNID/manifest.json` records all the settings and the versions of kbench, pi, Node.js, Python and the OS. It
also records the GPUs and the replies of the server to `/health` and `/v1/models`. The manifest does not record the host name
or the user name. But the prompts in `events.jsonl` contain the path of the work folder, and this path can contain
your user name. Examine a run before you publish it.

Our own results, and what each file means, are in [results/README.md](results/README.md).

## License

Copyright (c) 2026 [Amir Husain](https://www.amirhusain.com). kbench is open source under the MIT License. See
[LICENSE](LICENSE). Kindi, pi and the model have their own licenses.
