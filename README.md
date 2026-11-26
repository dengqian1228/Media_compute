# 媒体计算课程大作业：L0 梯度最小化图像结构平滑与边缘提取

本项目实现课程第 4 题：自行实现 L0 梯度最小化结构平滑，并比较平滑前后的边缘提取结果；额外功能为 Clip-art JPEG 压缩伪影处理。具体评分和交付要求见 [docs/requirements.md](docs/requirements.md)。选题正式归属仍待确认。

## 双人分工

| 成员 | 姓名 | 工作范围 |
| --- | --- | --- |
| 成员 A | 章小龙，学号 2023010725。Git 提交身份 `Zhang XiaoLong` 已由本人确认 | L0 平滑核心算法；λ、κ 控制和多组图像实验；灰度、彩色图像读写与结果复现；相同参数的原图／平滑图边缘检测对照；提供基础算法与实验说明。 |
| 成员 B | 蒋天乐，学号 2023010721 | Clip-art JPEG 压缩伪影处理；PSNR、SSIM 及全图、局部对照；Demo、报告和交付材料整合。 |

以上为协作范围；代码、实验和材料由 AI Agent 辅助实现并验证，详见 AI_LOG.md。双方的人工理解、结果核验与课堂展示由本人完成，不把自动检查当作成员已理解或课程已获分。

## 快速开始与材料入口

当前网页展示结构平滑、同参Canny、JPEG与指标三个部分，可直接打开[离线Demo](docs/demo_interactive.html)。也可使用系统Python启动本地网页：

```bash
python3 -m scripts.demo_server
```

打开终端打印的网址，默认 `http://127.0.0.1:8765/`。三个页面支持参数滑块、真实迭代、曲线与局部。无需虚拟环境或联网。Windows用 `python -m scripts.demo_server`。[当前操作、来源与核对](docs/demo_course.md)。

[全屏演示PPTX](docs/L0_图像结构平滑与边缘提取_全屏演示版.pptx) · [44秒三段演示视频](docs/media/demo_three_sections_v2.mp4) · [讲稿](docs/presentation_course_notes.md)。

网页已移除读写与复现页面，相关核心接口、服务API和历史结果保留。当前视频依次展示全图结构平滑、同局部边缘提取、同局部论文素材。所有展示素材来自真实照片、论文官网或注明作者的公开作品。

需要实际计算并生成单次结果页时，使用下面的 CLI Demo：

在项目根目录直接使用系统 Python 3.10+ 运行：

```bash
python3 -m scripts.demo --mode all
```

已有依赖时无需安装。若提示缺少 NumPy、Pillow 或 OpenCV，再执行：

```bash
python3 -m pip install --user -r requirements-member-b.txt
```

当前启动方法不创建或激活虚拟环境。此前记录中的 `/tmp/media-compute-*` 仅是历史测试环境，可能已被清理，不用作启动路径。Windows 使用系统 `python` 执行相同命令，详见 Demo 说明。

终端打印离线 `index.html` 的路径，直接用浏览器打开。CLI 实际计算本组算法；调整参数后重新运行，离线页只显示本次结果。默认照片 λ=.02、JPEG λ=.008 / Q30，κ=2，βmax=1e5。

- [Demo 操作与已归档离线页](docs/demo.md)
- [课程报告](docs/report.md) · [可打印报告 HTML](docs/report.html)
- [9 分钟双人展示](docs/presentation.md) · [离线幻灯片](docs/presentation.html) · [讲稿与排练安排](docs/presentation_notes.md)
- [JPEG 全图、局部和指标实验](results/jpeg_artifacts/README.md) · [成员 B 独立核对记录](results/member_b_verification/README.md)
- [交付核对表](docs/delivery_checklist.md) · [AI 使用日志](AI_LOG.md)

## 目录

| 路径 | 用途 |
| --- | --- |
| `docs/requirements.md` | 带 PDF 页码的课程要求和实施建议。 |
| `docs/algorithm.md` | 学习提纲、核心代码与公式对应关系。 |
| `AI_LOG.md` | 两位成员共用的 AI 使用总日志。 |
| `AGENTS.md` | 项目智能体工作规则。 |
| `l0_smoothing/` | L0 核心模块、8 位图像读写、单图命令行运行与复现。 |
| `tests/` | 核心和读写复现流程的小规模自动验证。 |
| `data/验证样例/` | 本轮合成的灰度与 RGB 流程验证输入及来源说明。 |
| `results/验证运行/` | 本轮实际运行和复现的输入副本、输出及 JSON 记录。 |
| `data/structure_smoothing/` | 三幅真实图像的下载原件、预处理输入、来源／许可与 SHA-256 清单。 |
| `results/structure_smoothing/` | 18 组参数实验、CSV、全图／局部对照和复现抽查。 |
| `scripts/structure_smoothing_experiment.py` | 归档输入预处理、参数网格运行及结果审计。 |
| `results/edge_comparison/` | 原图与全部平滑结果的 Canny 边缘图、全图／局部对照和复现检查。 |
| `scripts/edge_comparison.py` | 对已保存结果做固定参数的 Canny 检测及逐像素复核。 |
| `docs/basic30_checklist.md` | 基础 30 分逐项证据与待人工核验事项。 |
| `requirements.txt` | 成员 A 归档环境，原文件保留。 |
| `requirements-member-b.txt` | 成员 B 本轮实际使用的固定依赖版本。 |
| `scripts/jpeg_artifacts.py`、`l0_smoothing/metrics.py` | JPEG 生成、批量实验、PSNR／SSIM 和审计。 |
| `data/jpeg_artifacts/`、`results/jpeg_artifacts/` | 干净 Clip-art 来源、JPEG 与 24 组真实恢复和正负结果。 |
| `scripts/demo.py`、`results/demo/` | CLI 三功能 Demo、离线结果页、复现检查。 |
| `docs/report.md`、`docs/presentation.md` | 报告和展示可编辑稿；同名 HTML 供离线阅读／展示。 |

