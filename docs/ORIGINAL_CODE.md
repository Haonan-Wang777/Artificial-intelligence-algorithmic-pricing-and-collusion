# 作者原始程序：结构、构建和核对

用户上传的真正内层包已经提供完整原始代码。本项目按作者许可提取到 [`vendor/calvano_original`](../vendor/calvano_original/README.md)，保留原许可和致谢，记录原文件哈希。未修改的原始 baseline.exe 已在补充现有 Intel OpenMP 运行库路径后成功执行小规模实验；其源码编译流程尚未验证。

## 原程序结构

`AER_fcode/baseline` 处理基准、参数网格与多数稳健性实验；`stochasticdemand` 和 `entryexit` 分别处理随机需求、市场进入退出。论文图表各有一个 `AER_paper_Rscripts/<figure或table>/` 目录，包含 Fortran 输入文件与 R 汇总脚本。附录对应 `AER_online_appendix_Rscripts`。作者软件指南 `README.pdf` 和两份 Table replication PDF 列出图表与程序的对应关系。

按模块 `USE` 依赖关系，baseline 可依次编译：

```text
generic_routines.f90
globals.f90
QL_routines.f90
PI_routines.f90
LearningSimulation.f90
ConvergenceResults.f90
EquilibriumCheck.f90
ImpulseResponse.f90
QGapToMaximum.f90
DetailedAnalysis.f90
LearningTrajectory.f90
main.f90
```


## 直接运行作者 baseline.exe

本项目已实际验证：作者程序最初因缺少 Intel OpenMP 运行库返回 `0xc0000135`；通过已有 MATLAB 的 `C:\Program Files\MATLAB\R2025b\bin\win64` 目录提供依赖搜索路径后，小规模原程序运行成功。没有修改原 exe，也不复制 MATLAB 的运行库进公共项目。

`experiments/run_original.py` 提供原程序运行入口，并支持 `--runtime-path`。可用以下命令查看当前参数，再选择所需输入、规模和运行库目录：

```text
python experiments/run_original.py --help
```

其他机器应提供自己已安装、可使用的 Intel OpenMP 运行库路径；不能假定也安装了 MATLAB 或具有相同目录。原始模型输入和可执行文件均可从 vendor 读取。原程序运行结果与 Python 的结果分别保存，具体运行参数、完成规模和诊断数据见各自运行记录及最终报告。

## 编译依赖与辅助脚本

作者软件指南列明使用 Intel Visual FORTRAN Compiler XE 13.1.2.190 / Visual Studio / OpenMP；R 4.0.2 与 RStudio 1.3.959。原源码使用 Intel 的 `ifport`、`SORTQQ`、`LOC` 与 `<变量>` FORMAT 扩展，gfortran 不能保证原样编译。

本环境查找 `ifort`、`ifx`、`gfortran` 和 `Rscript` 未发现可调用程序。原码编译和 R 流程**尚未执行验证**；这与已成功执行作者预编译 baseline.exe 是两项不同的检查。已提供 [`scripts/build_original.ps1`](../scripts/build_original.ps1)，按上面的模块顺序调用 Intel classic `ifort`、复制图表输入到独立构建目录，不自动运行生成的程序：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_original.ps1
```

先打开已配置 Intel 编译器环境的命令窗口。脚本面向 Windows Intel classic 编译链，需由拥有相应环境的研究者实际检查；新 oneAPI 的兼容性和编译选项不能视为已验证。构建成功后，可以在脚本输出的目录内手工运行新编译的 `baseline.exe`。不要在 vendor 源码目录生成/覆盖实验结果。

默认输入来自 `AER_paper_Rscripts/table_I/A_InputParameters.txt`，是作者 1,000 会话配置。它的 25 核设置、较大上限和详细分析会带来明显计算及输出成本。应先在复制后的输入里缩减会话数、核数，关闭不需要的详细输出，确认流程；修改后的输入属于缩小验证配置，应与原输入分别保存。没有修改 vendor 中的原始输入。

Fortran 输出在工作目录产生；随后在包含相应 R 脚本与所需输出的独立工作目录运行 R。不同图表的结果文件名和前处理并不相同，按作者软件指南和同目录 `readme.txt` 执行。项目为节约体积省略了若干大型原始结果，因此 R 脚本目录不能直接视为含全部输入结果的开箱即用数据集。

## 与 Python 的关键核对点

- 原随机流为 RAN2，初态随机流与探索/并列破局随机流分开；Python 随机流不同，不能逐位复现作者样本。
- 原探索从概率 1 开始；输入 beta 按 `itersPerEpisode` 缩放。例如原输入 `0.1/25000` 对应每期 `4e-6`。
- 原表 I 输入的 Nash/合作价格只给 5 位小数；Python 若数值求解至更高精度，其网格会出现微小差别。
- 原程序并列最优动作随机打破；收敛策略改变时连续窗口计数重新设为 1，终态写在转移到下一状态之前。
- `QGapToMaximum` 的 Q-loss 是一次偏离后回到固定所学策略的损失比例。完整重新优化的最优反应价值差应另列，不能替代这一口径。
- `table_I.R` 标注 All States 的表格行实际读取 `QGapNotOnPath`。源码与文字命名不一致应在对比中披露；可同时报告真正全状态与离轨状态均值。

这些核对点用于判断实现等价性；本文件不提供未经实际运行的原程序结果。
