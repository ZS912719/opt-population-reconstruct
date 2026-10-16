# 合成人口重建（Python）

[English](README.md) | **简体中文**

输入为 500 人、12 个三分类属性、45 张边缘表、729 个计数约束。输出只是与边缘统计一致的合成人口，**不代表恢复了原始人口**。研究附件中的人格、LLM 和心理特征内容不属于本项目的实现范围。原始人口未提供。

## 安装及运行

Python 3.10+。纯模式只依赖 NumPy，精确补全额外依赖 SciPy/HiGHS。

```powershell
python -m pip install -r requirements.txt
# Optional exact-completion dependency
python -m pip install -r requirements-exact.txt
python -m unittest discover -s tests -v
python -m synthpop solve --method greedy --seed 0 --seconds 30 --out results/run
python -m synthpop solve --exact --seconds 60 --exact-at 300 --exact-seconds 8 --backtracks 1000 --rollback 75 --out results/run_exact
python -m synthpop validate --population results/run_exact/population.csv --out results/checked
python -m synthpop experiment --seeds 0,1,2 --seconds 12 --out results/pure
python -m synthpop experiment --seeds 0,1,2 --exact --seconds 60 --exact-at 300 --exact-seconds 8 --backtracks 1000 --rollback 75 --out results/hybrid
```

完整精确求解对照（前缀长度为零，因此此命令不衡量贪心的效果）：

```powershell
python -m synthpop solve --exact --exact-at 500 --seconds 45 --exact-seconds 40 --out results/full_exact
```

`solve` / `validate` 仅在完整独立验证通过时返回退出码 0；失败返回 2。`experiment` 返回 0 表示实验已运行完毕，成功率在汇总中记录。失败目录的 population.csv 是部分人口，不可用于声称满足实例。每次运行建议使用新输出目录。

## 文件格式和数据检查

`data/` 包含附件的两个 CSV 副本，未作修改。CSV 外层分隔符由 csv.Sniffer 从逗号、制表符、分号中检测。实际 scope 为 `A2|A3|A7|A9`，cell 为 `A2=v0;A3=v1;A7=v2;A9=v0`。内部解析独立于 CSV 分隔符。每个表的 scope 属性顺序用于解码，cell 赋值顺序可以不同。

加载器检查 ID 唯一、引用存在、合法属性及取值、整数非负 target、arity/num_cells/target_sum 元数据、完整笛卡尔单元格集合、每张表 target 和为 N，以及任意两表在共同属性上的投影一致性。这些是必要条件，**不证明全局可行**。默认实例规模是 k=12,n=500；小型实例可用 `--k` 和 `--n`。

## 模块

| 文件 | 职责 |
|---|---|
| synthpop/data.py | 读取和必要一致性检查 |
| synthpop/candidates.py | 全 persona 枚举、零目标排除、匹配和反向索引、可撤销状态 |
| synthpop/solver.py | 随机基线、贪心、前瞻、有限回退、随机重启 |
| synthpop/exact.py | 可选整数规划和求解状态分类 |
| synthpop/validate.py | 从序列化人口重新计算所有边缘计数 |
| synthpop/__main__.py | 命令行、指标与实验汇总 |

## 贪心及恢复

每一步重新计算合法候选掩码和不同候选支持数 q。仅匹配的全部 r>0 的 persona 可以加入。选择 r/q 最大的正需求单元格，对其合法支持者评分：需求项为匹配单元格紧迫度之和，除以“表数 × 全部正需求单元格平均紧迫度”；熵增量惩罚 `[(n+1)ln(n+1)-n ln n]/(ln N+1)`。因此 beta=1 时平均需求项约为 1，alpha=1 对最强重复惩罚约为 1。评分按 1e-7 量化并随机打破近似平局。没有另设“不同 persona 数量”的精确目标函数，D 与 H 分别报告。

