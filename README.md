# Synthetic Population Reconstruction

**English** | [简体中文](README.zh-CN.md)

A Python project for constructing an integer population that exactly matches supplied marginal counts. It combines urgency-based greedy construction, lookahead, bounded backtracking, random restarts, and optional mixed-integer completion. A random legal-candidate baseline provides a comparison.

Matching these marginals produces a compatible synthetic population. **It does not recover the original population**, which is not included in the inputs.

## Problem

Construct exactly **500 individuals**. Each individual has 12 categorical attributes, `A0` through `A11`, with values `v0`, `v1`, or `v2`. A complete assignment is a *persona*, and multiple individuals may share one persona.

The input contains 45 marginal tables: 12 unary, 20 binary, 10 ternary, and 3 four-way tables, totaling **729 count constraints**. Every cell must match its integer target exactly; approximate agreement is not success.

Two diversity measures are reported separately:

- **Distinct personas, D:** the number of different complete attribute assignments.
- **Shannon entropy, H:** `-sum(p_x * ln(p_x))`, using natural logarithms, where `p_x` is the fraction of individuals with persona x.

Maximizing D and maximizing H are different objectives. The greedy repetition penalty encourages entropy; this implementation does not prove a global optimum for either measure. Personality modeling and LLM-based agents discussed in the research background are outside this project's scope.

## Requirements and installation

Use **Python 3.10 or newer**. NumPy is required; SciPy, with its bundled HiGHS solver, is optional and used only for exact completion. Pure greedy and random modes can run without SciPy. No separate HiGHS installation is required when using the SciPy backend.

Run these commands from the repository root. A virtual environment is recommended:

```powershell
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS shells: source .venv/bin/activate
python -m pip install -r requirements.txt
# Optional exact-completion dependency
python -m pip install -r requirements-exact.txt
python -m unittest discover -s tests -v
```

The recorded experiments used Python 3.12.7, NumPy 1.26.4, SciPy 1.13.1, and bundled HiGHS 1.2.0, confirmed separately through solver diagnostic output. To install the recorded Python package versions, use `python -m pip install -r requirements-tested.txt`. Timing and solver behavior can vary across environments and versions.

## Running the project

### Pure greedy or random baseline

```powershell
python -m synthpop solve --method greedy --seed 0 --seconds 30 --out results/run
python -m synthpop solve --method random --seed 0 --seconds 30 --out results/random_run
```

For a single random construction without recovery, add `--backtracks 0 --restarts 0`. A pure run may stop with an incomplete population.

### Greedy construction with exact completion

```powershell
python -m synthpop solve --method greedy --seed 1 --exact --seconds 60 --exact-at 300 --exact-seconds 8 --backtracks 1000 --rollback 75 --out results/run_exact
python -m synthpop validate --population results/run_exact/population.csv --out results/checked
```

This is the configuration of the highest-entropy recorded run. A fixed seed controls NumPy random choices; it does not guarantee identical time-limited solver results across machines.

### Multi-seed experiments

```powershell
python -m synthpop experiment --seeds 0,1,2 --seconds 12 --out results/new_pure
python -m synthpop experiment --seeds 0,1,2 --exact --seconds 60 --exact-at 300 --exact-seconds 8 --backtracks 1000 --rollback 75 --out results/new_hybrid
```

`experiment` runs both methods with the selected seeds and budgets. Use new output directories to preserve recorded results. `solve` and `validate` return exit code 0 only for an independently verified complete population, or 2 on failure. For `experiment`, exit code 0 means the experiment finished; inspect its success rates to determine which runs succeeded. Run `python -m synthpop --help` for all options. The default instance is `--k 12 --n 500`; smaller instances can override these values.

To run a complete integer-programming control without a greedy prefix:

```powershell
python -m synthpop solve --exact --exact-at 500 --seconds 45 --exact-seconds 40 --out results/new_full_exact
```

## Input format and checks

The supplied CSV files are copied unchanged into [data/](data/):

