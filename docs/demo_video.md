# 第9页：预录演示视频

- [独立MP4](media/demo_paper_comparison.mp4)
- [浏览器播放器](media/demo_player.html)
- [含内嵌视频的PPTX](L0_图像结构平滑与边缘提取_论文对照版.pptx)

视频长 **51.16秒**，1280×720、25fps、H.264/yuv420p MP4，无声，未加速。第9页总预算75秒，可留约24秒介绍与收尾。放映时点击画面播放，边播放边讲解。视频文件已嵌入PPTX，不依赖录制工具、网络、Python或临时目录。

为避免播放器兼容问题，课前在展示电脑用PowerPoint/WPS试播，并同时准备独立MP4；若嵌入视频不能播放，直接用系统播放器打开MP4。PDF第9页是视频封面，PDF本身不播放视频。复制浏览器播放器时，把 `docs/media/` 整个目录一起复制。

## 视频内容与讲解

1. 启动：浏览器录制页面调用系统Python，真实执行本组CLI；画面显示实际stdout。
2. 西瓜：官网JPEG、作者输出与本组输出的全图及同一局部。
3. 蜗牛：默认参数结果、局部细节与λ=0.08强平滑对照。
4. 指标：展示本次运行四档参数的实际一致性表。

开场可说：“下面播放本组程序的预录演示，展示从实际计算到结果对比的完整流程。”视频无声，由本人同步讲解，不把预录结果说成课堂现场实时运行。

## 可复现性和验证范围

本次视频由Playwright实际录制Chromium浏览器页面，再转码为H.264。界面中的命令由本地服务执行，不是手工编造的终端记录。浏览结果时增加了标签切换与录屏排版，图片、参数和指标来自同一次真实运行，未修改结果像素。它是浏览器内容录屏，不是Windows桌面或PowerPoint播放录屏。

实际命令：

```bash
/usr/bin/python3 -m scripts.paper_comparison run --output-dir results/paper_comparison/video_demo
```

[本次实验记录](../results/paper_comparison/video_demo/paper-20261125T094931Z-5866f9217397/experiment.json)。录制时间、命令、返回码、stdout、浏览时间线、原始WebM、MP4摘要和转码命令见[录制清单](media/demo_paper_comparison.json)。实际录制目录为 `results/demo_video/record-20261125T094927Z/`。

MP4完成全段FFmpeg解码检查。PowerPoint/WPS实际播放仍需在展示机验证；不能用文件结构检查代替Office播放测试。

## 重新录制与导出

录制工具位于 `scripts/record_demo_video.py`，可选依赖见 `requirements-video.txt`。本轮依赖与Chromium仅安装到/tmp下的工具目录，没有创建虚拟环境或更改系统Python包；运行Demo与播放视频不依赖这些工具。工具齐备时，用 `--output` 指定新视频路径，程序拒绝覆盖已有成片：

```bash
python3 -m scripts.record_demo_video --output docs/media/demo_paper_comparison_take2.mp4
```

本轮实际命令另设 `PYTHONPATH=/tmp/media-video-tools` 和 `PLAYWRIGHT_BROWSERS_PATH=/tmp/media-playwright-browsers` 来定位录制工具。该路径仅是本轮制稿环境，不是后续视频播放或Demo启动要求。

`build_paper_presentation.py` 使用 `docs/media/demo_paper_comparison.mp4` 及同名PNG封面、JSON清单导出第9页。重新使用另一段成片时须同步路径或文件及清单，不能只替换MP4而留下旧摘要。

## 本轮补充检查

Chromium实际打开播放器并播放成功，视频元信息为51.16秒、1280×720，并在18、36、48秒定位播放、查看画面。PPTX第9页的内嵌MP4与独立文件SHA-256相同，视频关系未引用外部路径；其余9页PDF渲染像素与修改前一致。记录见 `results/demo_video/playback_check.json` 与 `presentation_check.json`。这些检查不等于PowerPoint/WPS实机试播。