前瞻每轮最多模拟 `--top` 个候选，检查剩余需求非负及所有正需求仍有合法支持。可用 `--capacity` 增加每个支持候选 `U=min r` 的总容量必要检查。重复合法，所以 r>q 不表示不可行。前瞻和容量检查通过均不证明剩余问题可行。每次失败分支在当前深度禁用；撤销到父节点后清除子层禁用记录。超过时间、总撤销人数预算或重启次数停止。回退指标计数的是撤销个体数（批量撤销也逐人计数）。

基线从当前全部合法候选均匀随机选择，不作前瞻、不使用紧迫度或熵评分；发生死路后使用同样的有限回退/重启机制。可指定 `--backtracks 0 --restarts 0` 获得单次无修复基线。混合实验中两个方法使用相同预算和精确补全策略。

## 精确补全

对当前合法候选建立非负整数 z，729 行等式为 `M z = r`，变量上界为 `min r`。线性代价为当前重复次数加随机微扰，是重复偏好的启发式，**不等于 Shannon 熵或 D 的精确优化**。剩余人数达到 `--exact-at` 或出现死路时启动。只有返回整数解且矩阵等式精确重验通过时才接受；最终仍需独立 CSV 验证。仅 `status=2` 表示该前缀剩余问题证明不可行，此时按 `--rollback` 批量撤销继续尝试。超时/未知不当作不可行，不据此执行批量不可行恢复；仍可继续普通贪心和死路修复。

SciPy status=0 仅证明其线性代理目标最优，**不证明多样性或熵最优**；status=1 是达到限制，可能有可行 incumbent。记录原始状态、消息、可行 incumbent 标志及 SciPy 版本；HiGHS 版本不通过公共 SciPy API 暴露。本次另行运行 `milp(..., options={'disp':True})`，日志确认 HiGHS 1.2.0。接口参考：https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html 。实际测试环境 Python 3.12.7、NumPy 1.26.4、SciPy 1.13.1；精确版本列在 requirements-tested.txt。

时间预算是软墙钟限制：Python 在每轮检查截止时间，求解器获得剩余预算；原生求解器清理、启动和一次数组扫描可能造成少量超时。不是操作系统硬终止保证。预处理不计入求解预算。

## 内存

枚举 531,441 个 persona 后，零目标排除剩 11,453 个。持久数组：

| 数组 | dtype / 大小 | 字节 |
|---|---|---:|
| persona 属性 | uint8 / 11453×12 | 137436 |
| 匹配单元格 | uint16 / 11453×45 | 1030770 |
| 反向索引 offset | int64 / 730 | 5840 |
| 反向索引候选 ID | int32 / 515385 | 2061540 |

合计 3,235,586 字节，约 3.09 MiB。状态 r 为 729 个 int64，persona 次数为 11,453 个 int64。初始属性矩阵约 6.08 MiB；枚举中广播 int64 临时数组约 48.66 MiB，筛选和排序还产生副本。精确补全 CSC 数据、行号、列偏移约额外 6 MiB 起，求解器内部内存可能更高。表格是数组字节数，**不是实测进程峰值内存**。

## 输出与实验解读

每个运行目录包含 population.csv（每行一个人、A0–A11）、validation.csv（每个 cell 的 target/actual/difference）、metrics.json（数量、误差、D、重复人数、最大重复次数、自然对数 H、时长、种子、参数、回退和重启次数、补全日志、终止状态）。运行先写 population.csv，再读回来独立计数，完全不依赖候选匹配缓存或求解器剩余计数。实验额外输出 summary.csv、summary.json，只对成功运行计算 D/H 均值；无成功结果则为 null。

有限种子成功率只是给定参数、环境和预算下的观测，不是普遍成功概率。H 与 D 是不同指标：相同 D 下，重复次数分配不同会改变 H。没有进行全局多样性或熵最优求解，也不能通过这些边缘约束验证真实人口或未观测行为。实际运行结果见 EXPERIMENTS.md。`python scripts/report.py` 可从三组已完成实验重新验证、生成报告并选择已观测 H 最高的可行运行作为 results/final；选择记录写入 selection.json。该脚本针对本项目交付的实验目录组织。