| File | Fields |
|---|---|
| `constraint_scopes.csv` | `table_id, arity, scope, num_cells, target_sum` |
| `constraint_cells.csv` | `cell_id, table_id, arity, scope, cell, target` |

CSV delimiters are detected with `csv.Sniffer` from comma, tab, and semicolon. In the supplied files, the outer delimiter is a comma, scopes use `|`, and cell assignments use `;` and `=`. For example, scope `A2|A3` can have cell `A2=v0;A3=v1`. Assignment order may differ from scope order.

The loader checks unique IDs, valid references, attributes and values, nonnegative integer targets, table metadata, complete cell combinations, a total of N in every table, and agreement of overlapping projections. All attributes must be covered. **These are necessary checks, not a proof of global feasibility.** A test includes locally consistent marginals that are globally infeasible.

## Algorithm

### 1. Candidate preprocessing

Enumerate all `3^12 = 531,441` personas and remove any matching a zero-target cell. This instance retains **11,453 candidates**. Precompute each candidate's matching cell in every table and build a cell-to-candidate reverse index.

The persistent attribute matrix, matching matrix, reverse offsets, and reverse candidate IDs occupy **3,235,586 bytes, about 3.09 MiB**. Enumeration uses additional temporary arrays; an int64 broadcast intermediate alone is about 48.66 MiB. Solver matrices and internal solver storage require further memory. These are array-size estimates, not measured peak process memory.

### 2. Greedy selection

Maintain remaining cell demand `r_c`, selected persona counts `n_x`, and the selected population. A candidate is legal only if every cell it matches has positive remaining demand. Adding one individual subtracts one from its matching cell in each table.

Let `q_c` be the number of distinct currently legal candidates supporting cell c. For positive remaining demand, urgency is `u_c = r_c / q_c`. Positive demand with no support triggers recovery. Since repetitions are allowed, **r_c > q_c is not an infeasibility test**.

Choose a most urgent positive-demand cell, then rank its legal supporters using:

```text
S(x) = beta * sum(u_c matched by x) / demand_scale
       - alpha * [(n_x + 1) ln(n_x + 1) - n_x ln(n_x)] / (ln(N) + 1)
```

Here `0 ln(0) = 0`, and `demand_scale` is the number of tables times the mean urgency over all positive-demand cells. This gives a typical demand score near one and a maximum repetition penalty near one, making alpha and beta comparable weights. Scores are quantized at `1e-7`, with random tie-breaking. The repetition increment corresponds to the entropy objective at fixed final N; it is not a separate exact optimization of D.

### 3. Lookahead and bounded recovery

Simulate up to `--top` ranked candidates per round. Reject a trial if it creates negative demand or leaves any positive-demand cell without legal support. With `--capacity`, also require the sum of supporting candidate bounds `U_x = min(r_c matched by x)` to cover each cell's remaining demand. Passing these checks does not establish residual feasibility.

State updates are reversible. Failed choices are banned at the current search depth; child-depth bans are cleared when backing up. Wall-clock, backtracking, and restart budgets bound the search. The backtracking count measures individuals undone, including batch rollback, and excludes lookahead simulations.

The baseline samples uniformly from all currently legal candidates. It does not use urgency, repetition scoring, or lookahead, but can use the same recovery and optional exact-completion settings.

### 4. Optional exact completion

For every legal candidate, introduce a nonnegative integer variable `z_x` with upper bound `min(r_c matched by x)`, and impose `M z = r` for every cell. Completion starts at `--exact-at` remaining individuals or at a dead end. Its linear cost is the current persona count plus a small random perturbation: a repetition preference, **not an exact entropy or distinct-persona objective**.

Only a solver proof of residual infeasibility triggers batch rollback of up to `--rollback` individuals. A timeout or unknown status is not treated as infeasibility; ordinary greedy search and dead-end recovery may continue. A time-limited call may still provide a feasible incumbent, which is accepted only after integer and equality checks.

SciPy status 0 proves optimality only for this linear surrogate; status 1 indicates a limit, and status 2 indicates infeasibility. Raw statuses and messages are recorded. Final success always requires independent verification of the saved CSV. See the [SciPy MILP interface](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html).

