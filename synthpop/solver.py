import time
from dataclasses import dataclass, asdict
import numpy as np
from .candidates import State
from .exact import complete


@dataclass
class Config:
    method: str = 'greedy'
    seed: int = 0
    seconds: float = 30
    restarts: int = 2
    backtracks: int = 100
    top: int = 8
    alpha: float = 1.0
    beta: float = 1.0
    capacity: bool = False
    exact: bool = False
    exact_at: int = 100
    exact_seconds: float = 10
    rollback: int = 25


def solve(data, candidates, config):
    start = time.perf_counter()
    deadline = start + config.seconds
    rng = np.random.default_rng(config.seed)
    info = {'parameters': asdict(config), 'backtracks': 0, 'restarts': 0, 'exact_calls': [], 'exact_seconds': 0.0}
    best = []
    reason = 'restart_budget_exhausted'
    for restart in range(config.restarts+1):
        if time.perf_counter() >= deadline:
            reason = 'time_limit'
            break
        info['restarts'] = restart
        state = State(data, candidates)
        # Per-prefix bans avoid immediately revisiting a failed branch.
        bans = {}
        exact_attempted = set()
        repair = False
        while len(state.chosen) < data.n and time.perf_counter() < deadline:
            depth = len(state.chosen)
            if depth > len(best):
                best = state.chosen.copy()
            remaining = data.n-depth
            if config.exact and (remaining <= config.exact_at or repair) and tuple(state.chosen) not in exact_attempted:
                exact_attempted.add(tuple(state.chosen))
                extension, log = complete(state, min(config.exact_seconds, max(0.001, deadline-time.perf_counter())), rng)
                log['prefix_length'] = depth
                info['exact_calls'].append(log)
                info['exact_seconds'] += log['seconds']
                if extension is not None:
                    for x in extension:
                        state.add(x)
                    break
                if log['status'] == 'dependency_missing':
                    reason = 'exact_dependency_missing'
                    break
                if log['status'] == 'infeasible' and depth == 0:
                    info.update(termination_status='global_infeasible_proven', solve_seconds=time.perf_counter()-start)
                    return candidates.x[best], info
                if log['status'] == 'infeasible' and depth:
                    count = min(config.rollback, depth, config.backtracks-info['backtracks'])
                    if not count:
                        reason = 'backtrack_budget_exhausted'
                        break
                    for _ in range(count):
                        state.undo()
                    info['backtracks'] += count
                    bans = {d:b for d,b in bans.items() if d <= len(state.chosen)}
                    repair = True
                    continue
                repair = False
            legal = state.legal()
            q = state.support(legal)
            choices = np.flatnonzero(legal)
            if np.any((state.r > 0) & (q == 0)):
                choices = np.array([], dtype=int)
            if config.method == 'greedy' and len(choices):
                urgency = np.divide(state.r, q, out=np.zeros(len(q)), where=q > 0)
                positive = np.flatnonzero(state.r > 0)
                maximum = urgency[positive].max()
                pivot = rng.choice(positive[np.isclose(urgency[positive], maximum, rtol=1e-7, atol=1e-12)])
                choices = candidates.supporters(pivot)
                choices = choices[legal[choices]]
                n = state.counts[choices]
                penalty = (n+1)*np.log(n+1)-n*np.log(np.maximum(n, 1))
                demand = urgency[candidates.match[choices]].sum(axis=1)
                # Mean urgency makes a typical demand score ~1; max entropy increment
                # makes alpha=1 a worst-case one-unit repetition cost.
                scale = len(data.tables)*urgency[positive].mean()
                score = config.beta*demand/max(scale, 1e-15)-config.alpha*penalty/(np.log(data.n)+1)
                # 1e-7 score quantization defines approximate ties; random secondary key.
                order = np.lexsort((rng.random(len(score)), -np.round(score/1e-7)))
                choices = choices[order]
            elif len(choices):
                choices = rng.permutation(choices)
            choices = [int(x) for x in choices if int(x) not in bans.get(depth, set())]
            accepted = False
            # The baseline samples any legal candidate without lookahead.
            for x in choices[:config.top if config.method == 'greedy' else 1]:
                state.add(x)
                if config.method == 'random' or state.check(config.capacity):
                    accepted = True
                    break
                state.undo()
                bans.setdefault(depth, set()).add(x)
            if accepted:
                continue
            if choices and config.method == 'greedy':
                # More alternatives can be examined in the next iteration, bounded by time.
                continue
            if config.exact and tuple(state.chosen) not in exact_attempted:
                repair = True
                continue
            if not depth or info['backtracks'] >= config.backtracks:
                reason = 'dead_end_or_backtrack_budget'
                break
            failed = state.undo()
            info['backtracks'] += 1
            bans.setdefault(depth-1, set()).add(failed)
            bans = {d:b for d,b in bans.items() if d < depth}
        if len(state.chosen) > len(best):
            best = state.chosen.copy()
        if len(state.chosen) == data.n:
            best = state.chosen.copy()
            reason = 'complete_pending_independent_validation'
            break
        if time.perf_counter() >= deadline:
            reason = 'time_limit'
            break
    info.update(termination_status=reason, solve_seconds=time.perf_counter()-start)
    return candidates.x[best], info
