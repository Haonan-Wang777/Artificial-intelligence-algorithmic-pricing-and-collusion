# 作者 Fortran 源码核验与诊断口径更正

## 来源更正

用户外层 ZIP 中的 `Replication Package.zip` 是正确的 Calvano 等人 AER 复现包，已保存为 `data/source/provided_replication_package.zip`（27,317,813 字节）。它包含 `AER_fcode/`、论文/附录 R 脚本、软件指南及许可证。此前对工作区既有的 `replication_package_MS-FTBDA-20-01585.zip` 的判断不能套用到用户附件；两者不是同一个 ZIP。`notes/paper_audit.md` 已修正该来源误判。

本次审计独立从正确 ZIP 提取 `AER_fcode/baseline/*.f90` 到 `data/source/author_code/AER_fcode/baseline/` 供逐行检查，不执行附件中的 `.exe`。这是一份源码审查记录，不代表作者 Fortran 已在本环境编译运行。

## 最重要发现：作者的“均衡/Q-loss”不是完整 MDP 最优响应

`EquilibriumCheck.f90::computeEqCheckSession`（约第370–405行）对每个状态、企业和首期价格调用 `QL_routines.f90::computeQCell`，然后比较所选首期动作的值与该行最大值。`computeQCell` 的执行逻辑为：

1. 首期一方改选候选价格；其他企业按已学策略取价。
2. **首期之后所有企业，包括改变首期动作的企业，都恢复已学策略**。
3. 用确定性轨迹和周期几何尾项计算无限期折现收益。

因此作者计算的量是

\[
Q^{\pi,1dev}_i(s,a_i)=r_i(s,a_i,\pi_{-i}(s))+\delta V_i^\pi(T(s,a_i,\pi_{-i}(s))),
\]

而不是允许该企业此后每一期都重新优化的 `Q_i^*`。其“on-path equilibrium”检查是所有路径状态的一步偏离均无利。只在到达路径检查一步偏离，并不能排除离开该路径后继续修改自身策略所带来的多期收益。

`QGapToMaximum.f90` 第306–315行使用同一个 `computeQCell`，定义

\[
loss_i(s)=\frac{\max_a Q_i^{\pi,1dev}(s,a)-Q_i^{\pi,1dev}(s,\pi_i(s))}{|\max_a Q_i^{\pi,1dev}(s,a)|}.
\]

Table1 的 `.505 / .002 / .018` 必须与该作者一步偏离口径对照。当前 Python 的完整固定对手 MDP 最优响应在数学上是合理的更严格诊断，但它与作者表格不是同一指标；也不能用 `Q_i^*(s,pi_i(s))` 的首期动作损失代替上式，因为它允许首期之后最优延续。

**对已实际运行的 1,000 个 baseline 保存策略进行独立重算**，未重新训练、未改写源文件，得到：

| 指标 | 作者 Table1 | 本项目保存策略、作者一步偏离口径 |
|---|---:|---:|
| 所有路径状态、双方一步偏离无利的 session 比率 | .505 | .474 |
| 平均 on-path Q-loss | .002 | .0015897955773418564 |
| 平均 all-states Q-loss | .018 | .017985062070890272 |

本次独立重算使用 `1e-8` 折现利润的数值容差。作者 `EquilibriumCheck` 第398行使用 `TestDiff <= 0`（直接与行最大值精确比较），而其他代码部分使用 `AreEqualReals` 的绝对 machine epsilon；该区别应在正式实现中声明。重新导出的正式数据以 `results/` 的最终文件为准。

上述结果解释了此前严格 MDP 均衡率远低于论文的主要原因；不是随机训练过程突然失效，也不是企业2的状态视角转置。

## 状态索引：没有企业视角转置问题

`globals.f90` 第152–153行设

```
cStates  = (m^(LengthStates-1), ..., 1)
cActions = (m^(numAgents-1), ..., 1)
```

`QL_routines::computeStateNumber` 使用 `RESHAPE(TRANSPOSE(p))` 展平所有企业的共同价格历史，再作上述进位求和。对基准 `k=1,n=2`，即 `1 + (p1-1)*m + (p2-1)`；减去 Fortran 的1起始偏移后，正是 Python 的 `action0*m+action1`。`Q(state, ownAction, iAgent)` 对两个企业均使用**同一个全局 state**，没有让企业2将对手价格移到首位。Python 的共享状态编码正确。

## 学习过程与 Python 的对应

