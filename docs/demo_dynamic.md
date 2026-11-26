# 参数交互 Demo 与预录视频（上一版归档）

当前四项课程入口与真实读写复现见[完整Demo说明](demo_course.md)。下文保留上一版325帧材料记录，当前demo_interactive.html已指向四项功能页面。

直接双击 [demo_interactive.html](demo_interactive.html)，用 Chrome 或 Edge 打开。不需要启动 Python、虚拟环境、服务器或网络。页面读取已经用本组 L0 核心算好的图像。

1. 选择照片与 Canny 或论文 Clip-art，再选择图片。
2. 选择要变化的参数：λ或κ。
3. 拖动滑块，查看图像及对应数值。页面显示其他参数的固定值；可切换全图／同一局部，或开启自动往返播放。

照片包含沙滩、灰度砖墙和向日葵，显示原图、平滑图及同参 Canny；论文素材包含西瓜、蜗牛，显示官网输入、作者输出与本组输出。论文对照同时显示与作者输出的一致性 PSNR／SSIM。

## 参数与解释

| 滑块 | 预计算范围 | 保持固定 |
| --- | --- | --- |
| λ | 0.001—0.08，共45档；对数采样并加入常用值 | κ=2 |
| κ | 1.5—2.5，步长0.05，共21档 | 照片 λ=.02，JPEG λ=.008 |

所有计算 βmax=100000。Canny 始终使用阈值60/120、apertureSize=3、L2gradient=True，灰度转换方式相同。改变 κ 会改变优化迭代过程，不应解释为单调增强的平滑强度。

拖动切换的是离散采样点的真实计算结果；页面预加载当前序列，不进行图片插值，也不声称无限连续参数或实时执行算法。论文输入的原始 JPEG 质量未知，因此没有为它们提供 Q 滑块。作者结果不是真值：论文页指标只表示与作者输出的一致程度，不能据此宣称恢复质量更高。

## 离线文件与复现

入口依赖 [预计算目录](../results/interactive_demo/interactive-20261125T122838Z-fce049eb5fea/index.html) 中的图像，不要只复制入口 HTML。展示时可复制整个项目；也可以单独复制该预计算目录，直接打开其中的 `index.html`。来源、作者和许可见目录内 `SOURCE_CREDITS.md`。

该目录有325组唯一结果：三幅照片195组、两幅论文素材130组。缓存整理耗时21.621秒，全部复用已核对来源、核心及结果摘要的真实计算，并重新生成局部、Canny或指标；这不是325次算法求解耗时。`manifest.json` 保存输入来源／摘要、环境、命令、固定参数、逐组迭代次数、算法耗时、指标及图像摘要。保留原输入字节、无损显示 PNG 和浮点结果摘要；此展示缓存不逐帧保存 NPY，完整浮点数组可由核心重算。原实验中的 NPY 不受影响。

从项目根目录用系统 Python 重建新缓存：

```bash
python3 -m scripts.interactive_demo build
```

构建完成打印新目录；入口指向最新构建。重算成本取决于电脑配置。复核当前交付缓存：

```bash
python3 -m scripts.interactive_demo check results/interactive_demo/interactive-20261125T122838Z-fce049eb5fea
```

只刷新页面模板而不重算：

```bash
python3 -m scripts.interactive_demo render results/interactive_demo/interactive-20261125T122838Z-fce049eb5fea
```

智能体已核对全部325组图像摘要、局部、Canny或全图／局部指标，并按照片和论文素材两类输入各重算一组浮点及显示结果；[检查记录](../results/interactive_demo/interactive-20261125T122838Z-fce049eb5fea/checks-20261125T122929Z-c3545fbcd5fe/checks.json)。浏览器验证覆盖模式／素材切换、参数端点和中间值、自动播放、图片加载及无网络访问：[交互检查](../results/interactive_demo/real_sources_browser_checks/checks.json)。这些是智能体检查，现场电脑仍需本人打开确认。

## 第9页视频与展示

- [动态演示 PPTX](L0_图像结构平滑与边缘提取_课堂演示版.pptx)，第9页内嵌视频；[PDF](L0_图像结构平滑与边缘提取_课堂演示版.pdf)显示封面。
- [独立 MP4](media/demo_dynamic_real_sources.mp4) / [浏览器播放器](media/demo_dynamic_player.html)：44.76秒，1600×900、25fps、H.264，无声，正常速度。
- [9分钟讲稿](presentation_dynamic_notes.md)：A讲前5页，B讲后5页；第9页75秒中约45秒播放，余下时间用于开场与解释。

视频实际录制浏览器鼠标拖动：照片固定κ改变λ、固定λ改变κ、砖墙局部与Canny、论文蜗牛与西瓜的λ变化、蜗牛的κ变化。画面明确标注预计算，由本人同步讲解。每次显示的帧和参数记录在[录制元数据](media/demo_dynamic_real_sources.json)，不是课堂经历或实时算法运算记录。

制录工具为 `scripts/record_dynamic_demo.py`，依赖 Playwright、Chromium 和 imageio-ffmpeg；制稿工具为 `scripts/build_paper_presentation.py`。本次制录依赖放在 `/tmp` 工具目录，没有使用虚拟环境。播放交付文件不依赖这些临时目录。重新录制需指定新的输出文件，保留旧成片。

PPTX前5页按A的原PDF整页导入，其内容保持一致；B后5页文字与图片可编辑。尚未执行 PowerPoint／WPS 或投影实机播放检查；嵌入视频无法播放时，直接打开独立 MP4。
