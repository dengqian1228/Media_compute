# JPEG 指标与代表结果独立核对

使用者：成员 B 蒋天乐（2023010721）。执行者：智能体。完成于 2026-11-17 23:53:07 +08:00；成员人工核验待完成。

被核对实验：`results/jpeg_artifacts/jpeg-20261117T155122Z-e37cd961efa5/`。没有修改该实验的文件。

实际命令（项目根目录）：

```bash
/tmp/media-compute-venv/bin/python results/member_b_verification/jpeg-independent-20261117T155211Z/verify_metrics.py
```

环境 Python 3.10.12、NumPy 2.2.4、Pillow 11.3.0。核对程序未导入项目指标实现，也未使用 OpenCV 滤波；根据记录的约定，用 NumPy 显式高斯权重和有效域可分离卷积重算真实全图及 ROI 的 PSNR/SSIM。SSIM 为 11×11、σ=1.5、总体矩、K1=0.01、K2=0.03；只取完整窗口中心，RGB 按通道平均；先裁 ROI 再去掉 ROI 内 5 像素边界。

30 行全部核对通过（6 行 JPEG 基线、24 行 L0），λ 网格、质量网格无缺项。PSNR 最大差值为 0 dB，SSIM 最大绝对差为 `2.0516921495072893e-13`；这属于两种计算顺序的浮点差异。每个 JPEG 和输出均与同幅干净 `clean.png` 比较，干净 PNG 的 SHA-256 与生成清单一致，ROI 与生成前清单一致。全部输出保留，24 组中有 8 组全图 PSNR 下降、5 组 SSIM 下降。

机器可读证据见 [metrics_audit.json](metrics_audit.json)，独立代码为 [verify_metrics.py](verify_metrics.py)。

智能体实际查看了 `house_rgb/q30/same_region_zoom.png` 和 `line_gray/q70/full_comparison.png`：

- house Q30 的 JPEG 图在屋顶边缘、窗框周围和蓝色平坦墙面出现条纹、振铃及分块变化；λ=0.008 后这些变化明显减弱，主要屋顶、窗框仍可辨。此组全图 PSNR 从 30.9931 到 31.9893 dB，SSIM 从 0.93177 到 0.96518。
- line Q70 原 JPEG 已较接近干净图；λ=0.03 消除了右侧低对比细线，粗圆框和矩形仍在，属于保轮廓但丢真实细节的负例。全图 PSNR 从 39.1555 降至 27.5480 dB，SSIM 从 0.98349 降至 0.94532。

局部对照图的标题数字沿用全图指标；ROI 数值应读取 `metrics.csv` 的 `roi_psnr_db` 和 `roi_ssim`，不能将局部图标题误读为局部指标。已向实验 Agent 提醒在实验 README 明确这一点。

结论限于两幅确定性几何合成 Clip-art 与这组参数，不能据此声称所有 JPEG 输入都会改善；没有独立测试集，按本组真值择优只是实验描述。以上观察均为智能体检查，不代表两位成员已经手动核验。
