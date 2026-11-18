# 本地 Demo：运行程序，再打开离线结果页

成员 B：蒋天乐，学号 2023010721。本阶段由智能体实现并执行验证。课堂操作和人工核验由成员本人完成，当前没有记录为已完成。

## 运行环境

在项目根目录使用 Python 3.10 或以上版本。成员 B 实际验证环境是 Python 3.10.12、NumPy 2.2.4、Pillow 11.3.0、opencv-python 4.13.0.92（cv2 4.13.0）。依赖见 `requirements-member-b.txt`；成员 A 原环境记录保留在原 `requirements.txt`。

当前 Linux／WSL 直接使用系统 `python3`，在项目根目录运行：

```bash
python3 -m scripts.demo --mode all
```

已有依赖时无需安装。只有出现缺少 NumPy、Pillow 或 OpenCV 的提示，才执行用户目录安装，然后重试上面的命令：

```bash
python3 -m pip install --user -r requirements-member-b.txt
```

当前方案不创建或激活虚拟环境，也不需要 `sudo`。可用 `python3 -m scripts.demo --help` 查看参数。此前 `/tmp/media-compute-venv` 和 `/tmp/media-compute-clean` 是历史测试环境，临时目录可能已被清理，不能作为当前启动路径；历史验证记录保留在本文后半部分。

Windows 使用系统安装的 `python`，把命令中的 `python3` 换成 `python`；缺依赖时同样用 `python -m pip install --user -r requirements-member-b.txt`。

程序运行不联网、不启动服务器。固定依赖已在 Python 3.10.12、Linux／WSL2 的干净虚拟环境完成安装与运行验证；Windows 安装和图形浏览器仍待成员在展示电脑核验。

2026-11-19 补充验证使用系统 `/usr/bin/python3` 直接运行完整 Demo 和 `check`，没有安装新依赖：14 张内嵌图及两组核心复现通过，最大浮点误差和不同显示像素数均为 0。解释器 `sys.prefix` 与 `sys.base_prefix` 均为 `/usr`，不是虚拟环境；实际命令和结果见 [系统 Python 验证记录](../results/demo/system_python_verification.json)。

每次运行在 `results/demo/demo-<UTC时间>-<随机标识>/` 新建目录。终端打印 `index.html` 和 `demo.json` 路径。使用浏览器直接打开 `index.html`；14 张图和样式均内嵌，移动这个 HTML 文件也可查看。调整参数需要重新运行 CLI，离线页仅展示本次真实结果，不在浏览器中重新计算。

默认 `all` 模式包括：照片 L0 平滑、同参数 Canny 边缘对照、Clip-art JPEG 去伪影。照片默认 λ=0.02；JPEG 默认 λ=0.008、Q=30；共同 κ=2、βmax=100000。两个 λ 分别设定，避免误把照片参数当作 JPEG 推荐参数。

## 课堂建议操作

先运行默认 Demo，并打开打印的结果页。依次观察原图／平滑图及相同局部、原图／平滑图的同参 Canny、干净图／JPEG／恢复及同区域放大与指标。Canny 始终采用阈值 60/120、孔径 3、L2 梯度；RGB 统一转灰，无额外模糊。

再运行一个保留的失败案例：

```bash
python3 -m scripts.demo --mode jpeg --clipart line_gray --quality 70 --lambda 0.03
```

观察细灰线消失，并说明强平滑会把真实细线当作低幅度变化清除。这个案例的 PSNR 和 SSIM 均下降，不能只凭画面更平整判断恢复成功。

只演示平滑，可使用灰度或彩色的 8 位 L/RGB 文件：

```bash
python3 -m scripts.demo --mode smooth --input data/structure_smoothing/inputs/brick_window_gray.png --lambda 0.02 --kappa 2
python3 -m scripts.demo --mode all --smooth-lambda 0.02 --jpeg-lambda 0.008 --quality 30
```

`--lambda` 用于单独的 `smooth` 或 `jpeg` 模式；在 `all` 中必须分别使用 `--smooth-lambda`、`--jpeg-lambda`。JPEG `--quality` 为 1–95，κ>1，λ>0，βmax>2λ。自选平滑输入的来源和许可需要运行者另行登记，不会自动宣称拥有授权。

## 保留文件与复现

