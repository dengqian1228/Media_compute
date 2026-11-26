"""Precompute genuine L0 results for a fully offline parameter-slider Demo.

python3 -m scripts.interactive_demo build
python3 -m scripts.interactive_demo check <output-directory>
The browser switches discrete, computed frames; it never interpolates images.
"""
import argparse
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from l0_smoothing import smooth_l0
from l0_smoothing.metrics import image_metrics, METRIC_SPEC
from l0_smoothing.workflow import _display_pixels, _environment, _new_run_directory

ROOT=Path(__file__).resolve().parents[1]
LAMBDAS=sorted(set([round(float(x),6) for x in np.geomspace(.001,.08,41)]+[.005,.008,.02,.04]))
KAPPAS=[round(1.5+i*.05,2) for i in range(21)]
PHOTO=ROOT/'results/structure_smoothing/experiment-20261117T102719Z-1b827758b270'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def pixels(p):
    with Image.open(p) as im:return np.array(im)
def edges(a):return cv2.Canny(cv2.cvtColor(a,cv2.COLOR_RGB2GRAY) if a.ndim==3 else a,60,120,apertureSize=3,L2gradient=True)
def scores(a,b,roi):
    x0,y0,x1,y1=roi
    return {'full':image_metrics(a,b),'roi':image_metrics(a[y0:y1,x0:x1],b[y0:y1,x0:x1])}
def pair(out,a,name,roi):
    p=out/'assets'/f'{name}.png';Image.fromarray(a).save(p)
    x0,y0,x1,y1=roi;q=out/'assets'/f'{name}_roi.png';Image.fromarray(a[y0:y1,x0:x1]).save(q)
    return {'full':p.relative_to(out).as_posix(),'roi':q.relative_to(out).as_posix()}
def safe_path(out,name):
    p=(out/name).resolve()
    if not p.is_relative_to(out.resolve()):raise ValueError('path escapes run directory')
    return p


