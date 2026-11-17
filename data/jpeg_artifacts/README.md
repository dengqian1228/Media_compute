# Clip-art JPEG 实验输入

这两幅干净图由本轮 AI Agent 生成的 `scripts/jpeg_artifacts.py:draw_clean` 程序绘制，没有使用外部图片、论文恢复图或现成 L0 接口，也不是蒋天乐本人手绘作品。固定几何坐标、无随机数：先在 768×768 画布绘制，再用 Pillow LANCZOS 一次缩为 256×256，以保留抗锯齿边缘。PNG 真值此前没有经过 JPEG 编码。源程序和干净像素都随项目保留，不声称它们是外部公共领域素材。

| 文件 | 内容 | 模式 | 固定局部区域 xyxy（右／下端不含） |
| --- | --- | --- | --- |
| `house_rgb.png` | 彩色小屋、窗框、太阳和草地；平坦色块、强边界和低对比装饰细线 | RGB 8位 | `[30,90,126,186]` |
| `line_gray.png` | 灰度圆形、对角线、矩形、三角形和低对比细线 | L 8位 | `[94,52,190,148]` |

局部区域在运行参数网格前从生成几何中固定，全部质量和 λ 使用相同坐标。合成数据便于获得可信的干净参考，不能代表自然图像、所有 Clip-art 或实际网络二次压缩的分布。

实际生成命令（项目根目录，2026-11-17 +08:00；精确 UTC 时间与环境见 `manifest.json`）：

```bash
/tmp/media-compute-venv/bin/python -m scripts.jpeg_artifacts prepare
```

普通环境可用自己的 `python` 执行同一模块。`prepare` 不覆盖不同的现有图片；重复执行会验证生成像素及清单。文件 SHA-256、解码像素 SHA-256、模式、尺寸和本轮 Pillow 版本见 [manifest.json](manifest.json)。不同 Pillow 版本若生成像素不同，应保留归档输入，在新目录另做对照，不能覆盖真值。

JPEG 压缩输入保存在每次实验目录，不回写这两幅干净图。实验使用 Pillow JPEG 编码，quality={10,30,70}，RGB 设 subsampling=0（4:4:4）以主要观察量化、振铃和块状误差；L 无色度采样。关闭 optimize 和 progressive。质量参数不是跨编码器通用质量尺度。每个 `jpeg.json` 保留真实质量参数、采样、JPEG 量化表、编码器版本、文件大小和摘要。

PSNR／SSIM 公式参考 [SSIM 原作者页面](https://www.cns.nyu.edu/~lcv/ssim/)；RGB SSIM 通道等权平均是本组明确约定，区别于原作者网页对彩色图的 `rgb2gray` 预处理；指标协议见实验 README 与 `l0_smoothing/metrics.py`。
