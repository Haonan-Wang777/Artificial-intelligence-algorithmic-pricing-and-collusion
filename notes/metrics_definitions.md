# 数值指标与统计口径

本文件记录 Python 复现的实际计算定义，以便导师核查。论文来源为 `data/source/paper.pdf` 与 `data/source/supplemental_appendix.pdf`。已从用户提供的真实复现包 `data/source/provided_replication_package.zip` 取得官方 Fortran/R 源码，保存在 `vendor/calvano_original/`。下文明确区分官方一步偏离指标与本项目独立的完整动态最优响应诊断。数学定义已据源码核验，不表示随机数流、浮点运算顺序和训练轨迹已逐字节重现。

## 1. 冻结策略、精确周期与利润

训练结束后固定贪婪策略，不再探索、更新 Q 矩阵或重新训练。对记忆长度为 1 的模型，状态是上一期联合价格的离散索引；冻结策略产生下一期联合价格及下一状态。对记忆长度为 0 的模型只有一个状态。

从训练返回的最终状态开始，沿确定性状态转移行走，直至首次重复状态。重复前的非周期部分为 `transient_states`，随后恰好重复的状态序列为 `cycle_states`。周期检测没有任意有限期截断；`cycle_length` 是精确周期长度。均值仅使用周期，不计过渡部分，并对每个周期相位等权。

每个 session 的 `mean_profit` 与 `mean_price` 分别是各厂商的周期平均单期利润、价格。令竞争性与联合垄断基准利润分别为 πᶰᵢ、πᴹᵢ，则

\[
\Delta=\frac{1}{nL}\sum_{i=1}^{n}\sum_{\ell=1}^{L}
\frac{\pi_i(s_\ell)-\pi_i^N}{\pi_i^M-\pi_i^N}.
\]

`mean_delta` 是上式；`delta_by_player` 保留各厂商结果。不同 session 最后等权平均，不因为周期长而获得更高权重。带需求冲击的实验使用三个等概率需求状态的精确期望利润；价格状态转移仍是确定性的。

Table 1 的 `1-Sym.`、`1-Asym.`、`2`、`>=3` 用于区分固定价格与周期。当前代码以相同离散动作索引判定厂商对称性，适用于 Table 1 的对称基准模型；对非对称价格网格，动作索引相同不必代表实际价格相同，不能据此宣称厂商价格对称。

## 2. 保留在训练结果中的独立完整动态诊断

对每个厂商 i，固定其他厂商的完整策略。枚举所有状态与自身动作，用价值迭代求有限折扣 MDP：

\[
V_i^*(s)=\max_{a_i}\{r_i(s,a_i)+\delta V_i^*(T_i(s,a_i))\}.
\]

保存的 `bellman_residual` 是最终最大 Bellman 残差，目标不超过 10⁻¹¹；其除以 1−δ 给出最优价值函数的最大绝对误差上界。冻结联合策略的价值 Vᵖᵒˡᵢᶜʸ 通过确定性函数图计算：周期上的几何级数闭式求和，再对过渡状态回代，包含无限期尾项。

训练结果 JSON 中已有的 `q_loss_*` 字段计算如下完整动态价值损失；在取得真实官方源码后确认，它不是原文官方 Q-loss 的计算口径，应作为独立诊断保留，不能直接当作 Table 1 指标：

\[
q\_loss_i(s)=\frac{V_i^*(s)-V_i^{policy}(s)}{V_i^*(s)}.
\]

在本项目实际模型中分母为正。实现对一般输入以分母绝对值归一，并将微小负数值误差裁剪为零。`q_loss_on_path` 对厂商及精确周期相位等权平均；`q_loss_all_states` 对厂商及全部状态等权平均。数值保存为比例，例如 0.002 表示 0.2%，不是 0.002%。原训练结果及源码哈希保持不变，以免事后改变诊断口径掩盖差异；正式官方口径对照使用下文独立 sidecar 输出。

`is_equilibrium` 要求双方在每一个周期状态的 V*−Vᵖᵒˡᵢᶜʸ 均不超过 10⁻⁸（折扣利润绝对单位）。它检验冻结有限记忆策略是否在路径上构成完整动态最优响应，不把“训练策略稳定”当成博弈均衡。`is_subgame_perfect` 对全部状态执行同样检查。官方 `EquilibriumCheck` 使用下一节的一步偏离检查与零容差，含义不同。