def build(output,reuse=None):
    started=time.perf_counter();out=_new_run_directory(output,'interactive');(out/'assets').mkdir();(out/'inputs').mkdir()
    cases=[];sources=[];groups=[]
    prior=load(reuse/'manifest.json') if reuse else None
    reusable={}
    if prior:
        if prior['core_sha256']!=sha(ROOT/'l0_smoothing/core.py'):raise ValueError('reuse core mismatch')
        for f in prior['frames']:reusable[(f['case'],f['lambda'],f['kappa'])]=f
    def archive(path,expected):
        if sha(path)!=expected:raise ValueError('source hash mismatch: '+str(path))
        dest=out/'inputs'/path.name
        if dest.exists() and sha(dest)!=expected:raise ValueError('source name collision')
        shutil.copy2(path,dest)
        sources.append({'source':str(path.relative_to(ROOT)),'sha256':expected,'archived':dest.relative_to(out).as_posix()})
        return dest
    photos=load(ROOT/'data/structure_smoothing/manifest.json')
    for name,title in [('beach','沙滩'),('brick_window_gray','灰度砖墙'),('sunflower','向日葵')]:
        spec=photos['images'][name];src=archive(ROOT/spec['input_file'],spec['input_sha256'])
        roi=load(PHOTO/name/'roi.json')['xyxy']
        cases.append({'id':'photo_'+name,'mode':'photo','title':title,'quality':None,'roi':roi,'input':src.relative_to(out).as_posix(),'reference':None,'source_note':f"{spec['source_page']}；原图归档与预处理：data/structure_smoothing/manifest.json",'reference_kind':'none'})
    paper=load(ROOT/'data/paper_clipart/manifest.json')
    for c in paper['cases']:
        inp=c['files']['input'];author=c['files']['author'];src=archive(ROOT/'data/paper_clipart'/inp['file'],inp['sha256']);ref=archive(ROOT/'data/paper_clipart'/author['file'],author['sha256'])
        cases.append({'id':'paper_'+c['id'],'mode':'paper','title':c['title'],'quality':None,'roi':c['roi_xyxy'],'input':src.relative_to(out).as_posix(),'reference':ref.relative_to(out).as_posix(),'source_note':paper['page_url'],'reference_kind':'author_output_NOT_ground_truth'})
    frames=[]
    for case in cases:
        a=pixels(out/case['input']);roi=case['roi'];shared={'input':pair(out,a,case['id']+'_input',roi)}
        if case['mode']=='photo':
            e=edges(a);shared['input_edges']=pair(out,e,case['id']+'_input_edges',roi);case['input_edge_count']=int(np.count_nonzero(e))
        else:
            ref=pixels(out/case['reference']);shared['reference']=pair(out,ref,case['id']+'_reference',roi);case['baseline_metrics']=scores(ref,a,roi)
        case['shared']=shared
        default_lambda=.02 if case['mode']=='photo' else .008
        settings=list(dict.fromkeys([(lam,2.0) for lam in LAMBDAS]+[(default_lambda,k) for k in KAPPAS]))
        for lam,kappa in settings:
            index=len(frames);old=reusable.get((case['id'],lam,kappa))
            if old and old['input_sha256']==sha(out/case['input']):
                oldfile=reuse/old['output']['full']
                if sha(oldfile)!=prior['artifacts'][old['output']['full']]:raise ValueError('reuse frame changed')
                result=pixels(oldfile);iterations=old['iterations'];elapsed=old['elapsed_seconds'];float_hash=old['float64_sha256'];float_shape=old['float64_shape']
                reuse_record={'manifest':str((reuse/'manifest.json').relative_to(ROOT)),'frame':old['id'],'manifest_sha256':sha(reuse/'manifest.json')}
            else:
                r=smooth_l0(a.astype(np.float64)/255,lambda_=lam,kappa=kappa,beta_max=1e5)
                result=_display_pixels(r.image);iterations=r.iterations;elapsed=r.elapsed_seconds;float_hash=hashlib.sha256(r.image.tobytes()).hexdigest();float_shape=list(r.image.shape);reuse_record=None
            frame={'id':index,'case':case['id'],'lambda':lam,'kappa':kappa,'beta_max':1e5,'iterations':iterations,'elapsed_seconds':elapsed,'output':pair(out,result,f'frame_{index:03d}',roi),'float64_shape':float_shape,'float64_sha256':float_hash,'input_sha256':sha(out/case['input']),'reused_from':reuse_record}
            if case['mode']=='photo':
                e=edges(result);frame['edges']=pair(out,e,f'frame_{index:03d}_edges',roi);frame['edge_count']=int(np.count_nonzero(e))
            else:frame['metrics']=scores(ref,result,roi)
            frames.append(frame)
        print(f'{case["mode"]} / {case["title"]} / Q={case["quality"]}: {len(frames)} frames',flush=True)
    for case in cases:
        group={'id':case['id'],'mode':case['mode'],'title':case['title'],'sweeps':{}}
        default_lambda=.02 if case['mode']=='photo' else .008
        group['sweeps']['lambda']=[f['id'] for lam in LAMBDAS for f in frames if f['case']==case['id'] and f['lambda']==lam and f['kappa']==2.0]
        group['sweeps']['kappa']=[f['id'] for k in KAPPAS for f in frames if f['case']==case['id'] and f['lambda']==default_lambda and f['kappa']==k]
        groups.append(group)
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'command':[sys.executable,'-m','scripts.interactive_demo',*sys.argv[1:]],'cwd':str(Path.cwd()),'environment':{**_environment(),'opencv':cv2.__version__},'core_sha256':sha(ROOT/'l0_smoothing/core.py'),'lambdas':LAMBDAS,'kappas':KAPPAS,'cases':cases,'groups':groups,'frames':frames,'sources':sources,'metric_spec':METRIC_SPEC,'canny':{'low':60,'high':120,'aperture':3,'l2':True,'same_settings_for_both_images':True},'storage':'Lossless displayed PNGs, source bytes, parameters and float64 hashes retained; no per-frame NPY files. Recompute the core to reproduce float values.','display':'one-factor sweeps: lambda varies with kappa=2; kappa varies with lambda=.02 for photos or .008 for JPEG. No interpolation.','build_seconds':time.perf_counter()-started,'artifacts':{p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}}
    save(out/'manifest.json',manifest)
    render(out)
    print(out/'index.html',flush=True)
    return out


