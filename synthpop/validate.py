import csv
import math
from collections import Counter
from pathlib import Path


def verify(data, population):
    """Recount raw attribute rows without candidate indices or solver state."""
    rows = [tuple(int(v) for v in row) for row in population]
    if any(len(row) != data.k or any(v not in range(3) for v in row) for row in rows):
        raise ValueError('Invalid population attribute values')
    counts = [Counter(tuple(row[a] for a in t['attrs']) for row in rows) for t in data.tables]
    table_lookup = {int(t['table_id']): j for j,t in enumerate(data.tables)}
    validation = []
    for c in data.cells:
        actual = counts[table_lookup[int(c['table_id'])]][c['values']]
        validation.append({'cell_id': c['cell_id'], 'table_id': c['table_id'], 'scope': c['scope'], 'cell': c['cell'], 'target': c['target'], 'actual': actual, 'difference': actual-c['target']})
    errors = [abs(c['difference']) for c in validation]
    freq = Counter(rows)
    n = len(rows)
    metrics = {'population_size': n, 'constraints': len(errors), 'violated_constraints': sum(e != 0 for e in errors), 'total_absolute_error': sum(errors), 'max_absolute_error': max(errors, default=0), 'distinct_personas': len(freq), 'duplicate_people': n-len(freq), 'max_persona_multiplicity': max(freq.values(), default=0), 'shannon_entropy_nats': -sum((v/n)*math.log(v/n) for v in freq.values()) if n else 0.0, 'success': n == data.n and not any(errors)}
    return validation, metrics


def read_population(path, k):
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != [f'A{i}' for i in range(k)]:
            raise ValueError('Population header mismatch')
        result = []
        for row in reader:
            values = [row[f'A{i}'] for i in range(k)]
            if any(v not in ('v0','v1','v2') for v in values):
                raise ValueError('Invalid population value')
            result.append([int(v[1:]) for v in values])
        return result


def write_csv(path, fields, rows):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_population(path, population, k):
    write_csv(path, [f'A{i}' for i in range(k)], [{f'A{i}': f'v{v}' for i,v in enumerate(row)} for row in population])
