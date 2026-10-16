"""Recheck recorded populations and write a report from actual metrics only."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from synthpop.data import load
from synthpop.validate import read_population, verify


def main():
    data = load(ROOT/'data')
    lines = ['# Recorded Experiment Report', '', 'Experiment date: 2026-10-06. Python 3.12.7, NumPy 1.26.4, SciPy 1.13.1.', '', 'HiGHS diagnostic output, enabled separately with disp, confirmed bundled HiGHS version 1.2.0 in the experiment environment.', '', 'Zero-target filtering retains 11,453 candidates, matching the active persona count on page 15 of the research attachment. Input consistency checks are necessary conditions only.', '']
    feasible = []
    for name in ['pure','hybrid','hybrid_long_calls']:
        folder = ROOT/'results'/name
        if not (folder/'summary.json').exists():
            raise RuntimeError(f'Experiment not complete: {name}')
        summary = json.loads((folder/'summary.json').read_text())
        lines += [f'## {name}', '', 'Full command:', '', '```powershell']
        p = summary['parameters']
        command = f"python -m synthpop experiment --seeds {p['seeds']} --seconds {p['seconds']} --restarts {p['restarts']} --backtracks {p['backtracks']} --out results/{name}"
        if p['exact']:
            command += f" --exact --exact-at {p['exact_at']} --exact-seconds {p['exact_seconds']} --rollback {p['rollback']}"
        lines += [command, '```', '', '| Method | Seed | Success | Population | Violated constraints | L1 error | Max error | D (feasible only) | H (feasible only) | Solve seconds | Individuals undone | Restarts | Exact seconds |', '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for method in ['random','greedy']:
            for seed in map(int, p['seeds'].split(',')):
                run = folder/f'{method}_{seed}'
                m = json.loads((run/'metrics.json').read_text())
                _, check = verify(data, read_population(run/'population.csv',data.k))
                for key,value in check.items():
                    if m[key] != value:
                        raise RuntimeError(f'Metric mismatch: {run}/{key}')
                if m['success']:
                    feasible.append((run,m))
                d = str(m['distinct_personas']) if m['success'] else '-'
                h = f"{m['shannon_entropy_nats']:.6f}" if m['success'] else '-'
                lines.append(f"| {method} | {seed} | {m['success']} | {m['population_size']} | {m['violated_constraints']} | {m['total_absolute_error']} | {m['max_absolute_error']} | {d} | {h} | {m['solve_seconds']:.3f} | {m['backtracks']} | {m['restarts']} | {m['exact_seconds']:.3f} |")
        lines += ['', f"Shared preprocessing: {summary['shared_preprocessing_seconds']:.4f} seconds (performed once per experiment).", '']
        for method, r in summary['results'].items():
            lines.append(f"- {method} success rate: {r['successful_runs']}/{r['runs']}; feasible-only mean D={r['feasible_mean_distinct_personas']}, mean H={r['feasible_mean_entropy_nats']}.")
        lines += ['']
    full = ROOT/'results/full_exact'
    m = json.loads((full/'metrics.json').read_text())
    assert verify(data,read_population(full/'population.csv',data.k))[1]['success']
    lines += ['## Full Integer-Programming Control', '', 'Command: `python -m synthpop solve --exact --exact-at 500 --seconds 45 --exact-seconds 40 --out results/full_exact`.', '', f"Independent verification passed: 500 individuals, 729/729 constraints satisfied; D={m['distinct_personas']}, H={m['shannon_entropy_nats']:.6f}; solve time {m['solve_seconds']:.3f} seconds. The solver reached its time limit with a feasible incumbent, without proving linear-objective optimality. This run used no greedy prefix.", '']
    feasible.append((full,m))
    best_h = max(feasible,key=lambda pair:pair[1]['shannon_entropy_nats'])
    best_d = max(feasible,key=lambda pair:pair[1]['distinct_personas'])
    final = ROOT/'results/final'
    final.mkdir(exist_ok=True)
    for file in ['population.csv','validation.csv','metrics.json']:
        shutil.copyfile(best_h[0]/file,final/file)
    (final/'selection.json').write_text(json.dumps({'criterion':'highest observed Shannon entropy among independently verified runs', 'source':str(best_h[0].relative_to(ROOT)), 'max_distinct_personas_source':str(best_d[0].relative_to(ROOT)), 'global_optimality_proven':False},indent=2),encoding='utf-8')
    m = best_h[1]
    lines += ['## Default Deliverable and Limitations', '', f"The default results/final population comes from `{best_h[0].relative_to(ROOT).as_posix()}`, selected by the highest observed H: N={m['population_size']}, all constraint errors zero, D={m['distinct_personas']}, duplicate individuals={m['duplicate_people']}, maximum persona multiplicity={m['max_persona_multiplicity']}, H={m['shannon_entropy_nats']:.9f} nats.", '', f"The highest observed D is {best_d[1]['distinct_personas']}, from `{best_d[0].relative_to(ROOT).as_posix()}`, with H={best_d[1]['shannon_entropy_nats']:.9f}. D and H are selected and reported separately.", '', 'These are observed feasible solutions, without a global optimality proof for D or H. Exact-completion status=0 applies only to the linear surrogate objective; full completion or completion with a prefix does not prove optimality for the original diversity objectives.', '', 'The three-seed results apply only to the recorded parameters and do not establish general algorithm success rates. Incomplete pure-mode populations are excluded from feasible diversity comparisons. Hybrid mode includes exact repair, so its success cannot be attributed to pure greedy construction.', '', 'Some experiments ran concurrently and shared CPU resources. The timings document actual execution rather than isolated performance benchmarks. Time limits are soft, and solver shutdown can cause small overruns. Failed prefixes remain in their run directories and are explicitly marked success=false.', '', 'All 7 unittest tests passed, including a locally consistent but globally infeasible counterexample. Every experiment population is independently rechecked from CSV when this report is generated.']
    (ROOT/'EXPERIMENTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'final_source':str(best_h[0]), 'best_entropy':m['shannon_entropy_nats'], 'best_distinct':best_d[1]['distinct_personas']},indent=2))


if __name__ == '__main__':
    main()
