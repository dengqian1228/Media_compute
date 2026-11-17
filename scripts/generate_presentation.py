"""Build editable, offline presentation slides from actual archived experiments.

Run at project root: python -m scripts.generate_presentation
The source is this file. Crops use archived ROI coordinates; source hashes and
crop coordinates are exported to docs/presentation_assets.json for inspection.
"""
import base64
import csv
import hashlib
import html
import io
import json
from pathlib import Path
from html.parser import HTMLParser

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT/'docs'
SMOOTH = ROOT/'results/structure_smoothing/experiment-20261117T102719Z-1b827758b270'
EDGES = ROOT/'results/edge_comparison/edges-20261117T105442Z-a63edf132bc2'
JPEG = ROOT/'results/jpeg_artifacts/jpeg-20261117T155122Z-e37cd961efa5'
DEMO = ROOT/'results/demo/中文验证/demo-20261117T155441Z-d0d62b1d3d75'
NEGATIVE = ROOT/'results/demo/中文验证/demo-20261117T155455Z-928d25ba4500'
ASSETS = []


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def csvrows(path):
    return list(csv.DictReader(path.open(encoding='utf-8-sig')))


def figure(path, label, roi=None):
    path = Path(path)
    with Image.open(path) as original:
        image = original.copy()
    if roi:
        image = image.crop(roi)
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    uri = 'data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode('ascii')
    ASSETS.append({'source': path.relative_to(ROOT).as_posix(), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'roi_xyxy': roi, 'display': label, 'embedded_size': list(image.size)})
    return f'<figure><figcaption>{html.escape(label)}</figcaption><img src="{uri}" alt="{html.escape(label, quote=True)}"></figure>'


def group(figures, cls=''):
    return '<div class="figures '+cls+'">'+''.join(figures)+'</div>'


