# 参数与结果对照 Demo

成员B：蒋天乐，2023010721。本页说明当前可操作的功能和实际检查结果。课程评分、两位成员的人工核验与课堂展示由本人完成。

## 打开 Demo

在项目根目录使用系统 Python：

```bash
python3 -m scripts.demo_server
```

Windows 系统 Python 对应命令：

```powershell
python -m scripts.demo_server
```

打开终端打印的网址，默认是 `http://127.0.0.1:8765/`。不用创建或激活虚拟环境，不依赖互联网。终端保持运行；结束时按 Ctrl+C。 如果更新服务代码后仍看到旧错误，请先Ctrl+C停止旧进程，再重新执行启动命令。端口占用时可加 `--port 8766`。

已有 NumPy、Pillow、OpenCV 时无需安装。缺少依赖再用系统 Python 执行 `python3 -m pip install --user -r requirements-member-b.txt`；Windows 将 `python3` 改为 `python`。

也可直接双击 [离线入口](demo_interactive.html)：当前三个页面全部可离线交互，不需要启动Python。读写与复现页面已移除，相关程序接口和历史证据保留。

## 三页分别演示什么

| 页面 | 课程功能 | 可以实际操作的内容 |
| --- | --- | --- |
| ①结构平滑 | 基础18分 | 三幅图，λ／κ滑块，22轮真实迭代逐步播放，全图／同一局部，前后分割拖动，原计算耗时曲线 |
| ②同参Canny | 基础6分 | 原图／平滑图／两张边缘图；改变λ、κ、迭代轮次或Canny阈值对；两张图检测参数始终相同 |
| ③JPEG与指标 | 额外6+4分 | 外部公开干净图生成JPEG，动态调整Q／λ／κ；干净图、压缩图、恢复图及同ROI；PSNR／SSIM基线和恢复曲线；另有论文作者对照 |

每页都能自动往返播放，点击曲线也能切换当前档位。页面显示“当前第几档／总档数”；论文页的三档按钮只是快捷跳转，λ仍有45档完整结果。全图和局部之间切换会保留当前参数，避免比较条件改变。参数序列是实际计算的有限采样，不做图像插值。

页面下方还有算法说明、课程条目映射、素材来源、环境、参数与运行记录入口。报告和本人讲解属于独立交付，Demo提供展示依据，不等于这些评分项自动完成。

## 参数、迭代与Canny

- λ：.001—.08，共45档，对数采样并加入.005、.008、.02、.04；固定κ=2。
- κ：1.5—2.5，步长.05，共21档；照片固定λ=.02，JPEG固定λ=.008。
- Q：5—95，步长5，共19档；固定λ=.008、κ=2。只对明确生成的受控JPEG启用。
- JPEG的λ／κ序列固定Q30。βmax全部为100000。
- Canny默认60/120、孔径3、L2gradient=True，RGB先统一转灰。阈值对序列为低阈值20—140、步长10，高阈值始终为低阈值两倍；此序列固定照片λ=.02、κ=2。

三幅照片的迭代帧来自本组核心的真实 `_fft_update` 返回值，使用Python观测钩子收集，没有改动核心。每幅λ=.02、κ=2实际运行22轮，显示当轮β与λ/β；最终帧与对应缓存像素完全一致。逐轮计时包含观测开销，不能与普通运行直接作性能比较。κ会改变迭代次数及输出，不是单纯的加速开关。

## 素材与两种指标口径

照片仍采用A归档的沙滩、灰度砖墙和向日葵，见 [来源清单](../data/structure_smoothing/manifest.json)。

论文官网西瓜、蜗牛使用原JPEG与作者公开输出，见 [论文素材清单](../data/paper_clipart/manifest.json)。作者逐图参数、原JPEG质量和干净真值未公开。这里的PSNR／SSIM只表示与作者结果的一致程度；不冒充真值质量，也不据此宣称超过论文。

有干净参考的受控JPEG实验采用外部已有作品：

- OpenMoji狐狸：Sofie Ascherl，彩色SVG。
- OpenMoji乌龟：Robert Winslow，黑白线稿SVG。

