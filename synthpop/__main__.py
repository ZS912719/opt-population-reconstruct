import argparse
import json
import platform
import time
from dataclasses import asdict
from pathlib import Path
import numpy as np
from .data import load
from .candidates import Candidates
from .solver import Config, solve
from .validate import verify, read_population, write_population, write_csv


def main():
    p = argparse.ArgumentParser(description='Exact marginal population reconstruction')
    p.add_argument('command', choices=['solve','experiment','validate'])
    p.add_argument('--data', default='data')
    p.add_argument('--out', default='results/run')
    p.add_argument('--population')
    p.add_argument('--k', type=int, default=12)
    p.add_argument('--n', type=int, default=500)
    p.add_argument('--method', choices=['random','greedy'], default='greedy')
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--seeds', default='0,1,2')
    for name, default, typ in [('seconds',30,float),('restarts',2,int),('backtracks',100,int),('top',8,int),('alpha',1,float),('beta',1,float),('exact-at',100,int),('exact-seconds',10,float),('rollback',25,int)]:
        p.add_argument('--'+name, default=default, type=typ)
    p.add_argument('--exact', action='store_true')
    p.add_argument('--capacity', action='store_true')
    args = p.parse_args()
    if args.n <= 0 or args.k <= 0 or args.seconds <= 0 or args.exact_seconds <= 0 or args.top <= 0 or args.rollback <= 0 or min(args.restarts,args.backtracks,args.exact_at,args.alpha,args.beta) < 0:
        p.error('Invalid nonpositive budget/size or negative parameter')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    data = load(args.data, args.k, args.n)
    load_seconds = time.perf_counter()-start
    if args.command == 'validate':
        if not args.population:
            p.error('--population required')
        validation, metrics = verify(data, read_population(args.population, data.k))
        write_csv(out/'validation.csv', list(validation[0]), validation)
        (out/'metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
        print(json.dumps(metrics))
        return 0 if metrics['success'] else 2
    candidates = Candidates(data)
    def run(method, seed, folder):
        folder.mkdir(parents=True, exist_ok=True)
        cfg = Config(**{key:getattr(args,key) for key in asdict(Config())})
        cfg.method, cfg.seed = method, seed
        population, info = solve(data, candidates, cfg)
        # Validate the serialized population, independently of internal counters.
        write_population(folder/'population.csv', population, data.k)
        validation, metrics = verify(data, read_population(folder/'population.csv', data.k))
        info.update(metrics)
        if metrics['success']:
            info['termination_status'] = 'success_independently_verified'
        info.update(preprocessing_seconds=load_seconds+candidates.seconds, load_seconds=load_seconds, candidate_seconds=candidates.seconds, candidate_count=len(candidates.x), memory_bytes=candidates.memory, python_version=platform.python_version(), numpy_version=np.__version__, necessary_consistency_checks_passed=True, global_feasibility_proven_by_prechecks=False)
        write_csv(folder/'validation.csv', list(validation[0]), validation)
        (folder/'metrics.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
        print(json.dumps({key: info[key] for key in ['success','termination_status','population_size','distinct_personas','shannon_entropy_nats','solve_seconds']}, ensure_ascii=False), flush=True)
        return info
    if args.command == 'solve':
        result = run(args.method, args.seed, out)
        return 0 if result['success'] else 2
    results = []
    seeds = [int(s) for s in args.seeds.split(',')]
    if len(set(seeds)) != len(seeds):
        p.error('Experiment seeds must be distinct')
    for method in ['random','greedy']:
        for seed in seeds:
            info = run(method, seed, out/f'{method}_{seed}')
            results.append({'method':method,'seed':seed, **{key:info[key] for key in ['success','population_size','violated_constraints','total_absolute_error','max_absolute_error','distinct_personas','duplicate_people','max_persona_multiplicity','shannon_entropy_nats','preprocessing_seconds','solve_seconds','backtracks','restarts','exact_seconds','termination_status']}})
    write_csv(out/'summary.csv', list(results[0]), results)
    summary = {}
    for method in ['random','greedy']:
        runs = [r for r in results if r['method'] == method]
        feasible = [r for r in runs if r['success']]
        summary[method] = {'runs':len(runs),'successful_runs':len(feasible),'success_rate':len(feasible)/len(runs), 'feasible_mean_distinct_personas':float(np.mean([r['distinct_personas'] for r in feasible])) if feasible else None, 'feasible_mean_entropy_nats':float(np.mean([r['shannon_entropy_nats'] for r in feasible])) if feasible else None}
    (out/'summary.json').write_text(json.dumps({'parameters':vars(args),'shared_preprocessing_seconds':load_seconds+candidates.seconds,'results':summary}, indent=2), encoding='utf-8')
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
