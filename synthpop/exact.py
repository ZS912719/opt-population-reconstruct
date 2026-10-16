import time
import numpy as np


def complete(state, seconds, rng):
    """Integer feasibility completion; random linear costs are not entropy optimization."""
    start = time.perf_counter()
    try:
        import scipy
        from scipy.optimize import milp, Bounds, LinearConstraint
        from scipy.sparse import csc_matrix
    except ImportError:
        return None, {'status': 'dependency_missing', 'seconds': time.perf_counter()-start}
    ids = np.flatnonzero(state.legal())
    if not len(ids):
        return None, {'status': 'infeasible', 'seconds': time.perf_counter()-start}
    matched = state.c.match[ids]
    t = matched.shape[1]
    matrix = csc_matrix((np.ones(matched.size), (matched.ravel(), np.repeat(np.arange(len(ids)), t))), shape=(len(state.r), len(ids)))
    upper = state.r[matched].min(axis=1)
    # Mild repetition preference; this is only a linear surrogate for completion.
    cost = state.counts[ids].astype(float) + rng.uniform(0, 0.1, len(ids))
    res = milp(cost, integrality=np.ones(len(ids)), bounds=Bounds(0, upper), constraints=LinearConstraint(matrix, state.r, state.r), options={'time_limit': max(0.001, seconds), 'mip_rel_gap': 0.0})
    info = {'status': {0:'linear_objective_optimal', 1:'limit_or_unknown', 2:'infeasible', 3:'unbounded', 4:'unknown'}.get(res.status, 'unknown'), 'solver_status': int(res.status), 'message': res.message, 'seconds': time.perf_counter()-start, 'scipy_version': scipy.__version__, 'solver': 'HiGHS bundled with SciPy', 'diversity_optimality_proven': False}
    info['highs_version'] = 'bundled with scipy; not exposed by public scipy API'
    if res.x is not None and np.all(np.isfinite(res.x)):
        z = np.rint(res.x).astype(np.int64)
        if np.max(np.abs(res.x-z)) < 1e-5 and np.all(z >= 0) and np.array_equal(np.asarray(matrix @ z).ravel(), state.r):
            info['feasible_incumbent'] = True
            return np.repeat(ids, z).tolist(), info
    return None, info
