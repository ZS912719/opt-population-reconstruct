import time
import numpy as np


class Candidates:
    def __init__(self, data):
        start = time.perf_counter()
        codes = np.arange(3**data.k, dtype=np.int64)
        x = ((codes[:, None] // (3**np.arange(data.k-1, -1, -1))) % 3).astype(np.uint8)
        # Filter table by table before allocating the full candidate-cell matrix.
        for t in data.tables:
            lookup = np.array([t['mapping'][v] for v in sorted(t['mapping'])])
            idx = x[:, t['attrs']].astype(np.int64) @ (3**np.arange(len(t['attrs'])-1, -1, -1))
            x = x[data.targets[lookup[idx]] > 0]
        dtype = np.uint16 if len(data.cells) < 65536 else np.uint32
        self.x = x
        self.match = np.empty((len(x), len(data.tables)), dtype=dtype)
        for j, t in enumerate(data.tables):
            lookup = np.array([t['mapping'][v] for v in sorted(t['mapping'])])
            idx = x[:, t['attrs']].astype(np.int64) @ (3**np.arange(len(t['attrs'])-1, -1, -1))
            self.match[:, j] = lookup[idx]
        flat = self.match.ravel()
        order = np.argsort(flat, kind='stable')
        counts = np.bincount(flat, minlength=len(data.cells))
        self.offset = np.r_[0, np.cumsum(counts)]
        self.reverse = (order // len(data.tables)).astype(np.int32)
        self.seconds = time.perf_counter()-start
        self.memory = {key: getattr(self, key).nbytes for key in ['x', 'match', 'offset', 'reverse']}

    def supporters(self, c):
        return self.reverse[self.offset[c]:self.offset[c+1]]


class State:
    def __init__(self, data, candidates):
        self.data, self.c = data, candidates
        self.r = data.targets.copy()
        self.counts = np.zeros(len(candidates.x), dtype=np.int64)
        self.chosen = []

    def legal(self):
        return np.all(self.r[self.c.match] > 0, axis=1)

    def support(self, legal):
        return np.bincount(self.c.match[legal].ravel(), minlength=len(self.r))

    def add(self, x):
        if np.any(self.r[self.c.match[x]] <= 0):
            raise ValueError('Illegal candidate')
        self.r[self.c.match[x]] -= 1
        self.counts[x] += 1
        self.chosen.append(int(x))

    def undo(self):
        x = self.chosen.pop()
        self.r[self.c.match[x]] += 1
        self.counts[x] -= 1
        return x

    def check(self, capacity=False):
        if np.any(self.r < 0):
            return False
        legal = self.legal()
        q = self.support(legal)
        if np.any((self.r > 0) & (q == 0)):
            return False
        if capacity and legal.any():
            upper = self.r[self.c.match[legal]].min(axis=1)
            cap = np.bincount(self.c.match[legal].ravel(), weights=np.repeat(upper, self.c.match.shape[1]), minlength=len(self.r))
            if np.any(cap < self.r):
                return False
        return True
