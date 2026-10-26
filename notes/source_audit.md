# 材料与原始代码来源审计

审计日期：2026-10-23。

## 来源结论与已纠正的审计错误

**用户上传的外层 ZIP 内含正确且完整的 AER 原始复现包。** 本地此前另有一个 1.5 MB 的 `data/source/replication_package_MS-FTBDA-20-01585.zip`，属于 SKU 库存补货研究，与当前论文无关。初次审计错误地将该旧文件认作上传 ZIP 的内层包；这是本项目审计过程的文件对应错误，已根据外层 ZIP 的真实成员和哈希纠正，不能归因于用户材料错配。

真正内层文件现提取为 `data/source/provided_replication_package.zip`，大小为 **27,317,813 字节**，SHA256 为 `b4d16499f35de197c929465001cd23650a99f84244e0378290444d7284f8a9b1`。其顶层含 `AER_fcode/`、`AER_paper_Rscripts/`、`AER_online_appendix_Rscripts/`、软件指南及许可证。

## 1. 论文与附录身份

论文首页为 Calvano, Calzolari, Denicolò and Pastorello，*Artificial Intelligence, Algorithmic Pricing, and Collusion*, *American Economic Review* 110(10), 3267–3297 (2020)，DOI `10.1257/aer.20190623`；附录同题、同作者，时间为 May 2020。

官方入口：[AEA 文章页](https://www.aeaweb.org/articles?id=10.1257/aer.20190623)，[在线附录](https://www.aeaweb.org/articles/materials/13398)。文章页的 Replication Package 链接指向 [10.3886/E119462V1](https://doi.org/10.3886/E119462V1) 与 [openICPSR 119462/V1](https://www.openicpsr.org/openicpsr/project/119462/version/V1/view)。官方 [baseline 文件目录](https://www.openicpsr.org/openicpsr/project/119462/version/V1/view?path=%2Fopenicpsr%2F119462%2Ffcr%3Aversions%2FV1%2FAER_fcode%2Fbaseline&type=folder) 中的源文件名与上传包一致。官方网页版本发布日期为 2020-09-23。

网上下载尝试曾返回 HTTP 403 或进入 OAuth 登录页面；**这不影响用户已提供的原代码可用性**。本项目原代码来源是上传 ZIP，不声称下载过网上文件，也未对在线包与上传包做逐字节相等验证。

## 2. 许可证与保留内容

实际读取了内层顶层 `LICENSE.txt`。许可证为作者的 MIT 条款，并附加终端用户文档必须包含作者致谢的要求。原始许可字节已保留于 `vendor/calvano_original/LICENSE.txt`；致谢置于项目 `THIRD_PARTY_NOTICES.md` 和 vendor 说明中。

按许可保留到 `vendor/calvano_original/` 的文件包括所有 Fortran 与 R 源文件、全部输入参数文件、较小的文本/R 数据，以及软件指南。`VENDOR_MANIFEST.json` 记录所有保留文件的原始路径、大小、SHA256，以及有意省略的文件。未改动这些第三方文件字节。

为控制项目体积，保留原始未修改 `baseline.exe`；未分发另外两个 `.exe`、两个各约 185.9 MB 的 `A_det_1.txt`、重复的大型 Rdata/原始结果等；省略不代表这些文件不在上传包内。保留的 R 脚本需要相应 Fortran 输出，部分脚本不能仅靠小数据直接生成全部论文图表。

论文与论文附录 PDF 保留在 `data/source/` 供本地阅读，公共 Git 不分发。vendor 中的软件指南属于作者程序所附文档，保留其原许可与作者署名。

## 3. 已直接核验的实现细节

基准源文件位于 `vendor/calvano_original/AER_fcode/baseline/`：

- `generic_routines.f90` 使用 Numerical Recipes RAN2；`LearningSimulation.f90` 按会话 `idum=-iSession`、辅助种子 `123456789` 初始化随机流，初始状态来自单独的固定初始种子流。
- `QL_routines.f90` 初始化 Q 为对手均匀随机动作时的折现收益。原程序并列最大值使用随机打破，不是固定最低价。
- 原迭代计数从 1 开始，初始 `eps=1`，实际探索更新公式须结合 `computePPrime` 核验。原程序策略改变时连续计数设为 1；`LearningSimulation` 原状态记录发生在更新到下一状态之前。
- `QGapToMaximum.f90` 调用 `QL_routines.computeQCell`，计算一次偏离后双方都回到固定所学策略的真实折现 Q 值；Q-loss 是这一组 Q 的最大值与所学动作 Q 的差除以最大 Q 的绝对值。不能将完整重新优化的最优值差直接标为论文 Q-loss。
- `AER_paper_Rscripts/table_I/table_I.R` 从 `DetailedAnalysis` 逐会话输出汇总表 1；零 gap 会话没有被过滤。注意原 R 脚本标作 All States 的行实际读取 `QGapNotOnPath`，核对论文比较时需要明确此命名差异。

Python 实现和作者原始 `baseline.exe` 均有实际运行。最初启动作者程序返回缺少运行库错误 `0xc0000135`，随后从现有 MATLAB 安装目录 `C:\Program Files\MATLAB\R2025b\bin\win64` 提供 Intel OpenMP 运行库搜索路径后，原程序小规模运行成功；没有修改 exe。训练及指标差异、修正和实验运行身份以最终代码、`docs/REPRODUCIBILITY.md` 和运行 manifest 为准，不能仅凭本审计说明宣称逐位一致。

## 4. 作者构建环境与 Python 实现的适用性

上传包 README（July 11, 2020）明确列出原环境：Intel Visual FORTRAN Compiler XE 13.1.2.190，Visual Studio，OpenMP；R 4.0.2、RStudio 1.3.959。源码直接使用 `ifport`、`SORTQQ`、`LOC` 和 `<变量>` FORMAT 扩展。`ifport` 与 Intel 格式扩展使其不能保证在 gfortran 上无修改直接编译。

本环境尚未验证 Intel 编译链；作者 Windows baseline 可执行程序已在补充现有 Intel OpenMP 运行库搜索路径后成功执行小规模实验。完整运行规模和结果以最终实验记录为准。构建步骤与按模块依赖排列的建议见 `docs/ORIGINAL_CODE.md`，构建辅助脚本不承诺当前编译成功。

Python 便于在现代平台运行、逐会话保存和自动检查；它基于原论文、附录和作者代码核验，但随机流与作者 RAN2 不同，因此固定 Python 种子不产生相同的作者样本路径。比较应基于模型参数、算法语义、指标定义和实际样本统计，并明确实现差异。

## 5. SHA256

机器可读清单：`notes/source_manifest.json`。外层 ZIP 实际读取的成员哈希如下：

| 文件 | SHA256 |
|---|---|
| 用户外层 ZIP | `5abdfa3a697c43306e11d0efc9c01fa3037742cfb0a8d605388baa68e2c9e57a` |
| 论文 PDF | `8ac3f4b6777dbbb1332728925a5123196f1846473841992574f6c519891a54d8` |
| Supplemental Appendix.pdf | `ef4902273a793b67f309fab253e712a1ae1462f1cae6817bdd11d694d2f5cdfd` |
| 真正内层 Replication Package.zip | `b4d16499f35de197c929465001cd23650a99f84244e0378290444d7284f8a9b1` |
| 本地既有无关库存 ZIP（非本次上传内层） | `a24e8531c846c3c17f35d422c2218c219d84693d9225301ad83ccfc7e7ee65de` |

哈希标识实际检查文件，不代表出版社数字签名。无关旧 ZIP 未用于训练、结果、vendor 或论文参数。