def main():
    smooth_rows = csvrows(SMOOTH/'runs.csv')
    jpeg_rows = csvrows(JPEG/'metrics.csv')
    demo = load(DEMO/'demo.json')
    def smoothed(name, lam):
        return SMOOTH/next(r['display_result'] for r in smooth_rows if r['image']==name and float(r['lambda'])==lam and float(r['kappa'])==2)
    def jpeg(name, quality, lam=None):
        return next(r for r in jpeg_rows if r['image']==name and int(r['jpeg_quality'])==quality and (r['stage']=='jpeg' if lam is None else r['lambda'] and float(r['lambda'])==lam))
    def compare_jpeg(name, quality, lam):
        baseline, restored = jpeg(name, quality), jpeg(name, quality, lam)
        roi = load(JPEG/name/'roi.json')['xyxy']
        paths = [JPEG/name/'clean.png', JPEG/baseline['display_result'], JPEG/restored['display_result']]
        labels = ['干净参考', f'JPEG Q={quality}', f'本组 L0，λ={lam:g}']
        figures = group([figure(p, l+' · 全图') for p,l in zip(paths,labels)], 'full-small')
        figures += group([figure(p, l+' · 同一局部', roi) for p,l in zip(paths,labels)], 'zoom')
        table = '<table><tr><th>全图指标</th><th>JPEG</th><th>L0</th></tr>'
        table += f'<tr><td>PSNR / SSIM</td><td>{float(baseline["psnr_db"]):.4f} dB / {float(baseline["ssim"]):.6f}</td><td>{float(restored["psnr_db"]):.4f} dB / {float(restored["ssim"]):.6f}</td></tr></table>'
        return figures+table
    basic = ''
    for name,label in [('beach','沙滩'),('brick_window_gray','灰度砖墙'),('sunflower','向日葵')]:
        roi=load(SMOOTH/name/'roi.json')['xyxy']
        basic += group([figure(ROOT/f'data/structure_smoothing/inputs/{name}.png',f'{label} · 原图局部',roi),
                        figure(smoothed(name,.005),'λ=.005，同一局部',roi),
                        figure(smoothed(name,.08),'λ=.08，同一局部',roi)],'mini')
    canny = group([figure(EDGES/'brick_window_gray/input_edges.png','原图 Canny'),
                   figure(EDGES/'brick_window_gray/lambda-0.02_kappa-2_edges.png','λ=.02，κ=2 后 Canny'),
                   figure(EDGES/'brick_window_gray/lambda-0.08_kappa-2_edges.png','λ=.08，κ=2 后 Canny')],'canny')
    slides = [
        {'title':'把细纹理压下去，把主要轮廓留下来','speaker':'A','seconds':35,'clock':'00:00–00:35',
         'md':'第4题：L0 梯度最小化结构平滑、固定参数边缘对照与 Clip-art JPEG 去伪影。成员 A：姓名、学号待填写；成员 B：蒋天乐 2023010721。当前为待排练稿，现场展示由两位成员本人完成。',
         'body':'<div class="hero"><p class="eyebrow">媒体计算课程 · 第4题</p><h1>L0 梯度最小化<br>图像结构平滑</h1><p class="large">参数影响 → 边缘对照 → JPEG 去伪影</p><p>成员 A：姓名／学号待填写<br>成员 B：蒋天乐 · 2023010721</p><p class="muted">准备材料与智能体运行结果；人工核验及课堂展示待成员完成。</p></div>'},
        {'title':'用非零梯度的“位置数”控制结构','speaker':'A','seconds':50,'clock':'00:35–01:25',
         'md':'目标 min_S ||S-I||² + λ C(S)，C(S)=#{p:Σc[(DxS)²+(DyS)²]>0}。保真项限制偏离输入，L0项惩罚存在梯度的位置数。RGB按像素联合统计方向和通道；λ越大惩罚越强，但真正细结构也可能消失。',
         'body':'<div class="formula">min<sub>S</sub> ‖S − I‖² + λ C(S)</div><div class="formula small-formula">C(S) = #{p : Σ<sub>c</sub> [(D<sub>x</sub>S)² + (D<sub>y</sub>S)²] &gt; 0}</div><div class="columns"><div class="card"><h3>保真项</h3><p>让结果接近输入，限制任意改变颜色与结构。</p></div><div class="card"><h3>稀疏梯度</h3><p>统计梯度存在的位置，抑制低幅度纹理；RGB按像素联合判断。</p></div></div><p class="callout">λ 增大：细节更少；也可能把有用的细线、砖缝一起抹去。</p><p class="source">依据 Xu 等，Image Smoothing via L0 Gradient Minimization，2011；本组核心由数组运算实现。</p>'},
        {'title':'交替更新：阈值辅助梯度，再用 FFT 求图像','speaker':'A','seconds':60,'clock':'01:25–02:25',
         'md':'初始化S=I、β=2λ；周期前向差分；q=Σc(gx²+gy²)，q≤λ/β时两个方向全部通道同时置零；FFT解固定h,v二次问题；β←κβ，直到β≥10^5。核心保存float64且不裁剪，显示PNG才裁剪量化。核心自写，NumPy FFT为基础库，不使用完整L0接口。',
         'body':'<div class="flow"><span>S=I<br>β=2λ</span><b>→</b><span>周期差分<br>联合阈值</span><b>→</b><span>FFT更新 S</span><b>→</b><span>β←κβ<br>β&lt;10⁵则循环</span></div><div class="formula small-formula">q = Σ<sub>c</sub>(g<sub>x</sub>²+g<sub>y</sub>²) ≤ λ/β ⇒ h=v=0</div><div class="formula small-formula">Ŝ = [Î + β(D̄<sub>x</sub>ĥ + D̄<sub>y</sub>v̂)] / [1 + β(|D<sub>x</sub>|²+|D<sub>y</sub>|²)]</div><p>周期边界使差分算子可在频域求解；最后一行／列连接第一行／列。</p><p>κ 控制 β 的增长步幅，会影响轮数与输出；不会只改变速度。</p><p class="source">代码：core.py；验证：周期边界、阈值等号、独立小矩阵求解。float64 原结果保留，显示PNG才裁剪量化。</p>'},
        {'title':'三幅图、18组参数：适中与过度平滑','speaker':'A','seconds':70,'clock':'02:25–03:35',
         'md':'每图λ={.005,.02,.08}，κ={1.5,2}，βmax=10^5。图示κ=2，分别为原图/.005/.08的同ROI。适中λ压低沙纹、砖面、草地纹理；.08丢失木头细轮廓、砖缝和花盘细节。κ=1.5为33–40轮，κ=2为20–24轮；不是同样输出的加速开关。',
         'body':basic+'<p>图示固定 κ=2；所有局部均从已归档同一 ROI 裁出。λ=.08 的结构损失完整保留。</p><p class="source">18组网格：λ={.005,.02,.08} × κ={1.5,2} × 3图，βmax=10⁵。κ=1.5：33–40轮；κ=2：20–24轮。来源：论文官网沙滩；Commons砖墙、向日葵；许可见数据清单。</p>'},
        {'title':'Canny 必须固定设置，少线并不自动更好','speaker':'A','seconds':55,'clock':'03:35–04:30',
         'md':'全部21张边缘图使用Canny60/120、孔径3、L2，无额外模糊，RGB统一转灰。图示砖墙全图。λ=.02窗框主体可辨，.08时大量砖缝损失。三图白边像素统计不能单独作为质量评价。A部分结束，转交B。',
         'body':canny+'<p class="callout">统一 Canny：60 / 120，孔径3，L2；RGB统一转灰，无额外模糊。</p><table><tr><th>白色边缘像素</th><th>原图</th><th>λ=.02</th><th>λ=.08</th></tr><tr><td>沙滩</td><td>14968</td><td>8380</td><td>4439</td></tr><tr><td>砖墙</td><td>43495</td><td>27792</td><td>10604</td></tr><tr><td>向日葵</td><td>41729</td><td>26268</td><td>7294</td></tr></table><p class="source">固定κ=2；统计只描述线条数量。21张边缘图已有重算检查，成员人工核验待完成。</p>'},
        {'title':'JPEG 实验：先有干净真值，再制造压缩','speaker':'B','seconds':50,'clock':'04:30–05:20',
         'md':'两幅256×256确定性程序合成Clip-art，RGB与L，无外部素材。JPEG Q={10,30,70}；RGB4:4:4，关闭progressive和optimize；24次L0。JPEG与输出PNG始终比较同一干净图。PSNR全通道MSE；SSIM11×11高斯sigma1.5、valid、总体矩、RGB通道平均，data_range255。局部另算。',
         'body':'<div class="flow"><span>干净 PNG<br>程序合成</span><b>→</b><span>真实 JPEG<br>Q=10 / 30 / 70</span><b>→</b><span>本组 L0<br>四个 λ</span><b>→</b><span>全图 + 同ROI<br>PSNR / SSIM</span></div><div class="columns"><div class="card"><h3>可追溯输入</h3><p>小屋 RGB、灰度线图，各256×256；无随机数。RGB设4:4:4，主要观察量化误差。</p><p>2图 × 3质量 × 4λ = 24组，全部保存。</p></div><div class="card"><h3>一致的比较口径</h3><p>同一干净参考，对解码JPEG和8位输出PNG计算；原始float64仍保留。</p><p>全图与局部独立计算，不能混用。</p></div></div><p class="source">SSIM：11×11高斯σ=1.5，K1=.01/K2=.03，data_range255，总体矩，valid内域；RGB逐通道均值。本组口径区别于作者RGB转灰默认。</p>'},
        {'title':'正例：窗框附近的条纹减轻','speaker':'B','seconds':55,'clock':'05:20–06:15',
         'md':'小屋Q30，λ=.008、κ=2、βmax1e5。全图PSNR30.9931→31.9893dB，SSIM.931767→.965178；局部PSNR28.6654→30.1149、SSIM.896815→.962119。主轮廓保留，条纹减轻，仍未回到真值。图片第一行全图，第二行同ROI。',
         'body':compare_jpeg('house_rgb',30,.008)+'<p class="source">Q30、κ=2、βmax=10⁵；上行为全图，下行为同ROI。局部 PSNR 28.6654→30.1149dB，SSIM .896815→.962119。条纹减轻，仍存在边界误差。</p>'},
        {'title':'失败例：轻度压缩，强平滑反而损失细线','speaker':'B','seconds':55,'clock':'06:15–07:10',
         'md':'灰度Q70，λ=.03、κ=2、βmax1e5。PSNR39.1555→27.5480dB，SSIM.983487→.945320；同ROI细横线和竖线消失。24组中8组PSNR下降、5组SSIM下降。不能把更干净的平面直接当更好；局部、全图和指标一起判断。',
         'body':compare_jpeg('line_gray',70,.03)+'<p class="source">上行为全图，下行为同ROI；低对比横线与竖线消失。24组中8组PSNR下降、5组SSIM下降；没有剔除失败结果。</p>'},
        {'title':'现场 Demo：执行本组算法，再打开结果页','speaker':'B','seconds':75,'clock':'07:10–08:25',
         'md':f'项目根目录运行 python -m scripts.demo --mode all --output-dir results/demo/classroom；打开命令打印的新index.html；展示平滑/同参Canny/JPEG/局部/指标。本轮all实测{demo["total_elapsed_seconds"]:.3f}秒，不保证换机耗时。备用打开已归档all页，负例打开已归档line_gray Q70 λ.03页；明确告知使用归档。',
         'body':f'<pre>python -m scripts.demo --mode all \\\n  --output-dir results/demo/classroom</pre><ol><li>终端输出一个新的 <code>index.html</code> 路径。</li><li>在浏览器打开：平滑 → 相同Canny → JPEG全图／局部与指标。</li><li>展示新目录内的 <code>demo.json</code> 和 <code>run.json</code>，核对参数。</li></ol><div class="columns"><div class="card"><h3>可运行事实</h3><p>本轮 all 实测 {demo["total_elapsed_seconds"]:.3f} 秒；包含运行与制页，属于本机单次观测。</p><p>网页负责查看，修改参数需重新执行命令。</p></div><div class="card"><h3>现场备用</h3><p>计算异常：打开已归档 all 结果页，并说明切换为归档。</p><p>失败案例：直接打开灰度 Q70、λ=.03 归档页，无需网络。</p></div></div><p class="source">启动及备用路径见 docs/presentation_notes.md；课前须在展示机安装依赖、运行并核对。</p>'},
        {'title':'交付依据、工作分工与实际限制','speaker':'B','seconds':35,'clock':'08:25–09:00',
         'md':'A范围：L0核心、读写复现、三图参数与Canny基础；B蒋天乐2023010721：JPEG/指标/Demo/报告展示整合。AI实际生成代码、运行检查与整理材料；双方理解、人工核验、排练与现场展示由成员完成，目前待完成。限制：合成Clip-art规模小，参数未独立验证，周期边界/显示裁剪影响，未宣称通用最优；无课程评分已通过声明。',
         'body':'<div class="columns"><div class="card"><h3>分工</h3><p>A：核心、读写与复现、三图参数、固定Canny。</p><p>B：蒋天乐 2023010721<br>JPEG／指标、Demo、报告与展示材料整合。</p></div><div class="card"><h3>结论有边界</h3><p>适中参数能减轻伪影；强平滑也会删掉细结构。</p><p>合成样本仅2幅，未验证通用最优参数。周期边界和显示裁剪可能影响结果。</p></div></div><p>AI实际辅助生成代码、执行实验与自动检查、整理材料；成员理解、人工核验、排练与现场展示仍须本人完成。</p><p class="source">参考：Xu等2011 L0论文；Wang等2004 SSIM；NumPy/Pillow/OpenCV官方文档。图片：官网沙滩（许可未注明）、Tarasna0922砖墙CC BY-SA4.0、Timovn向日葵CC BY4.0；JPEG图为程序合成。完整来源见报告与数据清单。</p>'},
    ]
    assert len(slides)==10 and sum(s['seconds'] for s in slides)==540
    assert sum(s['seconds'] for s in slides if s['speaker']=='A')==270
    assert sum(s['seconds'] for s in slides if s['speaker']=='B')==270
    css = '''
*{box-sizing:border-box}body{margin:0;background:#101f2b;color:#182a37;font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif}button{font:inherit;cursor:pointer;border:1px solid #638296;border-radius:8px;background:#203747;color:#fff;padding:6px 13px}.toolbar{display:flex;gap:12px;align-items:center;justify-content:center;color:#d1dfe5;height:48px;font-size:14px}.slide{display:none;position:relative;flex-direction:column;background:#f7faf9;width:min(100vw,calc((100vh - 48px)*16/9),1440px);aspect-ratio:16/9;margin:auto;padding:28px 42px 40px;overflow:auto;font-size:clamp(14px,1.45vw,21px)}.slide.active{display:flex}h1{font-size:clamp(32px,4.2vw,62px);line-height:1.15;margin:14px 0 24px;letter-spacing:1px}h2{font-size:clamp(22px,2.5vw,36px);margin:0 0 18px;color:#124c56}h3{font-size:1.12em;margin:0 0 10px}p{line-height:1.5;margin:10px 0}.hero{padding:26px 30px}.eyebrow{color:#2c7880;font-weight:bold;letter-spacing:4px}.large{font-size:1.4em}.muted,.source{color:#4c626d}.source{font-size:.7em;line-height:1.45;margin-top:9px}.columns{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:20px 0}.card{padding:20px;border:1px solid #c8ddde;border-radius:12px;background:#fff}.callout{border-left:5px solid #c56d36;background:#fff3e9;padding:12px 16px}.formula{font:1.85em Georgia,serif;text-align:center;padding:16px 10px;color:#174e58}.small-formula{font-size:1.35em}.flow{display:flex;gap:12px;align-items:center;justify-content:center;margin:22px 0}.flow span{padding:16px;border:1px solid #98c0c3;background:#edf6f4;border-radius:10px;min-width:140px;text-align:center}.figures{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.figures figure{margin:0;text-align:center;min-width:0}.figures figcaption{font-size:.72em;padding:5px;color:#3d5964}.figures img{display:block;max-width:100%;height:230px;object-fit:contain;margin:auto;image-rendering:auto;background:white}.mini{margin-bottom:7px}.mini img{height:clamp(72px,14vh,110px);image-rendering:pixelated}.full-small img{height:clamp(80px,14vh,120px)}.zoom img{height:clamp(115px,22vh,180px);image-rendering:pixelated}.zoom{margin-top:8px}.canny img{height:clamp(150px,30vh,245px)}table{border-collapse:collapse;width:100%;font-size:.78em;margin-top:14px}th,td{border-bottom:1px solid #c7d6dc;padding:7px 10px;text-align:left}th{background:#e2eeed}pre{padding:20px;background:#102b38;color:#e5f3f2;border-radius:9px;font:1.05em monospace;white-space:pre-wrap}code{font-size:.88em}ol{line-height:1.8}.page{margin-top:auto;padding-top:10px;display:flex;justify-content:space-between;color:#4f6973;font-size:.63em}a{color:#256976}body:fullscreen .toolbar{height:42px}body:fullscreen .slide{width:100%;max-height:calc(100vh - 42px)}@media(max-width:850px){.slide{aspect-ratio:auto;min-height:calc(100vh - 48px);padding:20px}.flow{flex-wrap:wrap}.flow span{min-width:100px}.columns{gap:10px}.card{padding:12px}.figures{gap:7px}.mini img{height:90px}.full-small img{height:100px}.zoom img{height:140px}}@media print{@page{size:16in 9in;margin:0}body{background:#fff}.toolbar{display:none}.slide,.slide.active{display:flex!important;width:16in;height:9in;aspect-ratio:auto;padding:35px 50px 35px;overflow:hidden;margin:0;break-after:page;font-size:21px}h1{font-size:62px}h2{font-size:36px}.mini img{height:115px}.full-small img{height:135px}.zoom img{height:190px}.slide:last-child{break-after:auto}}
'''
    parts=['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>L0结构平滑 · 双人9分钟展示</title><style>'+css+'</style></head><body>',
           '<nav class="toolbar"><button id="prev">← 上页</button><span id="position">1 / 10</span><button id="next">下页 →</button><button id="fullscreen">全屏 F</button><button onclick="window.print()">打印 / PDF</button><span>← → / 空格翻页 · F全屏 · Home回首页</span></nav><main>']
    md=['# L0结构平滑：双人9分钟展示材料\n\n状态：待成员核对和排练；这是准备稿，不是课堂展示记录。B：蒋天乐（2023010721）；A课程姓名、学号待填写。\n\n离线版：[presentation.html](presentation.html)。HTML由 `python -m scripts.generate_presentation` 生成，图片嵌入文件，可左右键翻页、F全屏或打印。可编辑源为生成脚本；讲解及备用路径见 [presentation_notes.md](presentation_notes.md)。\n']
    for i,s in enumerate(slides,1):
        parts.append(f'<section class="slide{" active" if i==1 else ""}" data-seconds="{s["seconds"]}" aria-label="第{i}页"><h2>{i:02d} · {s["title"]}</h2>'+s['body']+f'<footer class="page"><span>成员{s["speaker"]} · 建议 {s["clock"]} · {s["seconds"]}秒</span><span>待排练稿 · 智能体执行结果 · {i}/10</span></footer></section>')
        md.append(f'\n## {i:02d} {s["title"]}\n\n成员{s["speaker"]}｜{s["clock"]}｜{s["seconds"]}秒\n\n{s["md"]}\n')
    parts.append('''</main><script>
const slides=Array.from(document.querySelectorAll('.slide'));let index=0;
function show(i){index=Math.max(0,Math.min(slides.length-1,i));slides.forEach((s,n)=>s.classList.toggle('active',n===index));document.getElementById('position').textContent=(index+1)+' / '+slides.length;slides[index].scrollTop=0;document.getElementById('prev').disabled=index===0;document.getElementById('next').disabled=index===slides.length-1;}
function fullscreen(){if(document.fullscreenElement){document.exitFullscreen();}else if(document.body.requestFullscreen){document.body.requestFullscreen().catch(()=>{});}}
document.getElementById('prev').onclick=()=>show(index-1);document.getElementById('next').onclick=()=>show(index+1);document.getElementById('fullscreen').onclick=fullscreen;
document.addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(index+1);}else if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(index-1);}else if(e.key==='Home'){show(0);}else if(e.key==='End'){show(slides.length-1);}else if(e.key.toLowerCase()==='f'){fullscreen();}});show(0);
</script></body></html>''')
    md.append('\n## 引用与证据\n\n- [L0论文及项目官网](https://jiaya.me/file/archive/projects/L0smoothing/ImageSmoothing.htm)\n- [SSIM原作者页面](https://www.cns.nyu.edu/~lcv/ssim/)\n- [输入来源与许可](../data/structure_smoothing/README.md)、[Clip-art输入](../data/jpeg_artifacts/README.md)\n- [结构平滑记录](../results/structure_smoothing/README.md)、[Canny记录](../results/edge_comparison/README.md)、[JPEG记录](../results/jpeg_artifacts/README.md)\n- 逐张嵌图来源与裁剪坐标：[presentation_assets.json](presentation_assets.json)。所有裁剪仅用于展示，不重新计算或伪造实验结果。\n')
    DOCS.mkdir(exist_ok=True)
    (DOCS/'presentation.html').write_text(''.join(parts),encoding='utf-8')
    (DOCS/'presentation.md').write_text(''.join(md),encoding='utf-8')
    (DOCS/'presentation_assets.json').write_text(json.dumps({'generator':'scripts/generate_presentation.py','slides':10,'total_seconds':540,'speaker_seconds':{'A':270,'B':270},'assets':ASSETS},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Structural validation only; this does not claim a browser/visual test.
    class Audit(HTMLParser):
        def __init__(self):
            super().__init__();self.images=0;self.slides=0
        def handle_starttag(self,tag,attrs):
            d=dict(attrs)
            if tag=='img':
                assert d['src'].startswith('data:image/png;base64,')
                with Image.open(io.BytesIO(base64.b64decode(d['src'].split(',',1)[1]))) as im:
                    im.verify()
                self.images+=1
            if tag=='section' and 'slide' in d.get('class','').split():self.slides+=1
            if tag in ('script','link','iframe','video','audio'):assert not d.get('src') and not d.get('href')
    audit=Audit();audit.feed((DOCS/'presentation.html').read_text())
    assert audit.slides==10 and audit.images==len(ASSETS)
    print(f'Generated {audit.slides} slides, {audit.images} embedded verified PNGs; A270+B270=540 seconds; no external runtime dependencies. Browser rendering not tested.')


if __name__=='__main__':
    main()