两幅作品均为CC BY-SA 4.0。原SVG、许可与署名、固定上游commit、转换环境和摘要已归档：[来源与许可](../data/public_clipart/SOURCE_CREDITS.md)、[完整清单](../data/public_clipart/manifest.json)。不是本组自绘或AI生成，也不冒充论文图。先在白背景栅格化为256×256 PNG，狐狸为RGB、乌龟为L；该未经过JPEG的PNG是本次受控压缩的干净参考。JPEG采用记录的Q、4:4:4设置，关闭渐进与优化编码。所有恢复及JPEG基线都对同一参考计算全图和固定ROI指标。

## 论文西瓜与蜗牛怎样看变化

切到“论文官网·作者对照”后默认显示同一局部，按原像素放大。左侧JPEG输入和中间作者输出保持固定，右侧才随本组参数更新。可直接点三档按钮：λ=.001弱处理、.008去伪影对照、.08强平滑，均固定κ=2。

西瓜重点看眼睛、眉毛和嘴边的杂色，蜗牛看螺旋白边与橙色区域的条纹。κ=1.5到2.5端点的输出平均每通道只差约1.33／1.42个8位灰度级，外观变化较小；不要把κ当作主要平滑强度。λ=.08虽然变化显著，也会改变颜色和轮廓，属于需要讨论的过平滑情况。

[西瓜局部三档与输入](../results/course_demo/paper_visibility/paper_9_roi_comparison.png)、[蜗牛局部三档与输入](../results/course_demo/paper_visibility/paper_20_roi_comparison.png)。这两张对照只对既有结果裁剪和最近邻放大，没有改写结果像素或重新压缩输入。[逐像素差异分析](../results/course_demo/paper_visibility/analysis.json)、[浏览器检查](../results/course_demo/paper_visibility/browser_check.json)。当前第9页视频对西瓜和蜗牛都完整展示45档λ，同一局部连续切换；旧的三档停留录像单独归档。

## 正例与失败情况

两幅公开图共166组恢复，38个JPEG基线。所有结果都保留，其中29组全图PSNR下降、14组全图SSIM下降。

| 展示案例 | 参数 | 全图PSNR：JPEG→恢复 | 全图SSIM：JPEG→恢复 |
| --- | --- | --- | --- |
| 狐狸改善 | Q30、λ=.017259、κ2 | 31.2301→32.7107 dB | .946113→.974424 |
| 乌龟过平滑 | Q30、λ=.08、κ2 | 31.9761→26.7794 dB | .972928→.958181 |

选择③的受控JPEG，固定Q30拖动λ，结合局部检查轮廓变化；再切到Q滑块，观察压缩程度改变后同一恢复参数的收益。指标变差的档位会明确显示，不能把平坦区域更干净直接当成恢复质量更好。课程原始PDF当前未附在项目目录，功能映射依据 [既有要求摘录](requirements.md)。

## 实际产物和检查

当前三页浏览器检查：[186项参数／视图与交互核对](../results/course_demo/browser_checks/check-20261125T134113Z-416e1392af1f/checks.json)，并确认读写页控件已不存在。

以下缓存和既有检查保留原始记录；其中历史IO浏览器检查对应移除页面前的版本，不能当作当前网页仍有IO入口。

当前 [完整缓存](../results/course_demo/course-20261125T125030Z-ada4fa81e776/index.html) 包含557个L0显示帧：照片与论文参数325帧、公开JPEG恢复166帧、照片实际迭代66帧，另有39对Canny阈值比较。缓存整理耗时55.604秒，包含复制、迭代观测、真实读写复现与制页；不把它当成557次算法求解时间。每帧参数及原计算耗时保存在manifest中。

- [完整缓存检查](../results/course_demo/course-20261125T125030Z-ada4fa81e776/checks-20261125T125239Z-c1ae2e2b8654/checks.json)：2041项文件摘要、557帧、全量指标／ROI／Canny、39对阈值及RGB/L实际复现通过。
- [公开JPEG独立检查](../results/public_jpeg_demo/public-jpeg-20261125T124736Z-cc942891889c/checks-20261125T124840Z-1be84ca7b43d/checks.json)：166组指标及38基线重算，RGB/L各抽查一组浮点和显示复现。
- [浏览器交互检查](../results/course_demo/browser_checks/check-20261125T125228Z-672c8edda17e/checks.json)：186个动态位置、曲线／分割／自动播放、离线证据及本地实际运行复现通过，无JS错误或外部网络请求。
- [错误状态检查](../results/course_demo/browser_checks/io-error-check-20261125T125337Z-d8d98eb8a280/checks.json)：超大／损坏上传、无效参数、运行期间控件禁用、失败后不残留旧结果。
- 服务API测试位于 `tests/test_demo_server.py`；这些均为智能体验证，不是成员人工核验。

