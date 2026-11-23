# L0结构平滑：双人9分钟展示材料

状态：待成员核对和排练；这是准备稿，不是课堂展示记录。B：蒋天乐（2023010721）；A：章小龙（2023010725）。

离线版：[presentation.html](presentation.html)。HTML由 `python -m scripts.generate_presentation` 生成，图片嵌入文件，可左右键翻页、F全屏或打印。可编辑源为生成脚本；讲解及备用路径见 [presentation_notes.md](presentation_notes.md)。

## 01 把细纹理压下去，把主要轮廓留下来

成员A｜00:00–00:35｜35秒

第4题：L0 梯度最小化结构平滑、固定参数边缘对照与 Clip-art JPEG 去伪影。成员 A：章小龙 2023010725；成员 B：蒋天乐 2023010721。当前为待排练稿，现场展示由两位成员本人完成。

## 02 用非零梯度的“位置数”控制结构

成员A｜00:35–01:25｜50秒

目标 min_S ||S-I||² + λ C(S)，C(S)=#{p:Σc[(DxS)²+(DyS)²]>0}。保真项限制偏离输入，L0项惩罚存在梯度的位置数。RGB按像素联合统计方向和通道；λ越大惩罚越强，但真正细结构也可能消失。

## 03 交替更新：阈值辅助梯度，再用 FFT 求图像

成员A｜01:25–02:25｜60秒

初始化S=I、β=2λ；周期前向差分；q=Σc(gx²+gy²)，q≤λ/β时两个方向全部通道同时置零；FFT解固定h,v二次问题；β←κβ，直到β≥10^5。核心保存float64且不裁剪，显示PNG才裁剪量化。核心自写，NumPy FFT为基础库，不使用完整L0接口。

## 04 三幅图、18组参数：适中与过度平滑

成员A｜02:25–03:35｜70秒

每图λ={.005,.02,.08}，κ={1.5,2}，βmax=10^5。图示κ=2，分别为原图/.005/.08的同ROI。适中λ压低沙纹、砖面、草地纹理；.08丢失木头细轮廓、砖缝和花盘细节。κ=1.5为33–40轮，κ=2为20–24轮；不是同样输出的加速开关。

## 05 Canny 必须固定设置，少线并不自动更好

成员A｜03:35–04:30｜55秒

全部21张边缘图使用Canny60/120、孔径3、L2，无额外模糊，RGB统一转灰。图示砖墙全图。λ=.02窗框主体可辨，.08时大量砖缝损失。三图白边像素统计不能单独作为质量评价。A部分结束，转交B。

## 06 JPEG 实验：先有干净真值，再制造压缩

成员B｜04:30–05:20｜50秒

两幅256×256确定性程序合成Clip-art，RGB与L，无外部素材。JPEG Q={10,30,70}；RGB4:4:4，关闭progressive和optimize；24次L0。JPEG与输出PNG始终比较同一干净图。PSNR全通道MSE；SSIM11×11高斯sigma1.5、valid、总体矩、RGB通道平均，data_range255。局部另算。

## 07 正例：窗框附近的条纹减轻

成员B｜05:20–06:15｜55秒

小屋Q30，λ=.008、κ=2、βmax1e5。全图PSNR30.9931→31.9893dB，SSIM.931767→.965178；局部PSNR28.6654→30.1149、SSIM.896815→.962119。主轮廓保留，条纹减轻，仍未回到真值。图片第一行全图，第二行同ROI。

## 08 失败例：轻度压缩，强平滑反而损失细线

成员B｜06:15–07:10｜55秒

灰度Q70，λ=.03、κ=2、βmax1e5。PSNR39.1555→27.5480dB，SSIM.983487→.945320；同ROI细横线和竖线消失。24组中8组PSNR下降、5组SSIM下降。不能把更干净的平面直接当更好；局部、全图和指标一起判断。

## 09 现场 Demo：执行本组算法，再打开结果页

成员B｜07:10–08:25｜75秒

项目根目录运行 python -m scripts.demo --mode all --output-dir results/demo/classroom；打开命令打印的新index.html；展示平滑/同参Canny/JPEG/局部/指标。本轮all实测2.221秒，不保证换机耗时。备用打开已归档all页，负例打开已归档line_gray Q70 λ.03页；明确告知使用归档。

## 10 交付依据、工作分工与实际限制

成员B｜08:25–09:00｜35秒

A范围：L0核心、读写复现、三图参数与Canny基础；B蒋天乐2023010721：JPEG/指标/Demo/报告展示整合。AI实际生成代码、运行检查与整理材料；双方理解、人工核验、排练与现场展示由成员完成，目前待完成。限制：合成Clip-art规模小，参数未独立验证，周期边界/显示裁剪影响，未宣称通用最优；无课程评分已通过声明。

## 引用与证据

- [L0论文及项目官网](https://jiaya.me/file/archive/projects/L0smoothing/ImageSmoothing.htm)
- [SSIM原作者页面](https://www.cns.nyu.edu/~lcv/ssim/)
- [输入来源与许可](../data/structure_smoothing/README.md)、[Clip-art输入](../data/jpeg_artifacts/README.md)
- [结构平滑记录](../results/structure_smoothing/README.md)、[Canny记录](../results/edge_comparison/README.md)、[JPEG记录](../results/jpeg_artifacts/README.md)
- 逐张嵌图来源与裁剪坐标：[presentation_assets.json](presentation_assets.json)。所有裁剪仅用于展示，不重新计算或伪造实验结果。
