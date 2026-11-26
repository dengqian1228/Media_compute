# 论文官网素材：作者结果与本组结果对照

成员 B：蒋天乐，2023010721。由 AI 实际下载、调用本组核心运行、计算指标和检查；成员人工核验与课堂展示待本人完成。

本次按用户要求将B展示图片优先改为论文官网公开的实际Clip-art。原合成数据、实验、Demo及队友最新PDF全部保留。

## 数据与比较范围

[作者样例页](https://jiaya.me/file/archive/projects/L0smoothing/ClipArt.htm)提供压缩输入和作者结果。使用西瓜（9）与蜗牛（20），原尺寸运行本组 `smooth_l0`，未使用作者算法代码。详细来源、原始字节摘要、采样和量化表见[数据清单](../data/paper_clipart/manifest.json)及[来源说明](../data/paper_clipart/README.md)。官网论文PDF下载链接本轮返回404，未声称核对了正文图片编号；采用的是可访问的作者项目补充样例。

**作者输出不是干净真值。** PSNR、SSIM在此仅表示本组输出与作者输出的一致程度，不能解释为恢复质量或优于论文。作者逐图λ、κ和原JPEG质量未公开，不能声称严格同参复现。原有合成数据的30行有真值指标仍保留，承担恢复质量评价。

## 参数与真实运行

两幅图各运行λ={0.002,0.008,0.02,0.08}，κ=2、βmax=100000，共8组。展示参数0.008沿用已有Demo默认值，在对比结果前确定，未以作者像素反向选取。所有结果均保存，包括强平滑差异。输入不缩放；指标使用保存的8位RGB PNG，data_range=255；SSIM沿用本组11×11高斯σ=1.5、valid、总体矩、逐通道平均口径。局部按同一ROI裁剪后单独计算。

运行入口：

```bash
python3 -m scripts.paper_comparison run
```

已归档输入后无需联网、虚拟环境或新增运行依赖。输出新的目录，打开终端打印的 `index.html`。页面内嵌全图和局部图，包含官网输入、作者结果、本组结果及四档参数表。

本轮命令：`python3 -m scripts.paper_comparison prepare`、`python3 -m scripts.paper_comparison run`；总耗时 6.765250 秒（含读写与制页）。环境和实际解释器见[experiment.json](../results/paper_comparison/paper-20261125T093231Z-ebe97260fc7e/experiment.json)，单次耗时不是跨机保证。核心浮点输出、输入副本和逐次run.json全部保留。

| 样例 | λ | 相对作者全图PSNR/dB | 相对作者全图SSIM | 相对作者局部PSNR/dB | 相对作者局部SSIM | 核心秒数 |
| --- | --- | --- | --- | --- | --- | --- |
| 9 | 0.002 | 31.6248 | 0.944975 | 30.8182 | 0.932538 | 0.694098 |
| 9 | 0.008 | 34.1725 | 0.977844 | 34.1871 | 0.976265 | 0.619603 |
| 9 | 0.02 | 33.1097 | 0.982801 | 32.4877 | 0.982888 | 0.581046 |
| 9 | 0.08 | 26.6266 | 0.959438 | 26.0830 | 0.961144 | 0.527739 |
| 20 | 0.002 | 34.0865 | 0.948550 | 32.4307 | 0.915339 | 0.484043 |
| 20 | 0.008 | 47.8521 | 0.997680 | 46.8396 | 0.997149 | 0.435389 |
| 20 | 0.02 | 33.0463 | 0.971310 | 32.7141 | 0.961757 | 0.414392 |
| 20 | 0.08 | 24.6336 | 0.903928 | 21.8589 | 0.844276 | 0.373505 |

在AI查看的全图与固定局部中，λ=0.008抑制了输入轮廓附近的杂色，蜗牛输出与作者公开结果尤其接近。西瓜仍有细边界差异。λ=0.08使蜗牛螺旋轮廓和细白边发生变化，西瓜轮廓也更平滑；这些观察支持参数敏感性讨论，不能据此推断未知真值或作者参数。PSNR与SSIM对西瓜不同参数的排序并不完全一致，完整表格均保留。

## 验证和材料

检查命令（目录替换为本次实际输出）：

```bash
python3 -m scripts.paper_comparison check results/paper_comparison/paper-20261125T093231Z-ebe97260fc7e
```

已检查产物摘要、全部8行全图/局部指标，并对两幅默认λ输入执行核心复现。真实检查记录在实验目录的 `checks-.../checks.json`。这不是成员人工核验。

- [离线对照结果](../results/paper_comparison/paper-20261125T093231Z-ebe97260fc7e/index.html)
- [完整一致性表](../results/paper_comparison/paper-20261125T093231Z-ebe97260fc7e/author_agreement.csv)
- [论文对照版PDF](L0_图像结构平滑与边缘提取_论文对照版.pdf)
- [论文对照版PPTX](L0_图像结构平滑与边缘提取_论文对照版.pptx)
- [B部分讲稿](presentation_paper_notes.md)
- [图片来源和导出检查](presentation_paper_assets.json)

PDF前5页直接保留队友最新PDF原页面，并逐页栅格化比较一致。PPTX前5页以整页图片导入，B的后5页文字和图片可独立编辑。原版PDF/HTML/讲稿未覆盖，最新对照版使用上面单独的文件名。课前需在PowerPoint或WPS检查实际字体及投影显示，不能把PDF预览当成PowerPoint渲染验证。

生成材料的可选依赖列于 `requirements-presentation.txt`，与Demo运行依赖分开。本轮仅安装到 `/tmp/media-presentation-tools` 供工具使用，没有创建虚拟环境或改变系统包。具备这些工具和中文字体的环境可运行：

```bash
python3 -m scripts.build_paper_presentation --experiment results/paper_comparison/paper-20261125T093231Z-ebe97260fc7e
```

默认使用Linux的文泉驿字体；其他机器用 `--font` 指定可嵌入的中文TrueType字体。本轮实际生成命令额外设置 `PYTHONPATH=/tmp/media-presentation-tools` 以使用临时目录的制稿依赖；该临时路径不是后续启动Demo的要求。
