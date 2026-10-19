# Results

These files are the results of our runs with Ternary-Bonsai-2-2B. We measured on two setups:

- **K420**: a Quadro K420 with Kindi 0.1.0. Kindi serves one request at a time.
- **3080**: two RTX 3080 cards with llama.cpp `llama-server`, with the same model file and the sampling values of
  Kindi (temperature 0.7, top-p 0.8, top-k 20).

The agent was pi 1.3.0 with the configuration that `kbench run` writes. The full report is at
[amirhusain.com/kindi](https://www.amirhusain.com/kindi).

| File | Setup | Contents |
|---|---|---|
| `results.json` | 3080 and K420 | `kbench collect` output for five runs (see below) |
| `k420.json` | K420 | One agent run for each of 13 programming and repair tasks: 8 hard tasks and 5 easier tasks |
| `jobs-desk.json` | 3080 | `kbench textjobs` output: every item, the reply of the model, the score and the time |
| `jobs-k420.json` | K420 | `kbench textjobs` output, with the same items |
| `escalate-variants.json` | 3080 | The escalate job with three different prompts: correct answers, missed escalations and false alarms out of 30 |
| `escalate-safe-k420.json` | K420 | The escalate job with the prompt that adds "When you are not sure, answer yes." Each row has the message, the correct answer, the reply and the time in seconds. |
| `quiz.json` | K420 | The 12 questions in `kbench/tasks/quiz.py`: the number of correct answers for each method |
| `breakdown-k420.json` | K420 | `kbench breakdown` output with the first prompts: for each job, 3 agent runs, 3 one-prompt runs and the broken-down run |
| `breakdown-broken-k420.json` | K420 | The broken-down runs again with the fixed reply parser (first prompts) |
| `breakdown-fix-k420.json` | K420 | The spam and order jobs with the tested prompts, on the original items and on held-out items |
| `wf-k420.json` | K420 | The output of a small workflow program: the program counts and sorts, and the model writes only the words. The file has the time of each model call, the facts, the summary and the message rows. |

## The runs in results.json

| Run id | Setup | Tasks | Seeds | Conditions |
|---|---|---|---|---|
| `r2` | 3080 | the 32 `programming` and `repair` tasks | 3 | `base`, `think`, `base8k`, `ext`, `ext_think` |
| `t3` | 3080 | the 24 `terminal` tasks | 5 | `base`, `think`, `base8k`, `ext`, `ext_think` |
| `t3steps` | 3080 | `topip_steps`, `counterrors_steps`, `largest3_steps` | 5 | `base8k`, `think`, `ext_think` |
| `t3cmd` | 3080 | the three `_cmd` tasks and the three `_stepscmd` tasks | 5 | `base8k`, `think` |
| `k420-t3` | K420 | the 24 `terminal` tasks | 1 | `think` |

For each run and condition, `results.json` gives:

| Key | Meaning |
|---|---|
| `runs`, `pass` | The number of runs, and the number of runs that passed the hidden test |
| `outcomes` | The number of runs with each outcome: `pass`, `wrong`, `crash`, `timeout`, `nofile` |
| `false_claims` | Runs where the last message of the agent said that the result was correct, but the hidden test failed |
| `mean_secs` | The mean time of a run, in seconds |
| `pass_any`, `n_tasks` | The tasks that passed in at least one seed, and the number of tasks |
| `tasks` | Runs and passes for each task |

The `ext` and `ext_think` runs used an experimental pi extension. This release does not include that extension, so
you cannot repeat those two conditions. You can repeat all the other runs with `kbench run`.

## Notes

- In `k420.json`, the tier `easy` marks the five easier tasks of that run. The task list of kbench puts `fixavg` and
  `sumargs` in the `medium` tier. A time of 1800 seconds means that the agent session reached its time limit.
- The `hellosh` test now uses the name Sam in its check. The logic of the test did not change.
- The `gpuname` task asks for the name of the GPU. Its answer is different on each machine. The hidden test reads the
  correct answer from `nvidia-smi` on the same machine.
- The text items and the breakdown items are fictional. We wrote them for this benchmark.
