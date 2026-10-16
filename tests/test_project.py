import csv
import itertools
import tempfile
import unittest
from pathlib import Path
import numpy as np
from synthpop.data import load
from synthpop.candidates import Candidates, State
from synthpop.solver import solve, Config
from synthpop.validate import verify


class ProjectTests(unittest.TestCase):
    def fixture(self, directory):
        # Three attributes; a complete joint marginal provides known feasibility.
        pop = [(0,0,0),(0,1,0),(1,0,1),(1,1,1)]
        with open(Path(directory)/'constraint_scopes.csv','w',newline='') as f:
            w = csv.writer(f, delimiter='\t')
            w.writerow(['table_id','arity','scope','num_cells','target_sum'])
            w.writerow([1,3,'A0|A1|A2',27,4])
        with open(Path(directory)/'constraint_cells.csv','w',newline='') as f:
            w = csv.writer(f)
            w.writerow(['cell_id','table_id','arity','scope','cell','target'])
            for i,v in enumerate(itertools.product(range(3),repeat=3)):
                w.writerow([i+1,1,3,'A0|A1|A2',';'.join(f'A{a}=v{x}' for a,x in enumerate(v)),pop.count(v)])
        return load(directory,3,4)

    def test_csv_zero_exclusion_and_restore(self):
        with tempfile.TemporaryDirectory() as d:
            data = self.fixture(d)
            c = Candidates(data)
            self.assertEqual(len(c.x),4)
            self.assertTrue(np.all(data.targets[c.match] > 0))
            state = State(data,c)
            r, n, legal = state.r.copy(), state.counts.copy(), state.legal()
            state.add(0)
            state.undo()
            np.testing.assert_array_equal(state.r,r)
            np.testing.assert_array_equal(state.counts,n)
            np.testing.assert_array_equal(state.legal(),legal)
            self.assertEqual(state.chosen,[])

    def test_known_feasible_and_independent_validator(self):
        with tempfile.TemporaryDirectory() as d:
            data = self.fixture(d)
            c = Candidates(data)
            for method in ['random','greedy']:
                pop, _ = solve(data,c,Config(method=method,seconds=2,capacity=True))
                _, m = verify(data,pop)
                self.assertTrue(m['success'])
                _, bad = verify(data,pop[:-1])
                self.assertFalse(bad['success'])

    def test_invalid_target(self):
        with tempfile.TemporaryDirectory() as d:
            self.fixture(d)
            path = Path(d)/'constraint_cells.csv'
            path.write_text(path.read_text().replace(',0\n',',-1\n',1))
            with self.assertRaises(ValueError):
                load(d,3,4)

    def test_exact_completion(self):
        try:
            import scipy
        except ImportError:
            self.skipTest('Optional SciPy unavailable')
        with tempfile.TemporaryDirectory() as d:
            data = self.fixture(d)
            pop, info = solve(data,Candidates(data),Config(exact=True,exact_at=4,seconds=3))
            self.assertTrue(verify(data,pop)[1]['success'])
            self.assertTrue(info['exact_calls'][0]['feasible_incumbent'])

    def test_repetition_is_not_a_capacity_failure(self):
        with tempfile.TemporaryDirectory() as d:
            data = self.fixture(d)
            data.n = 8
            data.targets *= 2
            for cell in data.cells:
                cell['target'] *= 2
            c = Candidates(data)
            state = State(data,c)
            self.assertTrue(np.any(state.r > state.support(state.legal())))
            self.assertTrue(state.check(capacity=True))
            pop, _ = solve(data,c,Config(seconds=2,capacity=True))
            self.assertTrue(verify(data,pop)[1]['success'])

    def test_malformed_cell_and_duplicate_id(self):
        for replacement in ['A0=v9', 'A0=v0;A0=v0']:
            with tempfile.TemporaryDirectory() as d:
                self.fixture(d)
                path = Path(d)/'constraint_cells.csv'
                path.write_text(path.read_text().replace('A0=v0',replacement,1))
                with self.assertRaises(ValueError):
                    load(d,3,4)

    def test_local_consistency_does_not_prove_global_feasibility(self):
        try:
            import scipy
        except ImportError:
            self.skipTest('Optional SciPy unavailable')
        with tempfile.TemporaryDirectory() as d:
            with open(Path(d)/'constraint_scopes.csv','w',newline='') as f:
                w = csv.writer(f)
                w.writerow(['table_id','arity','scope','num_cells','target_sum'])
                for tid, (a,b) in enumerate([(0,1),(1,2),(0,2)],1):
                    w.writerow([tid,2,f'A{a}|A{b}',9,2])
            with open(Path(d)/'constraint_cells.csv','w',newline='') as f:
                w = csv.writer(f)
                w.writerow(['cell_id','table_id','arity','scope','cell','target'])
                cid = 0
                for tid,(a,b) in enumerate([(0,1),(1,2),(0,2)],1):
                    for x,y in itertools.product(range(3), repeat=2):
                        cid += 1
                        allowed = x < 2 and y < 2 and ((x == y) if tid < 3 else (x != y))
                        w.writerow([cid,tid,2,f'A{a}|A{b}',f'A{a}=v{x};A{b}=v{y}',int(allowed)])
            data = load(d,3,2)  # All shared projections agree, yet the parity cycle is impossible.
            c = Candidates(data)
            pop, info = solve(data,c,Config(exact=True,exact_at=2,seconds=2))
            self.assertEqual(info['termination_status'],'global_infeasible_proven')
            self.assertFalse(verify(data,pop)[1]['success'])


if __name__ == '__main__':
    unittest.main()
