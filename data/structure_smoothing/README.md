# 结构平滑实验输入与来源

三幅**原始下载文件**保留于 `sources/`，本组实际输入保留于 `inputs/`。文件大小、SHA-256、原始与处理后尺寸、模式及预处理步骤见 [manifest.json](manifest.json)。本轮只使用官网 `beach.png` 的**Input Images** 原图；官网同表中的 `*_s.png` 是作者的处理结果，没有用于本组输入或结果。

| 输入 | 来源与作者 | 来源页面所列许可 | 本组实际预处理 |
| --- | --- | --- | --- |
| `beach.png`（RGB） | [论文官网 Image Smoothing Examples](https://jiaya.me/file/archive/projects/L0smoothing/ImageSmoothing.htm) 中的 [输入原图](https://jiaya.me/file/archive/projects/L0smoothing/results/Smoothing/beach/beach.png)；官网页面未标作者 | **官网页面未注明图片许可**；公开再分发前须核实授权 | 800×533 RGB，EXIF 方向处理后转 8 位 RGB，LANCZOS 等比例缩至 512×341，存 PNG；未裁剪或调整对比度 |
| `brick_window_gray.png`（灰度） | [Brick wall and window.jpg](https://commons.wikimedia.org/wiki/File:Brick_wall_and_window.jpg)，Tarasna0922 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)；本组灰度转换、缩放和平滑为改作，保留相同许可与署名 | 3225×2200 RGB，EXIF 方向处理后转 8 位 L，LANCZOS 等比例缩至 512×349，存 PNG；未裁剪或调整对比度 |
| `sunflower.png`（RGB） | [Sunflower in a field.jpg](https://commons.wikimedia.org/wiki/File:Sunflower_in_a_field.jpg)，Timovn | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；在此注明本组缩放和平滑改动 | 4608×3456 RGB，EXIF 方向处理后转 8 位 RGB，LANCZOS 等比例缩至 512×384，存 PNG；未裁剪或调整对比度 |

文件页许可与作者信息于 2026-11-17 核对。输入分别呈现沙地纹理与木头／岩石边界、砖面纹理与窗框、花盘／草地纹理与花瓣轮廓。程序从这些预处理输入重新运行，不依赖网络。命令和结果见 [实验记录](../../results/structure_smoothing/README.md)。
