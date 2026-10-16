# Recorded Experiment Report

Experiment date: 2026-10-06. Python 3.12.7, NumPy 1.26.4, SciPy 1.13.1.

HiGHS diagnostic output, enabled separately with disp, confirmed bundled HiGHS version 1.2.0 in the experiment environment.

Zero-target filtering retains 11,453 candidates, matching the active persona count on page 15 of the research attachment. Input consistency checks are necessary conditions only.

## pure

Full command:

```powershell
python -m synthpop experiment --seeds 0,1,2 --seconds 12.0 --restarts 2 --backtracks 100 --out results/pure
```

| Method | Seed | Success | Population | Violated constraints | L1 error | Max error | D (feasible only) | H (feasible only) | Solve seconds | Individuals undone | Restarts | Exact seconds |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random | 0 | False | 135 | 368 | 16425 | 361 | - | - | 1.817 | 100 | 2 | 0.000 |
| random | 1 | False | 161 | 350 | 15255 | 335 | - | - | 2.162 | 100 | 2 | 0.000 |
| random | 2 | False | 183 | 352 | 14265 | 313 | - | - | 2.368 | 100 | 2 | 0.000 |
| greedy | 0 | False | 287 | 395 | 9585 | 206 | - | - | 12.006 | 100 | 2 | 0.000 |
| greedy | 1 | False | 287 | 395 | 9585 | 206 | - | - | 10.987 | 100 | 2 | 0.000 |
| greedy | 2 | False | 307 | 384 | 8685 | 186 | - | - | 12.001 | 100 | 2 | 0.000 |

Shared preprocessing: 0.6177 seconds (performed once per experiment).

- random success rate: 0/3; feasible-only mean D=None, mean H=None.
- greedy success rate: 0/3; feasible-only mean D=None, mean H=None.

## hybrid

Full command:

```powershell
python -m synthpop experiment --seeds 0,1,2 --seconds 60.0 --restarts 2 --backtracks 1000 --out results/hybrid --exact --exact-at 300 --exact-seconds 8.0 --rollback 75
```

| Method | Seed | Success | Population | Violated constraints | L1 error | Max error | D (feasible only) | H (feasible only) | Solve seconds | Individuals undone | Restarts | Exact seconds |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random | 0 | False | 35 | 411 | 20925 | 458 | - | - | 61.538 | 134 | 0 | 60.439 |
| random | 1 | False | 52 | 398 | 20160 | 443 | - | - | 62.370 | 192 | 0 | 60.881 |
| random | 2 | False | 29 | 424 | 21195 | 464 | - | - | 60.592 | 136 | 0 | 59.417 |
| greedy | 0 | True | 500 | 0 | 0 | 0 | 193 | 4.664782 | 34.703 | 300 | 0 | 29.478 |
| greedy | 1 | True | 500 | 0 | 0 | 0 | 191 | 4.717455 | 15.787 | 150 | 0 | 12.368 |
| greedy | 2 | True | 500 | 0 | 0 | 0 | 190 | 4.637186 | 16.532 | 150 | 0 | 13.253 |

Shared preprocessing: 0.6325 seconds (performed once per experiment).

- random success rate: 0/3; feasible-only mean D=None, mean H=None.
- greedy success rate: 3/3; feasible-only mean D=191.33333333333334, mean H=4.67314145209518.

## hybrid_long_calls

Full command:

```powershell
python -m synthpop experiment --seeds 0,1,2 --seconds 65.0 --restarts 2 --backtracks 1000 --out results/hybrid_long_calls --exact --exact-at 300 --exact-seconds 55.0 --rollback 500
```

| Method | Seed | Success | Population | Violated constraints | L1 error | Max error | D (feasible only) | H (feasible only) | Solve seconds | Individuals undone | Restarts | Exact seconds |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random | 0 | True | 500 | 0 | 0 | 0 | 137 | 4.079469 | 55.838 | 17 | 0 | 55.650 |
| random | 1 | True | 500 | 0 | 0 | 0 | 139 | 4.147284 | 55.449 | 31 | 0 | 55.178 |
| random | 2 | True | 500 | 0 | 0 | 0 | 136 | 3.912961 | 55.359 | 29 | 0 | 55.092 |
| greedy | 0 | True | 500 | 0 | 0 | 0 | 138 | 4.125527 | 57.330 | 200 | 0 | 55.264 |
| greedy | 1 | True | 500 | 0 | 0 | 0 | 139 | 4.109473 | 53.404 | 200 | 0 | 51.460 |
| greedy | 2 | True | 500 | 0 | 0 | 0 | 135 | 4.185341 | 51.497 | 200 | 0 | 49.513 |

Shared preprocessing: 0.6765 seconds (performed once per experiment).

- random success rate: 3/3; feasible-only mean D=137.33333333333334, mean H=4.046570974754079.
- greedy success rate: 3/3; feasible-only mean D=137.33333333333334, mean H=4.140113744900287.

## Full Integer-Programming Control

Command: `python -m synthpop solve --exact --exact-at 500 --seconds 45 --exact-seconds 40 --out results/full_exact`.

Independent verification passed: 500 individuals, 729/729 constraints satisfied; D=138, H=3.981021; solve time 40.786 seconds. The solver reached its time limit with a feasible incumbent, without proving linear-objective optimality. This run used no greedy prefix.

## Default Deliverable and Limitations

The default results/final population comes from `results/hybrid/greedy_1`, selected by the highest observed H: N=500, all constraint errors zero, D=191, duplicate individuals=309, maximum persona multiplicity=24, H=4.717455425 nats.

The highest observed D is 193, from `results/hybrid/greedy_0`, with H=4.664782465. D and H are selected and reported separately.

These are observed feasible solutions, without a global optimality proof for D or H. Exact-completion status=0 applies only to the linear surrogate objective; full completion or completion with a prefix does not prove optimality for the original diversity objectives.

The three-seed results apply only to the recorded parameters and do not establish general algorithm success rates. Incomplete pure-mode populations are excluded from feasible diversity comparisons. Hybrid mode includes exact repair, so its success cannot be attributed to pure greedy construction.

Some experiments ran concurrently and shared CPU resources. The timings document actual execution rather than isolated performance benchmarks. Time limits are soft, and solver shutdown can cause small overruns. Failed prefixes remain in their run directories and are explicitly marked success=false.

All 7 unittest tests passed, including a locally consistent but globally infeasible counterexample. Every experiment population is independently rechecked from CSV when this report is generated.
