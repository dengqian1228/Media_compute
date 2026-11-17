# 多图像结构平滑与参数对照

本轮实际运行目录为 [`experiment-20261117T102719Z-1b827758b270`](experiment-20261117T102719Z-1b827758b270)。三幅输入各运行 λ∈{0.005, 0.02, 0.08}、κ∈{1.5, 2}，固定 βmax=100000，共 18 组。每组复用 `run_and_save`，保留输入副本、`output.npy` 原始 float64、`output.png` 8 位显示图和 `run.json`。全部参数、迭代次数、耗时、平均绝对变化量及结果路径在 [runs.csv](experiment-20261117T102719Z-1b827758b270/runs.csv)；每个 `run.json` 还记录环境版本。

## 从已归档原图重复运行

在项目根目录执行：

```powershell
python -m scripts.structure_smoothing_experiment prepare
python -m scripts.structure_smoothing_experiment run
```

`prepare` 校验下载原图的 SHA-256；若现有预处理输入或清单内容不同，会报错而不覆盖。`run` 校验输入清单，按同一网格新建独立实验目录；运行耗时和目录名使用实际值，每次可不同。使用本轮目录抽查：

```powershell
python -m scripts.structure_smoothing_experiment check 'results/structure_smoothing/experiment-20261117T102719Z-1b827758b270'
```

`check` 核对 18 条 CSV／JSON 参数与文件，并从每幅图抽取一组重跑，另建 `checks-...` 目录保存复现输出和 `checks.json`；不覆盖既有运行。也可对某个 `runs.csv` 中的 `record` 路径使用 `python -m l0_smoothing replay <run.json路径> --output-dir <新目录>`。

## 对照图和观察

每幅图的 `full_comparison.png` 包括输入及 6 组输出，行对应 κ、列对应 λ；输入上的红框标出局部区域。`same_region_zoom.png` 对同一像素区域进行最近邻放大，区域坐标保存在各图的 `roi.json`。全图和放大图使用 `output.png` 显示副本；定量重算应使用未裁剪的 `output.npy`。

| 图像 | 全图 | 同区域放大 |
| --- | --- | --- |
| 沙滩 | [全图](experiment-20261117T102719Z-1b827758b270/beach/full_comparison.png) | [局部](experiment-20261117T102719Z-1b827758b270/beach/same_region_zoom.png) |
| 灰度砖墙窗户 | [全图](experiment-20261117T102719Z-1b827758b270/brick_window_gray/full_comparison.png) | [局部](experiment-20261117T102719Z-1b827758b270/brick_window_gray/same_region_zoom.png) |
| 向日葵 | [全图](experiment-20261117T102719Z-1b827758b270/sunflower/full_comparison.png) | [局部](experiment-20261117T102719Z-1b827758b270/sunflower/same_region_zoom.png) |

- **沙滩**：λ=0.005 已明显压低沙纹，木头与远处岩石的主轮廓尚在；λ=0.02 又削弱木头的沟纹和沙丘暗线；λ=0.08 使木头局部形状和沙丘细分界消失，属于本组参数中的过度平滑案例。两种 κ 下这一趋势一致。
- **灰度砖墙与窗户**：λ=0.005 清除砖面颗粒，同时保留多数砖缝和窗框；λ=0.02 进一步减少砖面灰度变化，窗框主体仍可辨；λ=0.08 把大量砖缝合并成大片灰区，窗框周围的小结构也丢失。该较差结果完整保留于网格中。
- **向日葵**：λ=0.005 抑制草地和花盘的细碎变化，花瓣外轮廓仍清楚；λ=0.02 花盘纹理已明显减少；λ=0.08 花盘几乎成为单色块、远处小花和草地结构大量消失，虽然主体外形仍在，但细节损失严重。
- **参数作用**：同一 κ 下，λ 从 0.005 增至 0.08，三图对原图的平均绝对变化量均增大（见 CSV），与上述纹理抑制和细节丢失一致。κ 控制 β 的增长步幅；同一 λ 下，κ=1.5 运行 33–40 轮，κ=2 运行 20–24 轮，本次耗时也较低。κ 还改变最终像素，不能只视为速度开关：例如灰度砖墙在 λ=0.08 时，两种 κ 输出的全图平均绝对差为 0.04299（以 `[0,1]` float64、全像素平均计算），局部砖缝残留程度也不同。不同 λ 的影响在这组图上更显著，但不据此推断其他图像或参数范围。

平均绝对变化量定义为 `mean(abs(output.npy - 预处理输入/255))`，数值只量化改动幅度，不单独代表视觉质量。观察来自本轮保存的显示图及同区域放大图，**属于智能体执行分析，成员人工核验待完成**；未作边缘检测或课程验收结论。

## 实际检查

- `python -m unittest discover -s tests -v`：10 项通过。
- `python -m scripts.structure_smoothing_experiment prepare`：三份原图 SHA-256 匹配，预处理输入和清单一致。
- `python -m scripts.structure_smoothing_experiment check 'results/structure_smoothing/experiment-20261117T102719Z-1b827758b270'`：18 条参数网格及产物审计通过；[最新抽查记录](experiment-20261117T102719Z-1b827758b270/checks-20261117T103151Z-6c9b13781aa8/checks.json) 中三幅图的复现均 `passed=true`、最大浮点绝对误差 0、不同显示像素数 0。先前一次审计也保留于同实验目录的另一个 `checks-...` 目录。

以上均为智能体执行验证，未记录成员人工验收。边缘提取、界面和 JPEG 去伪影仍待后续阶段。
