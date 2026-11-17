# 小规模流程验证

本目录保存对 `data/验证样例/` 两幅合成图的单次运行与复现记录。每个 `run-*` 或 `replay-*` 子目录各包含原输入文件副本、显示用 `output.png`、未裁剪的 float64 `output.npy` 和 `run.json`。这些文件只证明本轮命令行读写与复现流程的实际执行，不是课程应用实验或报告效果结论。

目录名含 UTC 创建时间和随机标识，以免覆盖旧结果。本轮实际记录如下；耗时来自各自 `run.json`，只代表此处的小样例验证。

| 输入 | 原运行记录目录 | 参数 `λ, κ, βmax` | 迭代次数 | 原运行耗时 | 复现记录目录 | 最大浮点误差 | 不同显示像素 |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: |
| `灰度样例.png` | `run-20261117T095048Z-c87c687d3f77` | `0.02, 2, 100000` | 22 | 0.003508599998895079 秒 | `replay-20261117T095059Z-57a61c3314f9` | 0 | 0 |
| `彩色样例.png` | `run-20261117T095053Z-9aae526321fe` | `0.03, 2, 100000` | 21 | 0.0038212999934330583 秒 | `replay-20261117T095104Z-f0fac1ded2f1` | 0 | 0 |

实际命令从项目根目录执行：

```powershell
python -m l0_smoothing run 'data/验证样例/灰度样例.png' --output-dir 'results/验证运行' --lambda 0.02 --kappa 2 --beta-max 100000
python -m l0_smoothing run 'data/验证样例/彩色样例.png' --output-dir 'results/验证运行' --lambda 0.03 --kappa 2 --beta-max 100000
python -m l0_smoothing replay 'results/验证运行/run-20261117T095048Z-c87c687d3f77/run.json' --output-dir 'results/验证运行'
python -m l0_smoothing replay 'results/验证运行/run-20261117T095053Z-9aae526321fe/run.json' --output-dir 'results/验证运行'
```

两次复现 `passed=true`，输入解码像素一致，显示像素无差异，最大浮点绝对误差为 0。工具、版本和检查过程另见项目根目录 `AI_LOG.md`。

保存输入副本的一致性检查加入后，使用同样的两条 `replay` 命令再次复现，分别生成 `replay-20261117T095608Z-74b373abb8f0` 与 `replay-20261117T095613Z-1d367ef11d6e`；两条新记录也均为 `passed=true`、最大浮点绝对误差 0、不同显示像素数 0。此前的运行和复现目录均予保留，因此本目录共有 6 份 `run.json`。对 6 份记录核查：输入副本的解码像素摘要、float64 输出形状、显示 PNG 像素摘要均与各自 JSON 一致。