def render(out):
    manifest=load(out/'manifest.json');template=(ROOT/'scripts/interactive_demo.html').read_text()
    credit=['# 图像来源与许可\n\n本演示对归档输入进行了L0平滑、裁剪展示和边缘提取。\n\n| 素材 | 原作者 | 来源与许可 |\n| --- | --- | --- |\n']
    for name,spec in load(ROOT/'data/structure_smoothing/manifest.json')['images'].items():
        credit.append(f"| {name} | {spec['author']} | [来源]({spec['source_page']})；{spec['license']} |\n")
    credit.append('\n砖墙及其衍生结果保留 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)；向日葵按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 署名。照片使用A实验已归档的缩放/灰度输入，本演示未再次缩放计算输入。\n\n西瓜与蜗牛：[Xu等2011论文官网Clip-art样例](https://jiaya.me/file/archive/projects/L0smoothing/ClipArt.htm)，成对使用JPEG输入及作者输出。官网未注明原图片作者或明确许可，不声称为本组原创或开放授权。作者结果不是干净真值。\n\n原始输入在inputs/，显示结果在assets/，参数与来源摘要在manifest.json。完整复现脚本位于项目仓库。\n')
    (out/'SOURCE_CREDITS.md').write_text(''.join(credit),encoding='utf-8')
    data=json.dumps(manifest,ensure_ascii=False,allow_nan=False).replace('</','<\\/')
    html=template.replace('__DATA__',data)
    (out/'index.html').write_text(html,encoding='utf-8')
    base='../'+out.relative_to(ROOT).as_posix()+'/'
    (ROOT/'docs/demo_interactive.html').write_text(html.replace('<!--BASE-->','<base href="'+base+'">'),encoding='utf-8')


def check(out):
    m=load(out/'manifest.json');cases={c['id']:c for c in m['cases']}
    for name,digest in m['artifacts'].items():
        if sha(safe_path(out,name))!=digest:raise ValueError('artifact mismatch: '+name)
    assert {c['mode'] for c in m['cases']}=={'photo','paper'}
    assert len(m['groups'])==5 and len(m['frames'])==325
    all_sweep_ids=set()
    for g in m['groups']:
        for axis,ids in g['sweeps'].items():
            assert ids and len(ids)==len(m[{'lambda':'lambdas','kappa':'kappas'}[axis]])
            fs=[m['frames'][i] for i in ids];all_sweep_ids.update(ids)
            if axis=='lambda':assert all(f['kappa']==2 for f in fs) and [f['lambda'] for f in fs]==m['lambdas']
            elif axis=='kappa':assert len({f['lambda'] for f in fs})==1 and [f['kappa'] for f in fs]==m['kappas']
            else:raise AssertionError('unsupported sweep')
    assert all_sweep_ids==set(range(len(m['frames'])))
    replayed=[];checked_modes=set()
    for f in m['frames']:
        c=cases[f['case']];a=pixels(out/c['input']);b=pixels(out/f['output']['full']);x0,y0,x1,y1=c['roi']
        assert np.array_equal(b[y0:y1,x0:x1],pixels(out/f['output']['roi']))
        if c['mode']=='photo':
            assert np.array_equal(edges(b),pixels(out/f['edges']['full']))
            assert int(np.count_nonzero(edges(b)))==f['edge_count']
        else:
            recomputed=scores(pixels(out/c['reference']),b,c['roi'])
            for region in ['full','roi']:
                for key in ['psnr_db','ssim']:assert abs(recomputed[region][key]-f['metrics'][region][key])<1e-10
        if c['mode'] not in checked_modes and f['lambda']==.008 and f['kappa']==2:
            r=smooth_l0(a.astype(np.float64)/255,lambda_=f['lambda'],kappa=f['kappa'],beta_max=f['beta_max'])
            assert np.array_equal(_display_pixels(r.image),b)
            assert hashlib.sha256(r.image.tobytes()).hexdigest()==f['float64_sha256']
            replayed.append(f['id']);checked_modes.add(c['mode'])
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'passed':True,'artifacts_checked':len(m['artifacts']),'frames_checked':len(m['frames']),'float_and_display_replayed_frames':replayed,'all_output_rois_canny_and_metrics_recomputed':True,'executed_by':'AI; not human review'}
    dest=_new_run_directory(out,'checks')/'checks.json';save(dest,result);print(dest)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','check','render']);p.add_argument('directory',nargs='?',type=Path);p.add_argument('--output-dir',type=Path,default=ROOT/'results/interactive_demo');p.add_argument('--reuse',type=Path);a=p.parse_args()
    if a.action=='build':build(a.output_dir.resolve(),a.reuse.resolve() if a.reuse else None)
    elif not a.directory:p.error('directory is required')
    elif a.action=='check':check(a.directory.resolve())
    else:render(a.directory.resolve())

if __name__=='__main__':main()