每组平滑复用 `run_and_save`，保存原输入字节副本、未裁剪 float64 `output.npy`、仅显示时裁剪量化的 `output.png` 和 `run.json`。JPEG 源自归档的干净几何绘图，重新编码真 JPEG；主指标对同一干净图计算。全图 PSNR 以全部通道均方误差、值域 255 计算；SSIM 为 11×11 高斯窗、σ=1.5、总体矩、有效窗口中心、RGB 逐通道平均。局部指标对固定 ROI 再裁剪重算。详细约定保留在 `jpeg/metrics.json`。

`demo.json` 保存真实命令、工作目录、参数相关的运行记录路径、环境、总耗时和产物 SHA-256。对终端输出目录执行：

```bash
python3 -m scripts.demo check 'results/demo/<实际demo目录>'
```

`check` 核对全部产物摘要，解析离线页且解码每张内嵌 PNG，重算 Canny 和 JPEG 指标，再分别从已保存输入副本运行核心复现。每次新增 `checks-.../checks.json`，不覆盖旧结果。返回码 0 为通过、2 为参数或检查失败。原始算法复现也可直接使用 `python3 -m l0_smoothing replay <真实run.json路径> --output-dir <新目录>`。

## 本轮实际运行与限制

实际命令中的 `python` 均为 `/tmp/media-compute-venv/bin/python`，工作目录为项目根目录：

| 运行命令 | 结果与验证 |
| --- | --- |
| `python -m scripts.demo --mode all --output-dir results/demo/中文验证` | [完整演示页](../results/demo/中文验证/demo-20261117T155441Z-d0d62b1d3d75/index.html)，总耗时 2.221 秒；照片核心 0.858 秒、JPEG 核心 0.253 秒；14 张内嵌图。 |
| `python -m scripts.demo --mode jpeg --clipart line_gray --quality 70 --lambda .03 --output-dir results/demo/中文验证` | [灰度失败例页](../results/demo/中文验证/demo-20261117T155455Z-928d25ba4500/index.html)，总耗时 0.395 秒；JPEG 核心 0.069 秒；6 张内嵌图。 |
| `python -m scripts.demo --mode smooth --input data/structure_smoothing/inputs/brick_window_gray.png --lambda .02 --output-dir results/demo/中文验证` | [灰度平滑页](../results/demo/中文验证/demo-20261117T155531Z-8e32d836016f/index.html)，总耗时 0.823 秒；核心 0.309 秒；8 张内嵌图。 |

上述三个目录各执行同一 `check <实际目录>`，均通过；每组复现的最大浮点误差 0、不同显示像素数 0。完整演示检查见 [checks.json](../results/demo/中文验证/demo-20261117T155441Z-d0d62b1d3d75/checks-20261117T155504Z-a3b1770669f6/checks.json)，灰度失败例检查见 [checks.json](../results/demo/中文验证/demo-20261117T155455Z-928d25ba4500/checks-20261117T155504Z-07073655e60f/checks.json)。以上耗时只是本机本次结果，不是跨机器基准。

参数拒绝已实际检查：`--quality 100`、`--kappa 1`、`--lambda nan` 及 `all --lambda .01` 均返回码 2。检查发现单模式 βmax 原先误受另一个未运行模式的默认 λ 约束，已修正为仅检查启用阶段的 λ；不是算法核心修改。

本机没有图形浏览器，验证范围是 CLI、产物、内嵌图片解析和数值复现，未声称已完成浏览器视觉核验、投影适配、现场运行或录像。课堂前两人应在展示电脑打开上述离线页、实际运行一次 CLI、确认显示缩放和耗时。现场 CLI 出现问题时可打开已归档完整演示页和失败例页，明确说明它们是本轮预计算结果。

## 干净环境补充验证

在 `include-system-site-packages=false` 的独立虚拟环境 `/tmp/media-compute-clean` 中安装 `requirements-member-b.txt` 后，实际执行 `python -m unittest discover -s tests -v`，14 项测试通过（2.130 秒）。实际执行 `python -m scripts.demo --mode all --output-dir results/demo/全新环境验证`，得到 [完整演示页](../results/demo/全新环境验证/demo-20261117T155744Z-eac941107dcc/index.html)；随后对该目录执行 `python -m scripts.demo check <实际目录>`，产物、指标、14 张内嵌图及两次核心复现均通过。完整环境、包路径、安装执行者与命令、实际耗时和检查路径见 [clean_environment_verification.json](../results/demo/clean_environment_verification.json)。这次补充验证保留原先三个 Demo 目录，未覆盖历史结果。
