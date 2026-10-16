import csv
import itertools
import re
from dataclasses import dataclass
from pathlib import Path
import numpy as np


def rows(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        sample = f.read(8192)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=',\t;')
        return list(csv.DictReader(f, dialect=dialect))


def integer(s):
    if not re.fullmatch(r'\d+', str(s)):
        raise ValueError(f'Expected nonnegative integer: {s!r}')
    return int(s)


def scope(s):
    # The supplied format uses |; also accept whitespace/comma/semicolon.
    parts = re.split(r'[|,;\s]+', s.strip())
    if any(not re.fullmatch(r'A\d+', p) for p in parts):
        raise ValueError(f'Invalid scope: {s}')
    a = tuple(int(p[1:]) for p in parts)
    if len(set(a)) != len(a):
        raise ValueError('Repeated attribute')
    return a


@dataclass
class Data:
    k: int
    n: int
    tables: list
    cells: list
    targets: np.ndarray


def load(directory, k=12, n=500):
    tables, cells = rows(Path(directory)/'constraint_scopes.csv'), rows(Path(directory)/'constraint_cells.csv')
    by_id = {}
    for t in tables:
        tid = integer(t['table_id'])
        a = scope(t['scope'])
        if tid in by_id or any(x >= k for x in a):
            raise ValueError('Invalid/duplicate table ID or attribute')
        if integer(t['arity']) != len(a) or integer(t['num_cells']) != 3**len(a) or integer(t['target_sum']) != n:
            raise ValueError('Invalid table metadata')
        t['attrs'], t['mapping'] = a, {}
        by_id[tid] = t
    seen = set()
    for i, c in enumerate(cells):
        cid, tid = integer(c['cell_id']), integer(c['table_id'])
        if cid in seen or tid not in by_id:
            raise ValueError('Invalid/duplicate cell ID or unknown table')
        seen.add(cid)
        t = by_id[tid]
        if scope(c['scope']) != t['attrs'] or integer(c['arity']) != len(t['attrs']):
            raise ValueError('Cell/table scope mismatch')
        terms = re.split(r'[;|,\s]+', c['cell'].strip())
        assignments = {}
        for term in terms:
            m = re.fullmatch(r'A(\d+)=v([012])', term)
            if not m or int(m[1]) in assignments:
                raise ValueError('Invalid cell assignment')
            assignments[int(m[1])] = int(m[2])
        if set(assignments) != set(t['attrs']):
            raise ValueError('Cell attributes mismatch')
        values = tuple(assignments[a] for a in t['attrs'])
        if values in t['mapping']:
            raise ValueError('Duplicate cell combination')
        t['mapping'][values] = i
        c['attrs'], c['values'], c['target'] = t['attrs'], values, integer(c['target'])
    targets = np.array([c['target'] for c in cells], dtype=np.int64)
    for t in tables:
        if set(t['mapping']) != set(itertools.product(range(3), repeat=len(t['attrs']))) or sum(targets[list(t['mapping'].values())]) != n:
            raise ValueError('Incomplete table or wrong population sum')
    if set(a for t in tables for a in t['attrs']) != set(range(k)):
        raise ValueError('Missing attribute coverage')
    for t, u in itertools.combinations(tables, 2):
        common = sorted(set(t['attrs']) & set(u['attrs']))
        if not common:
            continue
        def project(table):
            out = {}
            for v, i in table['mapping'].items():
                key = tuple(v[table['attrs'].index(a)] for a in common)
                out[key] = out.get(key, 0) + int(targets[i])
            return out
        if project(t) != project(u):
            raise ValueError('Inconsistent overlapping projections')
    return Data(k, n, tables, cells, targets)