## 重建与检查

已有全部素材和缓存，课堂启动不需要重新预计算。需要重建时，在项目根目录使用系统Python：

```bash
python3 -m scripts.public_jpeg_demo build
python3 -m scripts.course_demo build --jpeg results/public_jpeg_demo/public-jpeg-20261125T124736Z-cc942891889c
python3 -m scripts.course_demo check results/course_demo/course-20261125T125030Z-ada4fa81e776
```

第一条创建新的公开JPEG实验目录；若要合并新实验，将第二条的`--jpeg`改成第一条实际打印的目录。修改页面模板后，只需 `python3 -m scripts.course_demo render results/course_demo/course-20261125T125030Z-ada4fa81e776`，不必重跑算法。

参数预计算复用既有核心；服务调用原 `run_and_save` 与 `replay_record`。窗口中的真实迭代也直接调用原核心。没有调用作者L0实现或现成L0接口。旧实验和历史材料保留，当前入口以本页为准。

## 录像与PPT备用

[三段动态演示视频](media/demo_three_sections_v2.mp4)，[浏览器播放器](media/demo_course_player.html)。视频43.64秒，1600×1080、25fps、H.264，无声、正常速度；全部使用本组真实预计算图像，逐档操作，不做图像插值。

1. **结构平滑，全图**：沙滩，λ的45档、κ的21档和22步真实迭代。
2. **边缘提取，同一局部**：砖墙，对应λ的45档和同参Canny阈值对的13档。
3. **论文官网素材，同一局部**：西瓜与蜗牛，分别连续经过λ的全部45档，在λ=.008短暂停留。输入和作者结果保持固定，本组结果变化；作者一致性不是真值质量。

视频只包含上述三个部分。每次参数与图像状态保存在[录制JSON](media/demo_three_sections_v2.json)，检查记录见[播放与嵌入核对](../results/demo_video/three_sections_check.json)。

[全屏演示版PPTX](L0_图像结构平滑与边缘提取_全屏演示版.pptx)第9页为全页视频，无额外标题和介绍；[PDF](L0_图像结构平滑与边缘提取_全屏演示版.pdf)显示全页封面；[讲稿](presentation_course_notes.md)。A前5页保留，第6—10页不显示成员、建议用时和页码组成的灰色页脚，第10页仅显示“谢谢大家”。双人各270秒预算；第9页75秒预算中，约44秒播放、31秒讲解。未执行PowerPoint/WPS或投影实机核验，内嵌播放异常可直接打开MP4。

## 图片档位完整性复核

当前页面嵌入的数据与缓存manifest完全相同。重新读取2041项归档文件并核对摘要，2019个PNG/JPEG全部可解码；逐序列比较解码后的像素，λ45档、κ21档、Q19档、迭代22步及Canny13档均有对应文件，序列内全图及ROI像素均不同。浏览器逐档验证了1738个任务／参数／视图状态，全部实际图片路径与当前参数匹配。

[文件与像素复核](../results/course_demo/frame_coverage/audit.json)、[浏览器逐档记录](../results/course_demo/frame_coverage/browser_all_steps.json)、[档位计数显示检查](../results/course_demo/frame_coverage/counter_check.json)。这不是任意λ×κ×Q组合的全网格，只覆盖页面明确标注的单因素序列。相邻输出可能只有很小差异，例如公开狐狸／乌龟的κ相邻档平均每通道差都小于0.1个8位灰度级。

当前43.64秒录像的西瓜、蜗牛段分别实际经过全部45档λ；录制记录逐档检查了参数与图像对应关系。之前只选三档停留的录像保留归档。

PPT内嵌的[16:9视频](media/demo_three_sections_fullscreen.mp4)保持原始画面比例，左右补背景；三段内容、参数过程、43.64秒时长均与原录屏一致。生成命令（制稿依赖可用时，使用系统Python）：

```bash
python3 -m scripts.prepare_fullscreen_video
python3 -m scripts.build_paper_presentation --experiment results/paper_comparison/paper-20261125T093231Z-ebe97260fc7e
```
