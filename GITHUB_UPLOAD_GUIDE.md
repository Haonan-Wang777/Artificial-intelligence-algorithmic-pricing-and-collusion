# GitHub 网页上传版

此版本与完整交付包使用相同的实验数据。为适配网页上传，将数千个逐会话记录及部分作者补充文件打包在 `_archives/`；代码、报告、主要图表和汇总结果直接可见。所有上传文件合计不超过100个，每个文件小于25 MiB。

## 上传步骤

1. 解压 `github_web_upload.zip`，打开其中的 `calvano-pricing-reproduction` 文件夹。
2. 在 GitHub 新建或打开目标仓库，选择 **Add file → Upload files**。
3. 将该文件夹里面的全部文件和文件夹一起拖入上传区域，填写提交说明并点击 **Commit changes**。若仓库为空，先点击首页 **uploading an existing file**。
4. 上传后仓库根目录应直接出现 `README.md`、`REPRODUCTION_REPORT.md`、`src/`、`results/`、`_archives/` 等。

**上传时不要解压 `_archives/` 中的小ZIP。** 它们作为普通文件上传，用来避开网页文件数量限制。也不需要上传最外层的 `github_web_upload.zip`，更不要继续上传旧的数千文件版本。

若文件选择窗口不显示以点开头的配置文件，请启用显示隐藏文件，或补充上传 `.github`、`.gitignore`、`.gitattributes`。这些文件已计入100个的预算。

## 导师如何检查

README、中文报告、作者Table1及56格误差表、Python和作者程序的主要图表可直接在仓库查看，无需解压数据。

需要完整逐会话记录时，在项目根目录运行：

```text
python experiments/restore_assets.py
```

此命令只使用Python标准库，验证每份压缩包和每个恢复文件的SHA256，恢复原目录与原字节；已存在且相同的文件跳过，已存在但不同的文件不会被覆盖。运行一次后会恢复数千文件，这是本地核查所需，**不需要再把这些展开文件上传到GitHub**。

也可以直接按README运行 `python reproduce.py --quick` 或正式复现命令：网页版本的一键入口会先自动恢复这些文件，再运行原有实验流程。原始训练代码及已有数据、图表、指标不变。单独执行核验、作者源码构建或某个分析脚本前，请先运行恢复命令。

`_archives/manifest.json` 记录压缩包及全部被归档文件的校验值。`UPLOAD_MANIFEST.json` 记录网页版本各上传文件的数量、大小和校验值。原完整交付包仍可作为独立备份保留。

GitHub官方说明：网页每次最多上传100个文件，每个文件最大25 MiB。[添加文件到仓库](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)。
