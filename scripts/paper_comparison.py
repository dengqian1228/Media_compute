"""Download author Clip-art pairs, run OUR L0 core, and save an offline comparison.

python3 -m scripts.paper_comparison prepare  # network, once
python3 -m scripts.paper_comparison run      # offline, archived inputs
python3 -m scripts.paper_comparison check <experiment-directory>
Author outputs are comparison targets, never clean ground truth.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import platform
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import cv2
import numpy as np
from PIL import Image, JpegImagePlugin
from l0_smoothing.metrics import image_metrics, METRIC_SPEC
from l0_smoothing.workflow import run_and_save, replay_record, _new_run_directory

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/paper_clipart'
PAGE = 'https://jiaya.me/file/archive/projects/L0smoothing/ClipArt.htm'
BASE = 'https://jiaya.me/file/archive/projects/L0smoothing/results/JPEG/'
CASES = [('9', '西瓜', [180, 70, 300, 190]), ('20', '蜗牛', [180, 50, 300, 170])]
LAMBDAS = [.002, .008, .02, .08]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def pixels(p):
    with Image.open(p) as im:
        return np.array(im.convert('RGB'))


def prepare():
    if DATA.exists():
        raise ValueError('data/paper_clipart already exists; preserve archived sources')
    DATA.mkdir(parents=True)
    (DATA / 'ClipArt.source.html').write_bytes(urlopen(PAGE, timeout=40).read())
    items = []
    for name, title, roi in CASES:
        item = {'id': name, 'title': title, 'roi_xyxy': roi, 'files': {}}
        for role, filename in [('input', name + '.jpg'), ('author', name + '_L0.png')]:
            target = DATA / filename
            url = BASE + filename
            target.write_bytes(urlopen(url, timeout=40).read())
            with Image.open(target) as im:
                meta = {'url': url, 'file': filename, 'sha256': sha(target), 'size': list(im.size), 'mode': im.mode, 'format': im.format}
                if role == 'input':
                    assert im.format == 'JPEG'
                    meta.update(jpeg_quality=None, jpeg_quality_reason='not disclosed by author webpage; not inferred from quantization', sampling=JpegImagePlugin.get_sampling(im), quantization=im.quantization)
            item['files'][role] = meta
        assert item['files']['input']['size'] == item['files']['author']['size']
        items.append(item)
    save(DATA / 'manifest.json', {'retrieved_at': datetime.now(timezone.utc).isoformat(), 'page_url': PAGE,
        'page_sha256': sha(DATA / 'ClipArt.source.html'), 'paper': 'Xu et al., Image Smoothing via L0 Gradient Minimization, 2011',
        'source_kind': 'author project supplementary Clip-art examples; not claimed to be numbered paper figures',
        'license': 'No image license or original illustrator credit stated on the source page; retained with academic attribution; no open-license claim.',
        'clean_ground_truth_available': False, 'author_parameters': None,
        'preprocessing': 'Original downloadable bytes; no resize, re-encoding or alignment; ROIs used only for comparison.', 'cases': items})
    print(DATA / 'manifest.json')


def comparison(a, b, roi):
    x0, y0, x1, y1 = roi
    return {'full': image_metrics(a, b), 'roi': image_metrics(a[y0:y1, x0:x1], b[y0:y1, x0:x1])}


def make_html(out, manifest, rows):
    def fig(p, label, roi=None):
        with Image.open(p) as im:
            im = im.convert('RGB')
            if roi: im = im.crop(roi)
            stream = io.BytesIO(); im.save(stream, format='PNG')
        return '<figure><figcaption>' + label + '</figcaption><img src="data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode() + '"></figure>'
    html = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>论文官网 Clip-art 与本组 L0 对照</title><style>body{font-family:system-ui,sans-serif;max-width:1300px;margin:32px auto;padding:20px;color:#182a39}section{margin:45px 0}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}figure{margin:0;background:#f3f6f8;padding:10px}img{width:100%;height:260px;object-fit:contain}figcaption{padding:8px}table{border-collapse:collapse;width:100%}td,th{padding:8px;border:1px solid #ccc}.note{background:#fff3da;padding:16px}</style><h1>论文官网输入 → 作者结果 / 本组结果</h1><p class="note">作者输出不是干净真值。下表 PSNR / SSIM 仅表示与作者输出的一致程度，不是去伪影质量或复现精度排名。作者逐图参数和 JPEG 质量未公开。</p><p>来源：<a href="' + PAGE + '">Xu 等论文项目 Clip-art 样例页</a>；使用原始尺寸，本组核心未修改。</p>']
    for case in manifest['cases']:
        name, roi = case['id'], case['roi_xyxy']
        selected = next(r for r in rows if r['case'] == name and r['lambda'] == .008)
        src, author, ours = out/name/(name+'.jpg'), out/name/(name+'_L0.png'), out/selected['output']
        html += ['<section><h2>'+case['title']+'：默认 λ=0.008</h2><div class="grid">', fig(src,'官网原始 JPEG'),fig(author,'作者公开输出（非真值）'),fig(ours,'本组 L0，λ=0.008'),'</div><div class="grid">',fig(src,'同一局部：输入',roi),fig(author,'同一局部：作者',roi),fig(ours,'同一局部：本组',roi),'</div><table><tr><th>本组 λ</th><th>与作者全图 PSNR / SSIM</th><th>与作者局部 PSNR / SSIM</th><th>核心耗时</th></tr>']
        for r in rows:
            if r['case'] == name:
                html.append(f'<tr><td>{r["lambda"]}</td><td>{r["author_psnr_db"]:.4f} / {r["author_ssim"]:.6f}</td><td>{r["author_roi_psnr_db"]:.4f} / {r["author_roi_ssim"]:.6f}</td><td>{r["elapsed_seconds"]:.4f}s</td></tr>')
        html += ['</table><p>强平滑 λ=0.08 对照（仍用相同输入与局部）：</p><div class="grid">',fig(author,'作者局部',roi),fig(ours,'本组 λ=0.008',roi),fig(out/next(r['output'] for r in rows if r['case']==name and r['lambda']==.08),'本组 λ=0.08',roi),'</div></section>']
    html.append('</html>'); (out/'index.html').write_text(''.join(html),encoding='utf-8')


def run(output):
    started = time.perf_counter(); manifest = load(DATA/'manifest.json')
    for c in manifest['cases']:
        for f in c['files'].values():
            if sha(DATA/f['file']) != f['sha256']: raise ValueError('source hash mismatch: '+f['file'])
    out = _new_run_directory(Path(output), 'paper')
    shutil.copy2(DATA/'manifest.json',out/'source_manifest.json')
    rows=[]
    for c in manifest['cases']:
        directory=out/c['id'];directory.mkdir()
        for f in c['files'].values(): shutil.copy2(DATA/f['file'], directory/f['file'])
        source=directory/c['files']['input']['file']; author=pixels(directory/c['files']['author']['file'])
        for lam in LAMBDAS:
            rp=run_and_save(source,directory,lambda_=lam,kappa=2,beta_max=1e5)
            rec=load(rp); image=rp.parent/'output.png'
            m=comparison(author,pixels(image),c['roi_xyxy'])
            rows.append({'case':c['id'],'lambda':lam,'kappa':2,'beta_max':100000,'author_psnr_db':m['full']['psnr_db'],'author_ssim':m['full']['ssim'],'author_roi_psnr_db':m['roi']['psnr_db'],'author_roi_ssim':m['roi']['ssim'],'elapsed_seconds':rec['elapsed_seconds'],'iterations':rec['iterations'],'output':image.relative_to(out).as_posix(),'record':rp.relative_to(out).as_posix()})
    with (out/'author_agreement.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    make_html(out,manifest,rows)
    save(out/'experiment.json',{'created_at':datetime.now(timezone.utc).isoformat(),'command':[sys.executable,'-m','scripts.paper_comparison',*sys.argv[1:]],'cwd':str(Path.cwd()),'environment':{'python':platform.python_version(),'numpy':np.__version__,'opencv':cv2.__version__,'platform':platform.platform()},'core':'l0_smoothing.core.smooth_l0 via run_and_save; unchanged','core_sha256':sha(ROOT/'l0_smoothing/core.py'),'metric_spec':METRIC_SPEC,'metric_meaning':'agreement_with_author_output_NOT_restoration_quality','clean_ground_truth_available':False,'author_parameters':None,'jpeg_quality':None,'display_lambda':.008,'selection':'existing synthetic-demo default; fixed before comparing downloaded author outputs, not fitted to author pixels','rows':rows,'total_elapsed_seconds':time.perf_counter()-started,'artifacts':{p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}})
    print(out/'index.html'); return out


def check(out):
    out=Path(out); rec=load(out/'experiment.json');manifest=load(out/'source_manifest.json')
    for name,digest in rec['artifacts'].items():
        if sha(out/name)!=digest: raise ValueError('artifact mismatch: '+name)
    checkdir=_new_run_directory(out,'checks'); results=[]
    for c in manifest['cases']:
        author=pixels(out/c['id']/c['files']['author']['file'])
        for r in rec['rows']:
            if r['case']!=c['id']:continue
            m=comparison(author,pixels(out/r['output']),c['roi_xyxy'])
            for key,value in [('author_psnr_db',m['full']['psnr_db']),('author_ssim',m['full']['ssim']),('author_roi_psnr_db',m['roi']['psnr_db']),('author_roi_ssim',m['roi']['ssim'])]:
                if abs(r[key]-value)>1e-10:raise ValueError('metric mismatch')
            if r['lambda']==.008:
                rp,passed=replay_record(out/r['record'],output_parent=checkdir)
                if not passed: raise ValueError('core replay mismatch')
                results.append({'case':c['id'],'record':str(rp.relative_to(out)),'passed':passed})
    result={'created_at':datetime.now(timezone.utc).isoformat(),'actor':'AI automatic verification; not human review','passed':True,'artifacts_checked':len(rec['artifacts']),'metric_rows_checked':len(rec['rows']),'replays':results}
    save(checkdir/'checks.json',result);print(checkdir/'checks.json')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run','check']);p.add_argument('directory',nargs='?');p.add_argument('--output-dir',type=Path,default=ROOT/'results/paper_comparison');a=p.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='run':run(a.output_dir)
    elif a.directory:check(a.directory)
    else:p.error('check requires an experiment directory')

if __name__=='__main__':main()