| 环节 | 作者源码 | Python 对应与差异 |
|---|---|---|
| 初始 Q | `initQMatrices` 类型 `O`：对同一自有价格、全部对手格点利润求均值，再除 `1-delta`；所有状态相同 | 等价 |
| 初始状态 | 每个价格独立均匀抽格点；全部 session 的初始状态由单独固定 `ran2` 流先产生 | 分布等价；Python 每session的随机状态来自该session自身流，不能逐随机路径一致 |
| 行动时点 | 先产生所有企业 `pPrime`，再更新各自 Q | 等价 |
| 自身 Bellman target | 当期利润 + `delta*maxValQ(nextState,iAgent)` | 等价；各企业 Q 独立，作者企业循环不会造成跨企业新旧Q混用 |
| 探索 | `eps=1` 开始，每期后乘 `ExplorationParameters`；参数为 `exp(-MExpl/itersPerEpisode)` | Python首期epsilon=1，随后`exp(-beta*t)`，其中 `beta=MExpl/itersPerEpisode`，数学等价；浮点重复乘法与直接exp略有差异 |
| 随机探索动作 | 全部 m 个动作等概率，包含贪婪动作 | 等价 |
| 随机流 | Numerical Recipes `ran2`，每session设 `idum=-iSession`；每期固定抽取两个企业的两组随机数 | Python NumPy/Numba RNG不同，并采用有条件抽探索动作，因此逐随机序列不同 |
| 策略稳定判据 | 只检查本期更新行，等价于全部状态策略稳定；变化时计数重设1 | Python重设0，相差至多一个稳定计数期 |
| 停止保存状态 | 作者达到条件时保存本期动作发生前的state和旧strategy；学习循环不再作末尾推进 | Python保存执行末步后的state；无探索时在同一吸引周期，残余探索或多吸引域时可能不同 |
| 平局 | 代码 `MaxLocBreakTies` 随机选择数值相等的最大值（`generic_routines.f90` 第307–357行） | Python采用正文要求的最低价平局；这是正文与作者代码差异，不能声称逐实现相同 |

特别地，作者注释“Differently from MAXLOC, ties are broken randomly”和实际 `ran2` 抽平局动作一致；这与正文 PDF p.8 的最低价规则不相同。基准初始化的最优动作通常唯一，但不能据此隐瞒差异。

## 原始配置的具体值

从正确 ZIP 中直接读取的 `AER_paper_Rscripts/figure_4/A_InputParameters.txt`：

- 1,000 sessions，`itersPerEpisode=25000`。
- `alpha1=alpha2=.15`，`MExpl1=MExpl2=.1`，因此每期 `beta=.1/25000=4e-6`。
- `PerfMeasPeriodLength=4`，因此稳定窗口为100,000期，与正文及Python相同。
- `maxNumEpisodes=50000`，所以作者输入的 `maxIters=1.25e9`；正文概述为1e9。作者退出测试是 `iIters > maxIters`。本项目缩小cap必须单独披露。
- `pN=1.47293,pM=1.92498` 是输入文本提供的五位小数，`PI_routines::computePIMatricesLogit` 将其作为给定值建立格点、计算基准利润，并不自行高精度求解均衡。Python高精度重解符合论文数学定义，但产生微小格点差异，可能放大为不同学习轨迹。

正确包的 figure1 参数文件包含100×100个点，实际alpha从 `.0025` 按 `.0025` 递增至 `.25`，而正文 PDF p.9 写起点 `.025`。`MExpl=.005,.010,...,.5`，换算每期beta为 `2e-7,4e-7,...,2e-5`。使用正文参数范围与使用作者配置并不是完全相同的扫描，应准确标注所用范围。

## 利润、周期与标准差

`ConvergenceResults.f90` 枚举终端固定策略的确定性轨迹，识别周期后均匀平均完整周期利润；每个session再等权进入总体平均。与Python对周期/会话的权重一致。

该文件第170行之后明确先计算 `AvgProfits = SUM(Profits,DIM=2)/numAgents`，再对session计算 `sqrt(E[AvgProfits^2]-E[AvgProfits]^2)`，最后除以平均垄断利润与平均Nash利润的差。因此 Table1 的总体 Δ 标准差应为**每session双企业平均收益的标准差**，而非把两个企业的收益混成2,000个独立观测。作者使用总体分母N；Python的样本SD使用N−1，N=1,000时相差约0.05%，应标明。

非对称企业场景中，作者总体 Δ 使用平均利润除平均基准差；当前 Python 若先对各企业分别归一化再平均，会与该总体口径有差别。已执行的基准、企业数、无记忆场景企业对称，不受此问题影响。

## 图4源码的潜在索引问题与选择原则

`ImpulseResponse.f90` 约第164–197行，在 `iStatePre=1,...,PeriodsLengthPre` 的循环中调用

```
ComputeStaticBestResponse(OptimalStrategy, iStatePre, ...)
computeIndividualIR(OptimalStrategy, VisitedStatesPre(iStatePre), ...)
```

但 `ComputeStaticBestResponse`（第445–492行）实际把第二个参数当作**全局状态编号**，用 `OptimalStrategy(iState,:)` 计算静态最优响应。循环相位编号通常不等于 `VisitedStatesPre(iStatePre)`。这看起来是作者代码中的索引歧义/潜在错误；未在本环境编译执行验证，故不应直接断言它解释了全部图形差异。

此外源码对每个企业都施加偏离后求平均，Python最初只固定企业0。对称模型在重复抽样意义上同分布，但有限样本图形会有差异。正文图4脚注要求对对手“偏离前价格”的静态最优响应；本项目应优先公开采用该数学定义，避免为复制可能的程序索引错误而改变模型，并将任何与作者实现的差异列出。

## 建议的正式交付表述

1. 作者原始代码和配置已找到、已保存并逐关键模块核验；Python是跨平台重实现，不能称“原始 Fortran 原封不动重跑”。
2. 与原表的主对照采用作者一步偏离诊断；完整 MDP 最优响应另列，明确更严格。
3. 保存具体源码、来源、配置、种子和逐session策略；不通过改种子使结果贴近作者数字。
4. 正文与代码不一致处（平局、扫描下界、cap、五位小数输入、IR索引）逐项披露，并写清本项目遵循的版本。
