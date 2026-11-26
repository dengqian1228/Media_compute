"""Assemble the four course tasks, genuine iteration traces and offline assets.

python3 -m scripts.course_demo build --jpeg <public-jpeg-result-directory>
python3 -m scripts.course_demo check <course-directory>
python3 -m scripts.course_demo render <course-directory>
"""
import argparse
import copy
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
from l0_smoothing import core
from l0_smoothing.workflow import _display_pixels, _new_run_directory, _environment, run_and_save, replay_record
from scripts.interactive_demo import sha, load, save, pixels, pair, scores

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_BASE=ROOT/'results/interactive_demo/interactive-20261125T122838Z-fce049eb5fea'
CANNY_LOWS=list(range(20,141,10))

def canny(a,low=60):
    return cv2.Canny(cv2.cvtColor(a,cv2.COLOR_RGB2GRAY) if a.ndim==3 else a,low,low*2,apertureSize=3,L2gradient=True)

def merge_source(out,source,namespace,m):
    old=load(source/'manifest.json')
    assert old['core_sha256']==sha(ROOT/'l0_smoothing/core.py')
    for name,digest in old['artifacts'].items():
        p=(source/name).resolve()
        assert p.is_relative_to(source.resolve()) and sha(p)==digest,name
    shutil.copytree(source,out/namespace)
    def pref(x):return f'{namespace}/{x}'
    def paths(pair):return {k:pref(v) for k,v in pair.items()}
    offset=len(m['frames'])
    for c in copy.deepcopy(old['cases']):
        c['input']=pref(c['input'])
        if c['reference']:c['reference']=pref(c['reference'])
        c['shared']={k:paths(v) for k,v in c['shared'].items()}
        m['cases'].append(c)
    for f in copy.deepcopy(old['frames']):
        f['id']+=offset;f['output']=paths(f['output'])
        if 'edges' in f:f['edges']=paths(f['edges'])
        m['frames'].append(f)
    for g in copy.deepcopy(old['groups']):
        g['sweeps']={k:[i+offset for i in ids] for k,ids in g['sweeps'].items()};m['groups'].append(g)
    m['provenance'].append({'directory':str(source.relative_to(ROOT)),'manifest_sha256':sha(source/'manifest.json'),'copied_to':namespace})
    (out/f'SOURCE_{namespace}.md').write_text((source/'SOURCE_CREDITS.md').read_text() if (source/'SOURCE_CREDITS.md').exists() else json.dumps(old.get('sources',old.get('source_manifest',{})),ensure_ascii=False,indent=2),encoding='utf-8')
    return old

