# 图像来源与许可

本演示对归档输入进行了L0平滑、裁剪展示和边缘提取。

| 素材 | 原作者 | 来源与许可 |
| --- | --- | --- |
| beach | 未在官网页面注明 | [来源](https://jiaya.me/file/archive/projects/L0smoothing/ImageSmoothing.htm)；未在官网页面注明；公开再分发前须核实授权 |
| brick_window_gray | Tarasna0922 | [来源](https://commons.wikimedia.org/wiki/File:Brick_wall_and_window.jpg)；CC BY-SA 4.0; derived grayscale and smoothed images retain this license |
| sunflower | Timovn | [来源](https://commons.wikimedia.org/wiki/File:Sunflower_in_a_field.jpg)；CC BY 4.0; resize/smoothing changes are noted |

砖墙及其衍生结果保留 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)；向日葵按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 署名。照片使用A实验已归档的缩放/灰度输入，本演示未再次缩放计算输入。

西瓜与蜗牛：[Xu等2011论文官网Clip-art样例](https://jiaya.me/file/archive/projects/L0smoothing/ClipArt.htm)，成对使用JPEG输入及作者输出。官网未注明原图片作者或明确许可，不声称为本组原创或开放授权。作者结果不是干净真值。

小屋与灰度线图：本组 scripts/jpeg_artifacts.py 确定性绘图程序生成，使用干净图作参考。

原始输入在inputs/，显示结果在assets/，参数与来源摘要在manifest.json。完整复现脚本位于项目仓库。
