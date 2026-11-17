# 媒体计算课程大作业：L0 梯度最小化图像结构平滑与边缘提取

本项目拟完成课程第 4 题：自行实现 L0 梯度最小化结构平滑，并比较平滑前后的边缘提取结果；额外功能为 Clip-art JPEG 压缩伪影处理。具体评分和交付要求见 [docs/requirements.md](docs/requirements.md)。选题归属及成员信息尚待填写或确认。

## 双人暂定分工

| 成员 | 姓名 | 暂定工作 |
| --- | --- | --- |
| 成员 A（本轮提出任务者） | 课程登记姓名待填写；Git 提交身份 `Zhang XiaoLong` 已由本人确认 | L0 平滑核心算法；λ、κ 控制和多组图像实验；灰度、彩色图像读写与结果复现；相同参数的原图／平滑图边缘检测对照；提供基础算法与实验说明。 |
| 成员 B | 待填写 | Clip-art JPEG 压缩伪影处理；PSNR、SSIM 及全图、局部对照；Demo、报告和交付材料整合。 |

双方各自记录 AI 使用情况，共同理解算法、交叉检查结果并准备答辩。分工可在实际协作后更新；上述分工不是已完成声明。

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
| `requirements.txt` | 实际运行环境使用的 NumPy、Pillow、OpenCV 版本。 |

课程原始 PDF 位于项目上一级目录，未复制进仓库。`docs/requirements.md` 标注了所依据的文件和页码。

## 当前进度

- 已保留原有仓库及历史。L0 平滑纯数组核心模块、8 位灰度／RGB 读写、结果保存和按记录复现已由智能体实现；自动验证通过，成员人工核验待完成。
- 本轮在 Python 3.13.14、NumPy 2.5.4、Pillow 13.0.0 下运行了 `python -m unittest discover -s tests -v`，10 项测试通过；此前两幅中文路径合成样例已完成流程验证。其他环境尚未验证。
- 三幅真实图像（两幅 RGB、一幅灰度）的 λ×κ 共 18 组结构平滑实验已由智能体运行；来源、许可、预处理、全部结果、对照图、CSV 和复现抽查见 [实验记录](results/structure_smoothing/README.md)。成员人工核验待完成。
- 已由智能体对三幅原图及 18 组已保存的平滑图执行统一参数 Canny，保存 21 张边缘图及全图／局部对照，复算像素一致；见 [边缘实验记录](results/edge_comparison/README.md) 和 [基础 30 分逐项核对](docs/basic30_checklist.md)。成员人工核验待完成。
- 界面、JPEG 去伪影、Demo、报告仍待完成；合成样例输出只作为流程验证。
- 既往 AI 对话、成员 B 身份及成员 A 的课程登记姓名仍待补充；`AI_LOG.md` 中的“待补充”不表示交付要求已满足。
- 成员 A 已确认本仓库使用 `Zhang XiaoLong <xiaolong23@mails.tsinghua.edu.cn>` 作为 Git 提交身份；仅仓库本地配置已设置。实际提交状态以 `git log` 和 `git status` 为准。

## 后续阶段

1. 双方阅读论文与课程要求，并人工核对核心代码、读写复现流程及自动验证结果。
2. 由成员复核输入、算法、平滑及固定 Canny 参数的边缘对照结果，补全基础 30 分的人工核验记录。
3. 成员 B 完成额外功能、指标和局部结果对照。
4. 整合 Demo、报告与交付材料，核对日志、Git 历史和双人展示内容。

核心接口为 `l0_smoothing.smooth_l0(image, lambda_=0.02, kappa=2.0, beta_max=1e5)`：输入为 `[0,1]` 的 `H×W` 灰度或 `H×W×3` RGB 浮点数组；返回对象包含 `image`、`parameters`、`iterations` 和 `elapsed_seconds`。实现约定和公式映射见 [docs/algorithm.md](docs/algorithm.md)。

## 单图运行与复现

本轮使用的依赖版本见 [requirements.txt](requirements.txt)。命令应在项目根目录运行；本轮环境已安装这些依赖，未验证重新安装过程。下面第一条是实际执行过的灰度样例命令，彩色样例只需改输入路径和参数。

```powershell
python -m l0_smoothing run 'data/验证样例/灰度样例.png' --output-dir 'results/验证运行' --lambda 0.02 --kappa 2 --beta-max 100000
```

每次运行会新建 `run-UTC时间-随机标识/`，打印其中 `run.json` 的完整路径。目录含原输入文件副本、`output.npy`（未裁剪的 float64 结果）、`output.png`（仅显示时裁剪到 `[0,1]` 并量化为 8 位）及 `run.json`（输入摘要、参数、迭代次数、耗时和环境版本）。只支持 Pillow 读取为 8 位 `L` 或 `RGB` 的图像，其他模式会报错。

把上条命令输出的真实 `run.json` 路径作为复现输入：

```powershell
python -m l0_smoothing replay 'results/验证运行/<实际运行目录>/run.json' --output-dir 'results/验证运行'
```

复现默认读取记录内的输入副本；可加 `--input` 指定另一文件。程序先核对图像模式、形状及解码后的像素，再按记录的参数重算。`run.json` 记录输入文件字节是否相同，但同像素的不同 PNG 编码不会单独造成失败；浮点结果按最大绝对误差 `1e-12` 比较，显示结果按解码后像素精确比较。可用 `--float-atol` 调整浮点容差。每次复现也新建目录并写入比较结果；返回码 0 表示匹配，1 表示输出不匹配，2 表示输入、记录或参数错误。已有目录不会被覆盖。
