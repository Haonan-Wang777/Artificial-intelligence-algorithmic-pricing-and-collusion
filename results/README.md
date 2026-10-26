# 实际运行结果索引

- `original_baseline/`：作者未修改Windows程序，1,000次基准会话，全部收敛。Table1重构、原始策略、原生IR输出及哈希保留；优先检查此目录。
- `validated/`：独立Python主批次，共2,280次。`paper_one_step_comparison.csv` 对应作者一步检验；早期 `paper_comparison.csv` 的动态检验列定义不同，不作为Table1同口径误差。
- `four_firms_extended/`：同10个四企业种子改用原文训练上限的追加运行，全部收敛。主批次8次截尾记录保留。
- `original_smoke/`：作者程序2会话安装检查；与正式原程序批次前2会话比较，用于验证并行调度不改变结果。
- `final_integration/` 与 `final_integration_original/`：一键入口的最终两会话检查，包含Python及作者程序。

各目录的 `summary.json` 为摘要，`tables/` 可直接检查；`manifest.json`、`execution.json`、`summary_manifest.json`、`diagnostics_manifest.json` 按适用情况记录环境、输入输出和源码哈希。训练步数、策略等才是重放对象，耗时和时间戳不要求一致。

所有模拟数值均来自真实运行；论文目标列来自原文或附录，绝不充当新运行数据。主批次和四企业追加批次共享种子，不能合并计作独立样本。
