# 原图与 L0 平滑图的 Canny 边缘对照

本轮结果位于 [`edges-20261117T105442Z-a63edf132bc2`](edges-20261117T105442Z-a63edf132bc2)。输入是上一轮三幅预处理原图及 18 组**已保存**的 `output.png`；本轮没有重跑平滑。三幅图各有 1 张原图边缘图和 6 张平滑边缘图，全部索引、输入路径、SHA-256、转换后灰度实际最小／最大值、参数、边缘像素数和输出路径见 [edges.csv](edges-20261117T105442Z-a63edf132bc2/edges.csv)。环境版本和统一检测设置见 [edge_experiment.json](edges-20261117T105442Z-a63edf132bc2/edge_experiment.json)。

原图作者、来源链接、许可及预处理见 [输入来源记录](../../data/structure_smoothing/README.md)；官网 beach 原图的许可仍未在官网页面注明。

## 检测约定

- 使用 Pillow 将原图和保存的平滑显示 PNG 解码为 8 位 `L` 或 `RGB`，不做额外模糊、对比度拉伸或每组自动调参。RGB 统一使用 `cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)`；原有 `L` 灰度像素原样传入。OpenCV 的 RGB 转灰度权重为约 `0.299 R + 0.587 G + 0.114 B`，8 位转换的具体舍入由当前 OpenCV 实现决定。[OpenCV RGB 转灰度公式](https://docs.opencv.org/5.0/main_modules/gapi_colorconvert.html)
- Canny 输入为 `uint8` 单通道、数值范围 `0..255`。所有三幅原图及其全部平滑结果统一使用低阈值 `60`、高阈值 `120`、Sobel 孔径 `3`、`L2gradient=True`；阈值作用于 Canny 的梯度与滞后连接，不是把灰度像素直接二值化。[OpenCV Canny 接口说明](https://docs.opencv.org/5.0/main_modules/imgproc_feature.html)
- 检测使用 `output.png`，该文件已在上轮保存时由 float64 结果**仅为显示**裁剪到 `[0,1]` 并量化成 8 位；原始 `output.npy` 保留不变。执行脚本先核对 `output.png` 与该量化规则、上轮 `run.json` 参数及输入 SHA-256 一致。
- 本轮环境：Python 3.13.14、NumPy 2.5.4、Pillow 13.0.0、`opencv-python-headless` 5.0.0.93（`cv2.__version__` 为 5.0.0）。这些是实际运行版本，未验证其他环境。

## 对照图

每图 2 行对应 κ=1.5、2；每行由左至右为原图、λ=0.005、0.02、0.08。原图边缘图在两行重复，红框是局部区域；局部图对相同源像素区域做最近邻放大，使用上轮相同 ROI 坐标。边缘图为黑底白边，图版上的标签和红框只用于展示，独立边缘 PNG 不含标注。

| 输入 | 全图边缘对照 | 同区域局部边缘对照 |
| --- | --- | --- |
| 沙滩 RGB | [全图](edges-20261117T105442Z-a63edf132bc2/beach/full_edge_comparison.png) | [局部](edges-20261117T105442Z-a63edf132bc2/beach/same_region_edge_zoom.png) |
| 砖墙窗户灰度 | [全图](edges-20261117T105442Z-a63edf132bc2/brick_window_gray/full_edge_comparison.png) | [局部](edges-20261117T105442Z-a63edf132bc2/brick_window_gray/same_region_edge_zoom.png) |
| 向日葵 RGB | [全图](edges-20261117T105442Z-a63edf132bc2/sunflower/full_edge_comparison.png) | [局部](edges-20261117T105442Z-a63edf132bc2/sunflower/same_region_edge_zoom.png) |

## 实际观察与限制

- **沙滩**：原图有密集的沙纹、木头表面和海岸细线。λ=0.005／0.02 时沙纹与木头内部杂线减少，远处岩石外轮廓、部分木头边缘和长阴影仍可辨；λ=0.08 时近景木头的内部轮廓和部分沙丘线也消失，边缘图更稀疏却损失了可辨结构。
- **灰度砖墙窗户**：λ=0.005／0.02 减少砖面内部颗粒和重复细线，窗框主轮廓继续存在；λ=0.08 时大量砖缝和窗框附近的小分界中断或消失。该图的砖缝有些本身就是有意义的结构，因此“少线”不能自动解释为更好。
- **向日葵**：λ=0.005／0.02 减少草地及花盘的细碎边缘，前景花瓣外轮廓仍明显；λ=0.08 时花盘纹理、部分花瓣分隔及背景小花轮廓大量消失，主花外形虽在，但结构信息损失严重。

作为复核索引，三幅原图的白色边缘像素数分别为沙滩 `14968`、砖墙 `43495`、向日葵 `41729`；在 λ=0.02、κ=2 下分别为 `8380`、`27792`、`26268`，在 λ=0.08、κ=2 下为 `4439`、`10604`、`7294`。这些数字只是固定检测设置下的数量统计，不能区分杂乱细节与有用轮廓，也**不能单独证明视觉效果改善**。上述图像观察由智能体执行，成员人工核验待完成。

## 重复运行和检查

在项目根目录、具备 `requirements.txt` 所列依赖的环境中执行；每次 `run` 新建目录，不覆盖本轮结果：

```powershell
python -m scripts.edge_comparison run --source-experiment 'results/structure_smoothing/experiment-20261117T102719Z-1b827758b270' --low 60 --high 120 --aperture 3 --l2
python -m scripts.edge_comparison check 'results/edge_comparison/edges-20261117T105442Z-a63edf132bc2'
python -m unittest discover -s tests -v
```

本轮 `check` 的[最新实际记录](edges-20261117T105442Z-a63edf132bc2/checks-20261117T105846Z-26a6d96aa39e/checks.json)显示：每幅原图与其六组结果参数一致，21 张边缘图重新计算后与所存 PNG 的解码像素完全相同，灰度实际最小／最大值也与 CSV 一致。早先一次成功检查保留于同一目录的另一个 `checks-...` 文件夹。该结论为**智能体执行验证**，不是成员人工验收。
