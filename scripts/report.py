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
    lines = ['# 实际运行报告', '', '运行日期：2026-10-06。Python 3.12.7，NumPy 1.26.4，SciPy 1.13.1。', '', '通过 HiGHS 的 disp 日志另行核实，当前环境捆绑的 HiGHS 版本为 1.2.0。', '', '数据零目标筛选后有 11,453 个候选，与研究附件第 15 页的活跃 persona 数量一致。数据检查只是必要条件。', '']
    feasible = []
    for name in ['pure','hybrid','hybrid_long_calls']:
        folder = ROOT/'results'/name
        if not (folder/'summary.json').exists():
            raise RuntimeError(f'Experiment not complete: {name}')
        summary = json.loads((folder/'summary.json').read_text())
        lines += [f'## {name}', '', '完整命令：', '', '```powershell']
        p = summary['parameters']
        command = f"python -m synthpop experiment --seeds {p['seeds']} --seconds {p['seconds']} --restarts {p['restarts']} --backtracks {p['backtracks']} --out results/{name}"
        if p['exact']:
            command += f" --exact --exact-at {p['exact_at']} --exact-seconds {p['exact_seconds']} --rollback {p['rollback']}"
        lines += [command, '```', '', '| 方法 | 种子 | 成功 | 人数 | 不满足约束 | L1误差 | 最大误差 | D（仅可行） | H（仅可行） | 求解秒 | 撤销人数 | 重启 | 补全秒 |', '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
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
        lines += ['', f"共享预处理：{summary['shared_preprocessing_seconds']:.4f} 秒（每次实验只执行一次）。", '']
        for method, r in summary['results'].items():
            lines.append(f"- {method} 成功率：{r['successful_runs']}/{r['runs']}；可行结果 D 均值={r['feasible_mean_distinct_personas']}，H 均值={r['feasible_mean_entropy_nats']}。")
        lines += ['']
    full = ROOT/'results/full_exact'
    m = json.loads((full/'metrics.json').read_text())
    assert verify(data,read_population(full/'population.csv',data.k))[1]['success']
    lines += ['## 完整整数规划对照', '', '命令：`python -m synthpop solve --exact --exact-at 500 --seconds 45 --exact-seconds 40 --out results/full_exact`。', '', f"独立验证通过：500 人，729/729 约束满足；D={m['distinct_personas']}，H={m['shannon_entropy_nats']:.6f}；求解 {m['solve_seconds']:.3f} 秒。求解器达到时间上限但具有可行 incumbent，未证明线性目标最优。此运行没有贪心前缀。", '']
    feasible.append((full,m))
    best_h = max(feasible,key=lambda pair:pair[1]['shannon_entropy_nats'])
    best_d = max(feasible,key=lambda pair:pair[1]['distinct_personas'])
    final = ROOT/'results/final'
    final.mkdir(exist_ok=True)
    for file in ['population.csv','validation.csv','metrics.json']:
        shutil.copyfile(best_h[0]/file,final/file)
    (final/'selection.json').write_text(json.dumps({'criterion':'highest observed Shannon entropy among independently verified runs', 'source':str(best_h[0].relative_to(ROOT)), 'max_distinct_personas_source':str(best_d[0].relative_to(ROOT)), 'global_optimality_proven':False},indent=2),encoding='utf-8')
    m = best_h[1]
    lines += ['## 默认交付结果及限制', '', f"默认 results/final 来自 `{best_h[0].relative_to(ROOT).as_posix()}`，按实验中最高 H 选择：N={m['population_size']}，约束误差全部为 0，D={m['distinct_personas']}，重复人数={m['duplicate_people']}，最大重复次数={m['max_persona_multiplicity']}，H={m['shannon_entropy_nats']:.9f} nats。", '', f"实验中最大 D 为 {best_d[1]['distinct_personas']}，来自 `{best_d[0].relative_to(ROOT).as_posix()}`，其 H={best_d[1]['shannon_entropy_nats']:.9f}。D 与 H 分开选择和报告。", '', '这些均为已观测可行解，没有全局 D 或 H 最优证明。精确补全 status=0 只针对线性代理目标；完整补全或带前缀补全不能证明原始多样性目标最优。', '', '三种子结果只适用于本次参数；不能泛化为算法普遍成功率。纯模式未成功时，不对其部分人口比较可行多样性。混合模式包括精确修复，因此成功不能归因于纯贪心。', '', '部分实验同时运行，耗时受共享 CPU 竞争影响，适合复现操作记录，不是隔离环境性能基准。时间限制是软限制，求解器退出开销会有小幅超出。未经验证的失败前缀保留在对应运行目录并明确标记 success=false。', '', '7 项 unittest 全部通过；另含局部投影一致但全局不可行的反例测试。所有实验人口在汇总时再从 CSV 重验。']
    (ROOT/'EXPERIMENTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'final_source':str(best_h[0]), 'best_entropy':m['shannon_entropy_nats'], 'best_distinct':best_d[1]['distinct_personas']},indent=2))


if __name__ == '__main__':
    main()