课程原始 PDF 未复制进仓库；本轮上一级目录未附三份 PDF。`docs/requirements.md` 保留此前整理时的文件与页码，本轮未声称重新逐页复核原件。

## 当前进度

- 成员 A 的核心、读写和复现、三幅图 18 组平滑与 21 张固定参数 Canny 实验保留。成员 B 本轮独立审计产物、重算全部 Canny，并抽查三组核心复现：显示像素差 0，最大浮点误差约 1.395e-14（容差1e-12）。
- JPEG 额外功能已有 2 图 × 3 质量 × 4 λ 共 24 组，全部正负结果保留，PSNR/SSIM 全图及固定 ROI 指标有 30 行；独立重算最大 SSIM 差约 2.052e-13。见实验 README。
- 三功能 Demo 支持灰度／RGB、自选平滑输入及 λ／κ／JPEG 质量；生成可离线移动的内嵌图片结果页。14 项自动测试通过。本轮环境与成员 A 原环境分开记录，没有覆盖原依赖。
- 报告及双人9分钟展示材料按实际数据编写；具体交付检查见核对表。上述是智能体实现与验证，课程评分、成员人工核验及课堂展示均待本人完成。
- 成员 B 登记为蒋天乐，2023010721；本轮确认的 Git 身份为 `蒋天乐 <jtl23@mails.tsinghua.edu.cn>`。成员 A 已确认课程登记信息为章小龙，学号 2023010725。
- 当前目标仓库为 `git@github.com:dengqian1228/Media_compute.git`；真实历史以 `git log` 为准。既往普通 AI 问答、两人人工核验、最终场次与展示电脑适配仍需按实际补齐。

## 成员本人待完成

1. 两人核对整体算法、代码、正反例及固定 Canny 比较，按实际观察填写人工核验结果。
2. 在展示电脑运行 Demo、打开离线材料，按9分钟安排排练；现场展示由本人完成。
3. 补齐此前完整 AI 问答并核对最终通知；不能把待补项填成已通过。

核心接口为 `l0_smoothing.smooth_l0(image, lambda_=0.02, kappa=2.0, beta_max=1e5)`：输入为 `[0,1]` 的 `H×W` 灰度或 `H×W×3` RGB 浮点数组；返回对象包含 `image`、`parameters`、`iterations` 和 `elapsed_seconds`。实现约定和公式映射见 [docs/algorithm.md](docs/algorithm.md)。

## 单图运行与复现

成员 A 原运行环境见 [requirements.txt](requirements.txt)，成员 B 当前环境见 [requirements-member-b.txt](requirements-member-b.txt)。命令在项目根目录运行。下面第一条来自成员 A 的实际灰度样例，彩色样例可改输入路径和参数。

```powershell
python -m l0_smoothing run 'data/验证样例/灰度样例.png' --output-dir 'results/验证运行' --lambda 0.02 --kappa 2 --beta-max 100000
```

每次运行会新建 `run-UTC时间-随机标识/`，打印其中 `run.json` 的完整路径。目录含原输入文件副本、`output.npy`（未裁剪的 float64 结果）、`output.png`（仅显示时裁剪到 `[0,1]` 并量化为 8 位）及 `run.json`（输入摘要、参数、迭代次数、耗时和环境版本）。只支持 Pillow 读取为 8 位 `L` 或 `RGB` 的图像，其他模式会报错。

把上条命令输出的真实 `run.json` 路径作为复现输入：

```powershell
python -m l0_smoothing replay 'results/验证运行/<实际运行目录>/run.json' --output-dir 'results/验证运行'
```

复现默认读取记录内的输入副本；可加 `--input` 指定另一文件。程序先核对图像模式、形状及解码后的像素，再按记录的参数重算。`run.json` 记录输入文件字节是否相同，但同像素的不同 PNG 编码不会单独造成失败；浮点结果按最大绝对误差 `1e-12` 比较，显示结果按解码后像素精确比较。可用 `--float-atol` 调整浮点容差。每次复现也新建目录并写入比较结果；返回码 0 表示匹配，1 表示输出不匹配，2 表示输入、记录或参数错误。已有目录不会被覆盖。

## 成员 B：论文官网素材对照版（2026-11-25）

[早期论文对照PPTX](docs/L0_图像结构平滑与边缘提取_论文对照版.pptx)、[对应PDF](docs/L0_图像结构平滑与边缘提取_论文对照版.pdf)保留A的前5页，B部分改用作者官网西瓜和蜗牛JPEG输入，实际比较作者输出与本组结果。原版材料和合成真值实验均保留。

运行 `python3 -m scripts.paper_comparison run`，然后打开打印的HTML路径；已归档输入，无需虚拟环境或联网。[实验、指标口径与运行说明](docs/paper_comparison.md)、[9分钟讲稿](docs/presentation_paper_notes.md)。

第9页提供 [51秒预录视频](docs/media/demo_paper_comparison.mp4)，已内嵌于上述PPTX；也可用[浏览器播放器](docs/media/demo_player.html)或系统播放器离线观看。[播放与录制说明](docs/demo_video.md)。
