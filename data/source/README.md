# 输入材料与作者原始程序

用户上传的 ZIP 包含论文、在线附录，以及 **正确且完整的作者原始复现包**。真正内层 `Replication Package.zip` 已提取为 `provided_replication_package.zip`，大小 27,317,813 字节，包含 `AER_fcode`、论文/附录 R 脚本、输入参数、软件指南及许可证。

本地既有 `replication_package_MS-FTBDA-20-01585.zip` 为无关库存补货研究旧文件，不是用户上传 ZIP 的内层包。初次审计将两者混淆，已按外层 ZIP 真实成员与 SHA256 纠正；用户上传材料没有错配。

逐文件哈希见 [`notes/source_manifest.json`](../../notes/source_manifest.json)，来源审计见 [`notes/source_audit.md`](../../notes/source_audit.md)。上传的论文 PDF、附录 PDF 和 ZIP 保留在本地并由 `.gitignore` 排除公共分发。作者代码按包内许可保留于 [`vendor/calvano_original`](../../vendor/calvano_original/README.md)，保留原版权、许可和必需致谢；大型原始结果和另外两个 exe 未包含，原始 `baseline.exe` 按原许可保留。

## 官方来源与补充获取

1. [AEA 文章页](https://www.aeaweb.org/articles?id=10.1257/aer.20190623) 提供论文、[在线附录](https://www.aeaweb.org/articles/materials/13398) 和 Replication Package 入口。
2. 正确程序的官方 DOI 为 [10.3886/E119462V1](https://doi.org/10.3886/E119462V1)，存档为 [openICPSR 119462/V1](https://www.openicpsr.org/openicpsr/project/119462/version/V1/view)。按站点要求登录、阅读条款后下载。
3. 基准 Fortran 程序在 `AER_fcode/baseline`；另外两个目录处理随机需求与进入退出。上传包中的软件指南介绍编译、输入输出以及 R 作图流程。

本次网上下载尝试受 HTTP 403/登录限制，但上传包已提供原代码，所以不构成材料缺失。Python 实现与作者原始 baseline.exe 均已实际执行小规模实验。作者程序初次缺少 Intel OpenMP 运行库；补充现有 MATLAB 的运行库路径后成功启动，未修改二进制文件。原代码构建依赖与运行建议见 [`docs/ORIGINAL_CODE.md`](../../docs/ORIGINAL_CODE.md)。
