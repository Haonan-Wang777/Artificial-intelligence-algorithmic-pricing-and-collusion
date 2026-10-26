# 人工智能定价与合谋：可检查的数值复现

> **GitHub网页上传版**：完整数据仍然保留，数千个记录已打包在 `_archives/`。上传时保留这些小ZIP，**不要展开后再上传**。[网页上传与本地恢复说明](GITHUB_UPLOAD_GUIDE.md)。一键复现会自动恢复；手动核验前运行 `python experiments/restore_assets.py`。

复现 Calvano, Calzolari, Denicolò and Pastorello (2020), **Artificial Intelligence, Algorithmic Pricing, and Collusion**, *American Economic Review* 110(10): 3267–3297。[论文官方页面](https://www.aeaweb.org/articles?id=10.1257/aer.20190623)。

**已运行作者原程序1,000次及Python基准1,000次**。作者程序重构的Table1 **56/56个单元格**与论文保留三位小数的结果一致：利润增益 **.84872**、总体标准差 **.11198**、作者路径检验通过率 **.505**。Python利润增益 **.849125**，对原文绝对误差 **.000125**；偏离后的价格战与逐步恢复高价也得到复现。全网格及全部鲁棒性尚未执行。

用户提供的 `Replication Package.zip` 包含正确的作者 Fortran 源码、Windows程序与R脚本，已核验并按原许可保存在 `vendor/calvano_original/`。项目同时提供**作者原程序运行入口与独立Python实现**。早期审查误认目录中另一份旧ZIP，已按原上传文件重新核对并更正，见 [材料来源审计](notes/source_audit.md)。

## 快速运行

推荐 **Python 3.12.5 / 64 位**。Windows 在本目录打开终端：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe reproduce.py --workers 3
```

最后一条是一键复现命令：运行测试、主批次训练、两种诊断、完整性核查与三个种子的串行重跑，再执行四企业原始上限追加验证。新结果写入 `results/recheck/` 与 `results/recheck_four_firms_extended/`，不会覆盖已交付结果。本机耗时数分钟，首次编译和不同硬件会影响耗时。依赖下载需要网络，安装后实验不需要联网。

同时运行作者Windows程序，在这条命令后加 `--original --runtime-path "实际Intel运行库目录"`，原程序结果另存于 `results/recheck_original/`。

macOS / Linux 使用 `python3 -m venv .venv`、`source .venv/bin/activate`，随后用 `python` 执行同样的安装与运行命令。已实际验证的平台为 Windows；Linux 的 GitHub Actions 配置已提供，尚未在线运行。

只运行两次完整状态空间的集成检查：

```powershell
.venv\Scripts\python.exe reproduce.py --quick --workers 1
```

`--quick` 用于检查安装和运行链路，不能代替 1,000 次统计实验。`requirements-lock.txt` 锁定本次安装版本；`requirements.txt` 提供兼容版本范围。

## 交付结果与限制

| 实验 | 实际运行 | 论文 Δ | 本次 Δ | 结论 |
|---|---:|---:|---:|---|
| 双企业代表性参数 | 1,000 / 1,000 收敛 | .849 | .849125 | 利润与周期统计接近 |
| α、β 参数网格 | 3×3，基准格点1,000次，其余每点30次 | 约 .70–.90 | .7265–.8602 | 缩小网格；非原文100×100 |
| 三企业 | 30 / 30 收敛 | .643 | .641712 | 小样本近似复现 |
| 四企业追加验证 | 10 / 10 收敛 | .559 | .546882 | 原始训练上限、小样本近似复现 |
| 无记忆对照 | 1,000 / 1,000 收敛 | .185 | .172223 | 方向一致，数值偏差及停止条件歧义 |

所有实验保留15档价格、原始状态空间和连续100,000期全状态策略不变的收敛窗口。主批次训练上限是10,000,000期，原文为1,000,000,000期。四企业初始10次中8次截尾，原始记录保存在主批次；追加验证对**相同全部10个种子**改用原文上限，最大实际运行26,332,642期，没有挑选或替换种子。

**作者诊断与完整动态检验须分别阅读**：

- 已从作者 `computeQCell` 确认：其诊断允许本期一次动作偏离，之后恢复已学策略。Python该类诊断的路径损失约 .001590、无获利偏离频率 .474，接近论文 .002 与 .505；更细的零容差和表格汇总差别见报告。
- 固定对手、允许持续最优偏离的完整动态检验：路径价值损失 .130845，路径上双方最优频率 .002。**该指标与作者一步偏离诊断定义不同，不能直接用它衡量Table1复现误差。** 单次偏离无利不能替代完整动态均衡。

[完整报告](REPRODUCTION_REPORT.md) 解释比较口径、误差、计算预算与未复现内容；[指标定义](notes/metrics_definitions.md) 和 [作者源码核查](notes/author_code_audit.md) 给出精确对应。

![单期偏离后的价格路径](results/validated/figures/figure4_impulse_response.png)

## 项目结构

```text
src/collusion/             定价模型、Q-learning、周期/最优响应诊断、汇总绘图
experiments/               实验入口、独立一步诊断、结果核查、全规模配置生成
configs/                   实际验证、两次集成检查、四企业追加验证配置
data/reference/            手工转录的论文印刷目标值（不是模拟结果）
data/source/               原材料来源说明；本地论文与ZIP不随公开项目分发
results/validated/         2,280次主批次记录、策略快照、表格、图、环境清单
results/four_firms_extended/  四企业10次原文上限追加运行
results/original_baseline/ 作者原程序1,000次实际结果及逐会话策略
results/integration_check/ 一键入口的实际集成验证
tests/                     方程、动态最优响应、偏离、重放等验证
notes/                     论文审读、材料来源、指标口径
vendor/calvano_original/   保持原字节的作者源码、输入、R脚本与许可
docs/REPRODUCIBILITY.md    环境、种子与导师核查说明
REPRODUCTION_REPORT.md    中文复现报告
reproduce.py               一键重跑
```

## 独立检查已交付数据

```powershell
.venv\Scripts\python.exe experiments/verify_results.py --output results/validated --rerun 3
.venv\Scripts\python.exe experiments/verify_results.py --output results/four_firms_extended --rerun 0
.venv\Scripts\python.exe experiments/paper_diagnostics.py --output results/validated
```

已核查主批次全部2,280个快照的 SHA256、种子、状态、周期利润与汇总；三个基准种子串行重跑，策略、Q矩阵、收益历史与训练步数逐元素一致。多进程训练只并行独立会话。每个情景第 `i` 次的种子为 `20261023+i`；没有为了拟合论文调种子。

最终21项测试通过。另将净化后的ZIP解压到独立目录，在没有论文PDF、原始ZIP及重复可执行文件副本的条件下，成功完成Python与作者程序的两会话一键检查，并重新核对Table1全部56格。

重点文件：

- `results/validated/manifest.json`：真实配置、环境与源代码哈希。
- `results/validated/tables/sessions.csv`：逐会话结果。
- `results/validated/tables/paper_comparison.csv`：利润比较及额外动态诊断的数值差异；动态诊断与原表定义不同。
- `results/validated/tables/paper_one_step_comparison.csv`：经源码核对的一步偏离比较，保留容差及汇总差别。
- `results/validated/verification.json`：完整性与重跑核验结果。
- `results/validated/figures/`：收益分布、缩小网格、两种诊断对照、偏离路径、早期学习曲线。
- `results/original_baseline/tables/paper_comparison.csv`：作者原程序的10项核心统计对照。
- `results/original_baseline/tables/table1_original.csv`：作者原程序按周期分组的Table1。
- `results/original_baseline/tables/table1_cell_comparison.csv`：56格逐项误差及打印精度匹配检查。

`converged=false` 的会话保留终止策略，但不混入主要收敛均值。图1、图2仅为网格子集；图4没有作者逐点原始数据，属于机制与形状复现，未虚构逐点误差。

## 论文全规模脚本

```powershell
.venv\Scripts\python.exe experiments/make_full_config.py
.venv\Scripts\python.exe experiments/run.py --config configs/paper_full.json --output results/paper_full --workers 3
.venv\Scripts\python.exe experiments/paper_diagnostics.py --output results/paper_full
```

生成的计划采用正文α区间，为100×100格点、每点1,000次，共**1,000万次会话**，上限每次10亿期。此计划未执行；生成配置不会自动训练。β取100个正的等距值 `2e-7,...,2e-5`。作者输入文件α实际从.0025开始，而正文为.025；作者完整原输入也保存在vendor，不能混称两者完全一致。完整计划可能产生大量文件；同环境、同配置、同源码可恢复已完成会话。

## 作者原程序

Windows安装Intel运行库后可以直接运行作者未修改的程序：

```powershell
.venv\Scripts\python.exe experiments/run_original.py --sessions 1000 --cores 3 --timeout 600 --output results/original_recheck --runtime-path "含libiomp5md.dll的Intel运行库目录"
.venv\Scripts\python.exe experiments/summarize_original.py --output results/original_recheck
```

这里的目录需替换为实际安装位置。当前机器使用已安装MATLAB附带的运行库，未把第三方运行库复制进项目。已实际成功运行作者程序；输入、输出、程序及运行库哈希在 `results/original_baseline/`。该入口采用1e7训练上限、原100000稳定窗口，并开启IR/均衡/Q-gap分析；不修改程序字节。[原代码说明](docs/ORIGINAL_CODE.md) 记录Intel编译依赖和原参数尺度。

## GitHub 发布

`project_delivery.zip` 是可以解压后上传的项目包，包含独立代码、配置、真实结果与文档。未包含虚拟环境、论文PDF、无关旧数据包或论文全文提取文本。运行项目不依赖这些原材料文件；来源、DOI及输入哈希仍可检查。复制本目录上传时遵循 `.gitignore`；建议直接使用交付ZIP内的净化目录。

本项目独立代码使用 [MIT License](LICENSE)。第三方论文及作者代码不在本授权范围内；引用信息见 [CITATION.cff](CITATION.cff)。