Time limits are soft: preprocessing is separate, and native solver startup, shutdown, or an array operation can cause a small overrun.

## Outputs and verification

| Output | Contents |
|---|---|
| `population.csv` | One individual per row, with attributes `A0` through `A11` |
| `validation.csv` | Every constraint's target, actual count, and difference |
| `metrics.json` | Population size, errors, D, duplicates, maximum multiplicity, H, timings, budgets, seed, recovery counts, and termination status |
| `summary.csv` / `summary.json` | Multi-seed results and feasible-only diversity averages |

The verifier reads the saved population and recounts all marginals directly from attribute rows, without candidate lookup caches or solver residual counts. Incomplete or invalid populations remain explicitly unsuccessful. Diversity averages include only verified feasible runs; if none succeeded, the averages are null.

The default delivered population is in [results/final/](results/final/). It has **500 individuals, 729/729 exact constraints, D=191, 309 duplicate individuals, maximum multiplicity 24, and H=4.717455 nats**. Every count error is zero. The recorded maximum D is **193**, with H=4.664782, from a different run.

## Difficulties encountered and recorded results

1. **Local consistency does not ensure a feasible completion.** Pure runs exhausted recovery or time budgets despite valid inputs. Greedy prefixes can block all global completions; lookahead catches only some such failures.
2. **Short exact calls often end without a decision.** Eight-second completion calls sometimes timed out. The implementation preserves the distinction between proven infeasibility, unknown status, and a verified feasible incumbent.
3. **Recovery choices change the result.** Rolling back a shorter prefix preserves more greedy decisions; rolling back the whole prefix can turn the run into a full integer-programming solve and lose the greedy diversity benefit. Longer calls are not automatically better for diversity.
4. **D and H select different runs.** The observed maximum-D run is different from the maximum-H run. The linear completion objective also differs from both measures, so solver optimality does not settle either diversity objective.
5. **Performance comparisons need context.** Some experiments ran concurrently and shared CPU resources. The timings are recorded execution evidence, not an isolated performance benchmark; three seeds do not establish general success probabilities.

| Recorded configuration | Random success | Greedy success |
|---|---:|---:|
| Pure; 12-second solve budget | 0/3 | 0/3 |
| Hybrid; 60 seconds, 8-second exact calls, rollback 75 | 0/3 | 3/3 |
| Hybrid; 65 seconds, 55-second exact calls, rollback 500 | 3/3 | 3/3 |

In the main hybrid experiment, feasible greedy results averaged D=191.333333 and H=4.673141. With longer calls and full rollback, both methods averaged D=137.333333; random H averaged 4.046571 and greedy H averaged 4.140114. No global diversity or entropy optimum is claimed.

Full commands, per-seed metrics, and limitations are preserved in [EXPERIMENTS.md](EXPERIMENTS.md), currently in Chinese, and the machine-readable summaries under [results/](results/). `python scripts/report.py` rechecks the three recorded experiment groups, regenerates that report, and selects the observed highest-entropy feasible run for `results/final/`. It expects the delivered directory layout and updates those report and selection artifacts.

## Project layout and contribution language

| Module | Responsibility |
|---|---|
| `synthpop/data.py` | CSV loading and necessary consistency checks |
| `synthpop/candidates.py` | Enumeration, zero filtering, indexes, reversible state |
| `synthpop/solver.py` | Random baseline, greedy scoring, lookahead, recovery |
| `synthpop/exact.py` | Optional integer completion and solver status handling |
| `synthpop/validate.py` | Independent population recount and CSV output |
| `synthpop/__main__.py` | CLI, metrics, and experiments |
| `tests/test_project.py` | Parsing, zero exclusion, state restoration, known feasible/infeasible cases, repeated personas, and optional exact completion |

All commit messages, code comments, and docstrings must be written in **English**. Documentation may have separate language editions. See [CONTRIBUTING.md](CONTRIBUTING.md).