def build(base,jpeg,output):
    start=time.perf_counter();out=_new_run_directory(output,'course');(out/'assets').mkdir()
    m={'created_at':datetime.now(timezone.utc).isoformat(),'command':[sys.executable,'-m','scripts.course_demo',*sys.argv[1:]],'environment':{**_environment(),'opencv':cv2.__version__},'core_sha256':sha(ROOT/'l0_smoothing/core.py'),'cases':[],'groups':[],'frames':[],'provenance':[],'canny_lows':CANNY_LOWS}
    original=merge_source(out,base,'photo_paper',m);public=merge_source(out,jpeg,'public_jpeg',m)
    m.update({k:original[k] for k in ['lambdas','kappas']});m['qualities']=public['qualities']
    case_map={c['id']:c for c in m['cases']};m['edge_sweeps']={};m['traces']={}
    for g in m['groups']:
        if g['mode']!='photo':continue
        c=case_map[g['id']];source=pixels(out/c['input']);roi=c['roi']
        f=next(f for f in m['frames'] if f['case']==c['id'] and f['lambda']==.02 and f['kappa']==2)
        smoothed=pixels(out/f['output']['full']);items=[]
        for low in CANNY_LOWS:
            a=canny(source,low);b=canny(smoothed,low)
            items.append({'low':low,'high':low*2,'input_edges':pair(out,a,c['id']+f'_canny_{low}_input',roi),'edges':pair(out,b,c['id']+f'_canny_{low}_output',roi),'input_count':int(np.count_nonzero(a)),'output_count':int(np.count_nonzero(b)),'frame':f['id']})
        m['edge_sweeps'][g['id']]=items
        # Observe returns of the existing core's own FFT update, without changing it.
        snapshots=[];trace_start=time.perf_counter()
        def profile(frame,event,arg):
            if event=='return' and frame.f_code is core._fft_update.__code__:
                snapshots.append((arg.copy(),float(frame.f_locals['beta']),time.perf_counter()-trace_start))
        previous=sys.getprofile()
        try:
            sys.setprofile(profile);r=core.smooth_l0(source.astype(np.float64)/255,lambda_=.02,kappa=2,beta_max=1e5)
        finally:sys.setprofile(previous)
        assert np.array_equal(_display_pixels(r.image),smoothed)
        assert len(snapshots)==r.iterations
        ids=[]
        for i,(array,beta,elapsed) in enumerate(snapshots):
            result=array[...,0] if source.ndim==2 else array;display=_display_pixels(result);edge=canny(display)
            frame={'id':len(m['frames']),'case':c['id'],'lambda':.02,'kappa':2.0,'beta_max':1e5,'beta':beta,'threshold':.02/beta,'iterations':i+1,'total_iterations':len(snapshots),'elapsed_seconds':elapsed,'timing_kind':'cumulative with Python profiling overhead','kind':'actual_core_iteration','output':pair(out,display,c['id']+f'_iteration_{i+1}',roi),'edges':pair(out,edge,c['id']+f'_iteration_{i+1}_edges',roi),'edge_count':int(np.count_nonzero(edge)),'float64_sha256':hashlib.sha256(result.tobytes()).hexdigest(),'float64_shape':list(result.shape)}
            m['frames'].append(frame);ids.append(frame['id'])
        g['sweeps']['iteration']=ids;m['traces'][g['id']]={'frame_ids':ids,'final_equals_cached_output':True,'observed_function':'l0_smoothing.core._fft_update','core_unchanged':True}
        print('edge/iteration:',c['title'],len(ids),flush=True)
    # Real saved RGB/L runs and replays, available as evidence even in offline mode.
    m['workflow_examples']=[]
    for case_id in ['photo_beach','photo_brick_window_gray']:
        c=case_map[case_id];run=run_and_save(out/c['input'],out/'workflow',lambda_=.02,kappa=2)
        replay,passed=replay_record(run,out/'workflow');assert passed
        rec=load(run)
        m['workflow_examples'].append({'case':case_id,'title':c['title'],'mode':rec['input']['mode'],'record':run.relative_to(out).as_posix(),'replay':replay.relative_to(out).as_posix(),'input':(run.parent/rec['input']['copy']).relative_to(out).as_posix(),'output':(run.parent/rec['output']['display']).relative_to(out).as_posix(),'float':(run.parent/rec['output']['float']).relative_to(out).as_posix(),'run_data':rec,'comparison':load(replay)['comparison']})
    m['build_seconds']=time.perf_counter()-start
    m['artifacts']={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
    save(out/'manifest.json',m);render(out);print(out,flush=True)

def render(out):
    m=load(out/'manifest.json');data=json.dumps(m,ensure_ascii=False,allow_nan=False).replace('</','<\\/')
    template=(ROOT/'scripts/course_demo.html').read_text(encoding='utf-8');html=template.replace('__DATA__',data)
    (out/'index.html').write_text(html,encoding='utf-8')
    base='../'+out.relative_to(ROOT).as_posix()+'/'
    (ROOT/'docs/demo_interactive.html').write_text(html.replace('<!--BASE-->','<base href="'+base+'">'),encoding='utf-8')

def check(out):
    m=load(out/'manifest.json');cs={c['id']:c for c in m['cases']}
    for name,digest in m['artifacts'].items():
        path=(out/name).resolve();assert path.is_relative_to(out.resolve()) and sha(path)==digest,name
    assert {g['mode'] for g in m['groups']}=={'photo','paper','jpeg'}
    assert len(m['groups'])==7 and all('synthetic' not in c['id'] for c in m['cases'])
    for g in m['groups']:
        for axis,ids in g['sweeps'].items():
            fs=[m['frames'][i] for i in ids]
            assert all(cs[f['case']]['mode']==g['mode'] for f in fs)
            if axis=='lambda':assert [f['lambda'] for f in fs]==m['lambdas'] and all(f['kappa']==2 for f in fs)
            elif axis=='kappa':assert [f['kappa'] for f in fs]==m['kappas'] and len({f['lambda'] for f in fs})==1
            elif axis=='quality':assert [cs[f['case']]['quality'] for f in fs]==m['qualities'] and all(f['lambda']==.008 and f['kappa']==2 for f in fs)
            elif axis=='iteration':assert [f['iterations'] for f in fs]==list(range(1,len(fs)+1))
            else:raise AssertionError(axis)
    for f in m['frames']:
        c=cs[f['case']];a=pixels(out/f['output']['full']);x0,y0,x1,y1=c['roi']
        assert np.array_equal(a[y0:y1,x0:x1],pixels(out/f['output']['roi']))
        if c['mode']=='photo':assert np.array_equal(canny(a),pixels(out/f['edges']['full']))
        else:
            actual=scores(pixels(out/c['reference']),a,c['roi'])
            for view in ['full','roi']:
                for metric in ['psnr_db','ssim']:assert abs(actual[view][metric]-f['metrics'][view][metric])<1e-10
    for group,items in m['edge_sweeps'].items():
        c=cs[group]
        for item in items:
            f=m['frames'][item['frame']]
            for path,source in [(item['input_edges'],c['shared']['input']),(item['edges'],f['output'])]:
                edge=canny(pixels(out/source['full']),item['low']);assert np.array_equal(edge,pixels(out/path['full']))
                x0,y0,x1,y1=c['roi'];assert np.array_equal(edge[y0:y1,x0:x1],pixels(out/path['roi']))
    for w in m['workflow_examples']:
        path,passed=replay_record(out/w['record'],out/'checks_workflow');assert passed
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'passed':True,'frames_checked':len(m['frames']),'artifacts_checked':len(m['artifacts']),'edge_pairs_checked':sum(map(len,m['edge_sweeps'].values())),'workflow_modes':['RGB','L'],'all_metrics_and_rois_recomputed':True,'executor':'AI; not member review'}
    dest=_new_run_directory(out,'checks')/'checks.json';save(dest,result);print(dest)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','render','check']);p.add_argument('directory',type=Path,nargs='?');p.add_argument('--base',type=Path,default=DEFAULT_BASE);p.add_argument('--jpeg',type=Path);p.add_argument('--output-dir',type=Path,default=ROOT/'results/course_demo');a=p.parse_args()
    if a.action=='build':
        if not a.jpeg:p.error('--jpeg is required')
        build(a.base.resolve(),a.jpeg.resolve(),a.output_dir.resolve())
    else:
        if not a.directory:p.error('directory is required')
        (render if a.action=='render' else check)(a.directory.resolve())
if __name__=='__main__':main()
