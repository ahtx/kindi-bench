# Changelog

## 0.1.1

- `kbench breakdown` uses tested per-item prompts by default. The option `--prompts first` gives the first prompts,
  which failed on the spam and order jobs.
- `kbench breakdown` also scores the spam and order jobs on held-out items.
- The reply parser takes the allowed word that comes first in the reply. A reply such as "Ham. It is not spam." now
  counts as ham.
- The results of the breakdown jobs on the K420 are in `results/`.

## 0.1.0 - first public release