另保存 `action_loss_on_path` 与 `action_loss_all_states`：

\[
action\_loss_i(s)=
\frac{\max_a Q_i^*(s,a)-Q_i^*(s,a_i^{policy}(s))}{\max_a Q_i^*(s,a)}.
\]

这里 Q* 假设本期动作之后恢复最优响应；完整动态价值损失比较始终遵循学习策略与始终采用最佳响应的收益。二者不是同一指标；它们也都不同于下一节官方 Qᵖᵒˡᵢᶜʸ 指标。

### 已据官方源码确认的一步偏离口径

官方 `AER_fcode/baseline/QL_routines.f90` 的 `computeQCell` 在第一期仅替换被检查厂商的动作，随后明确执行 `pPrime = OptimalStrategy(VisitedStates(iPeriod),:)`，即双方重新使用固定的学习策略，不进行后续动态优化。因此它实际计算

\[
Q_i^{policy}(s,a)=r_i(s,a)+\delta V_i^{policy}(T_i(s,a)),
\]

官方 `QGapToMaximum.f90` 的 `computeQGapToMaxSession` 对此矩阵取每行最大值，定义 `(MaxQTrue−QTrue[学习动作])/ABS(MaxQTrue)`。学习动作的 Qᵖᵒˡᵢᶜʸ 与 Vᵖᵒˡᵢᶜʸ 数学相等。它只允许本期偏离一次，之后恢复学习策略，不是任意动态最优响应。独立脚本使用同一矩阵中的原动作单元计算差值，避免 V 值回代与 Q 单元运算顺序不同导致原动作出现微小伪误差。

已运行的基准 1000 个 session 中，完整动态收益损失的路径均值约为 0.130845，而官方一步偏离损失约为 0.001590。这是有源码支持的指标含义差异，不能通过混用两种定义解释为训练程序计算错误。完整动态 Vᵖᵒˡᵢᶜʸ 已独立检查线性 Bellman 方程（两个 smoke session 最大误差约 8.9×10⁻¹⁶），V* 已通过所得最优策略的闭式收益重新核验（差异不超过 1.9×10⁻¹⁰）。官方 `computeQCell` 的逐单元循环算法另有独立逐字逻辑翻译测试，与共享 Vᵖᵒˡᵢᶜʸ 方法在小模型全状态/全动作上误差不超过 10⁻¹²。

官方 `EquilibriumCheck.f90` 检查学习动作是否达到同一行 Qᵖᵒˡᵢᶜʸ 最大值，`TestDiff <= 0.d0`，即精确最大值相等。sidecar 的 `author_one_step_*` 使用该零容差规则；保留的 `paper_one_step_no_profitable_deviation*` 则使用 10⁻⁸ 绝对利润容差，作为数值敏感性对照。均衡频率的原文对照默认使用零容差官方口径，两者不能与完整动态 Nash 检验混称。

**Table 1 的源码标签差异：** `AER_paper_Rscripts/table_I/table_I.R` 在标题为 “Q Loss All States” 的行实际读取 `det$QGapNotOnPath`，即路径外状态，非 `QGapTot`。因此官方 Table 1 对照使用 `paper_one_step_loss_off_path`；真正全状态均值 `paper_one_step_loss_all_states` 另列。该 R 脚本每个 session 只取一行并直接 `mean`/`sd`，包含零损失 session。`QGapToMaximum` 独立外层汇总中的正值过滤不适用于 Table 1，因为 Table 1 读取 `DetailedAnalysis` 直接输出的逐 session 值。单状态无记忆模型没有路径外状态，off-path 字段为 `None`。

官方口径有独立、可复验的脚本：`python experiments/paper_diagnostics.py --output results/validated`。它读取并校验已保存快照，不重新训练或修改训练源码；`paper_one_step_*`、`author_one_step_*` 字段与完整动态指标分名。输出为：

