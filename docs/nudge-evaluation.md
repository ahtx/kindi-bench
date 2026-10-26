# Nudge before/after agent evaluation

Run: `nudge-eval` on vanguard's Quadro K420, `bonsai2-2b`, Kindi 0.2.0-dev+6aea479, one seed.
Conditions: base and the `extensions/nudge.mjs` extension, identical task set, thinking off, 4096-token cap.
Tasks: `csvline`, `roman`, `bigmul` (all hard). Hidden tests decide pass/fail.

## Outcome

| Metric | Base | Nudged |
|---|---:|---:|
| Tasks passed | 0/3 | 0/3 |
| pass@1 | 0.0% | 0.0% |
| Outcomes | nofile 2, crash 1 | nofile 3 |
| Mean wall time / run | 406 s | 183 s |
| Turns | 85 | 44 |
| Output tokens | 11,837 | 3,973 |
| Tool errors | 29 | 13 |
| Cut-off replies | 0 | 0 |

**Task-success efficacy is not demonstrated.** The nudge did not turn any failing task into a pass. Efficiency
improved substantially (55% fewer tool errors, 55% less wall time, 66% fewer output tokens), but three tasks are
too few to claim a general improvement. Online learning stays off. A larger mixed-tier benchmark is needed before
promoting a correction based on these results.

Raw collection: `docs/nudge-eval-results.json`. Extension: `extensions/nudge.mjs`.