- `tables/paper_one_step_sessions.csv`：逐 session、逐厂商的单次偏离统计，并保留完整动态最优响应结果作对照；所有删失 session 也有记录。
- `tables/paper_one_step_comparison.csv`：把基准模型的官方定义指标与 Table 1 打印值作比较，明确标注 off-path 标签差异及零容差。
- `tables/table1_author_one_step.csv`：按固定对称、固定不对称、周期长度、全部 session 与通过官方一步检验的 session 分组重建 Table 1，并包含样本标准差。
- `paper_diagnostics.json`：只在达到训练收敛条件的 session 内计算场景均值和样本标准差。
- `figures/figure2_one_step_vs_dynamic.png`：并列显示缩小参数网格上的单次偏离条件与完整动态最优响应条件。
- `diagnostics_manifest.json`：独立脚本哈希、训练 identity、训练 manifest 哈希、依赖源码哈希、输入记录哈希和输出哈希；`paper_diagnostics.json` 额外记录官方参考源码哈希。

单次偏离检查只在路径上成立，不足以推出完整动态 Nash 均衡。专门的解析测试给出了反例：一次偏离之后立即恢复学习策略并不获利，但连续偏离两次可以到达长期有利状态。报告同时保留严格动态检验与官方一步指标，并明确二者的含义。

为控制计算预算，三、四厂商稳健性实验只计算精确周期、利润与 Δ；最优响应、Q-loss 与均衡字段明确为 `None`，不计入均衡统计，不能解释为“已经达到均衡”。

## 3. Fig. 4 偏离、配对基准与 IC

对每个周期相位分别运行以下确定性实验：

1. t=0：双方执行冻结策略，记录偏离前价格。
2. t=1：厂商 0 被强制改为对厂商 1 的 **t=0 价格** 的离散静态最优响应；静态利润并列时选择最低价格。厂商 1 仍按自己的冻结策略行动。
3. t≥2：双方均恢复冻结策略。

周期中对手 t=1 的策略价格可能不同于 t=0。实现使用原文的“对偏离前价格最优响应”口径，并保留这一差异，不把对手 t=1 的动作额外固定。输出 t=0 至 t=15 的路径，以及相同起始相位下始终遵循冻结策略的配对基准。每个 session 先对所有相位等权平均，随后跨 session 等权平均，符合 Fig. 4 脚注的相位权重规定。

`discounted_gain` 是从 t=1 开始计算的“强制偏离一次、随后恢复学习策略”相对配对基准的无限期折扣收益变化。它利用精确策略价值计算尾项，不是只加总图中 15 期收益；改变画图 horizon 不会改变此指标。

`incentive_compatible` 的严格定义是：一个 session 的 **每个周期相位**，厂商 0 的偏离收益均不超过 10⁻⁸。`incentive_compatible_phase_fraction` 则保留不获利相位的比例；`phase_discounted_gains` 保留各相位原始结果。如果静态最优响应恰好等于原动作，零变化相位仍计为不获利，`actually_changed_phase_fraction` 可识别这种情况。

官方 `AER_paper_Rscripts/table_III/table_III.R` 先限定常价 session（`PreShockCycleLength == 1`），再对所有离散偏离价及两名偏离厂商分别计算 `mean(DeviationQ < OptStratQ001)`，使用严格负收益。本项目上面的 IC 仅对厂商 0 的静态最优响应偏离、包含所有周期 session，并使用收益变化 ≤10⁻⁸，含义明确不同，不能直接宣称重现 Table 3 的每格统计。它也不替代第 2 节的全部动态最优响应检验。

## 4. 汇总、删失与不确定性

主要统计只包含达到配置所规定策略稳定条件的 session。达到最大训练期数仍不稳定的运行属于右删失：保留最终快照与诊断，并单独报告数量，但不混入主要论文对照均值。若有删失，报告中的均值是“已收敛样本条件下”的均值，不能忽略其选择影响。

`ci95_delta` 是 session 级别的 Monte Carlo 均值不确定性区间：

\[
\overline\Delta \ \pm\ t_{0.975,N-1}\frac{s_\Delta}{\sqrt N}.
\]

样本标准差使用 N−1 自由度。N=1 时不报告区间；此时保存标准差为 0 只是单样本占位，不能解释为没有随机性。Fig. 4 阴影使用 session 相位均值的标准误乘 1.96，是近似 95% Monte Carlo 区间。

以上区间只描述本次独立随机种子 session 的抽样误差，不包含论文原始结果的抽样误差、原文数值四舍五入、实现差异、模型设定错误或删失偏差。不同参数场景复用相同 seed 编号，可能形成跨场景相关性；本项目未据此构造配对处理效应置信区间。重复运行同一 seed、同一环境可复验数值，不会增加独立样本量。
