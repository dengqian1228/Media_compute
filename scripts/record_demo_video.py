"""Record a real browser session that launches the group's CLI and views its output.

Uses optional Playwright/FFmpeg authoring tools, NOT a virtual environment.
Only binds to loopback; records actual subprocess output and actual saved pixels.
No synthetic terminal transcript or generated image frames are used.
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from playwright.async_api import async_playwright
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
CONTROL=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>L0 Demo 实机录制</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f3f8f8;color:#19313e;font-family:"Noto Sans CJK SC",sans-serif;padding:45px 60px}h1{font-size:34px;margin:10px 0}small{color:#4b737c}p{font-size:21px}.card{padding:28px;background:white;border-radius:16px;margin-top:28px}pre{height:230px;padding:24px;background:#152c36;color:#d7f4e6;border-radius:12px;font:17px/1.6 monospace;white-space:pre-wrap;overflow-wrap:anywhere;overflow:auto}button{background:#145e69;color:white;border:0;border-radius:8px;padding:14px 28px;font-size:20px;cursor:pointer}button:disabled{opacity:.6}#status{display:inline-block;margin-left:18px;color:#14646e}footer{font-size:16px;margin-top:24px;color:#526b73}</style>
<small>预录演示 · 本组程序真实运行 · 系统 Python</small><h1>Clip-art JPEG 去伪影：运行与结果对照</h1>
<p>论文官网输入 → 本组 L0 平滑 → 作者 / 本组全图与局部比较</p>
<div class="card"><button id="run">运行 Demo</button><span id="status">已准备官网原始输入，无需联网</span><pre id="terminal">$ /usr/bin/python3 -m scripts.paper_comparison run --output-dir results/paper_comparison/video_demo</pre></div>
<footer>2 幅输入 × 4 档 λ；κ=2，βmax=100000。作者结果不是干净真值。</footer>
<script>
const run=document.querySelector('#run'),term=document.querySelector('#terminal'),status=document.querySelector('#status');
run.onclick=async()=>{run.disabled=true;await fetch('/_start',{method:'POST'});status.textContent='正在执行本组算法…';let timer=setInterval(async()=>{let s=await(await fetch('/_status')).json();term.textContent=s.command+'\n'+s.stdout;if(s.done){clearInterval(timer);status.textContent=s.code===0?'运行完成，已保存8组结果':'运行失败，请查看真实输出';window.runResult=s;}},150);};
</script></html>'''

VIEWER_JS=r'''() => {
const sections=[...document.querySelectorAll('section')];
for(const el of [...document.body.children]){if(el.tagName!=='SECTION')el.style.display='none';}
const nav=document.createElement('header');nav.id='video-nav';nav.innerHTML=`<div class="eyebrow">预录实机演示 · 原尺寸数据 · 本组 L0 核心</div><h1>论文官网输入与本组结果对照</h1><div class="controls"><button data-case="0">西瓜</button><button data-case="1">蜗牛</button><span></span><button data-view="all">全图与局部</button><button data-view="roi">局部细节</button><button data-view="strong">强平滑对照</button><button data-view="table">完整参数表</button></div><p>PSNR / SSIM 仅表示与作者输出的一致程度，作者输出不是干净真值。</p>`;
document.body.prepend(nav);
const footer=document.createElement('footer');footer.id='video-footer';footer.textContent='来源：Xu 等（2011）论文项目官网 · 同一原始输入 · 本组 λ=0.008，强平滑 λ=0.08';document.body.append(footer);
let c=0,v='all';function show(){sections.forEach((s,i)=>{s.style.display=i===c?'block':'none';let grids=[...s.querySelectorAll('.grid')];grids.forEach((g,j)=>{g.style.display=(v==='all'&&j<2||v==='roi'&&j===1||v==='strong'&&j===2)?'grid':'none';g.classList.toggle('large',v!=='all');});s.querySelector('table').style.display=v==='table'?'table':'none';s.querySelectorAll('h2,p').forEach(x=>x.style.display='none');});nav.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.case!==undefined?+b.dataset.case===c:b.dataset.view===v));}
nav.querySelectorAll('button').forEach(b=>b.onclick=()=>{if(b.dataset.case!==undefined)c=+b.dataset.case;else v=b.dataset.view;show();});show();
}'''
CSS='''*{box-sizing:border-box}body{margin:0!important;padding:24px 36px!important;max-width:none!important;background:#f3f8f8;color:#19313e;font-family:"Noto Sans CJK SC",sans-serif}#video-nav .eyebrow{font-size:14px;color:#57747c}#video-nav h1{font-size:29px;margin:5px 0 14px}#video-nav p{font-size:16px;margin:10px 0 14px;color:#845b1e}.controls{display:flex;gap:8px}.controls span{width:20px}.controls button{font:17px sans-serif;padding:9px 15px;border:1px solid #a9c9cd;background:white;color:#1e535c;border-radius:6px;cursor:pointer}.controls button.active{background:#145e69;color:white}section{margin:0!important}.grid{gap:16px!important;margin:10px 0}figure{padding:6px 10px!important;background:white!important;border-radius:8px}figcaption{padding:3px!important;font-size:16px;color:#1a535e}img{height:180px!important;max-width:100%;image-rendering:auto}.large img{height:390px!important}table{background:white;font-size:21px;margin-top:38px;border-collapse:collapse}th,td{padding:18px!important}#video-footer{position:fixed;bottom:12px;left:36px;color:#536e75;font-size:14px}'''


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

async def record(args):
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    rec=ROOT/'results/demo_video'/('record-'+stamp);rec.mkdir(parents=True,exist_ok=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():raise ValueError('refusing to replace an existing video; choose another output')
    command=['/usr/bin/python3','-m','scripts.paper_comparison','run','--output-dir','results/paper_comparison/video_demo']
    state={'command':'$ '+' '.join(command),'stdout':'','done':False,'code':None}
    lock=threading.Lock();started=False;events=[]
    def worker():
        env=os.environ.copy();env.pop('PYTHONPATH',None)
        t=time.perf_counter()
        proc=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env)
        for line in proc.stdout:
            with lock:state['stdout']+=line
        code=proc.wait()
        with lock:state.update(done=True,code=code,process_elapsed_seconds=time.perf_counter()-t)
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
        def log_message(self,*a):pass
        def do_GET(self):
            if self.path in ('/_recorder','/_status'):
                with lock:raw=CONTROL.encode() if self.path=='/_recorder' else json.dumps(state,ensure_ascii=False).encode()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8' if self.path=='/_recorder' else 'application/json');self.end_headers();self.wfile.write(raw)
            else:super().do_GET()
        def do_POST(self):
            nonlocal started
            if self.path!='/_start' or started:self.send_error(409);return
            started=True;threading.Thread(target=worker,daemon=True).start();self.send_response(200);self.end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}'
    begin=time.perf_counter()
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True);browser_version=browser.version
        context=await browser.new_context(viewport={'width':1280,'height':720},device_scale_factor=1,locale='zh-CN',record_video_dir=str(rec/'raw'),record_video_size={'width':1280,'height':720})
        page=await context.new_page();video=page.video
        page.on('pageerror',lambda error: print('Browser error: '+str(error),flush=True))
        async def hold(label,seconds):
            events.append({'elapsed_seconds':time.perf_counter()-begin,'label':label,'hold_seconds':seconds});print(label,flush=True);await asyncio.sleep(seconds)
        await page.goto(url+'/_recorder');await hold('准备执行本组Demo',3)
        await page.click('#run');await page.wait_for_function('window.runResult && window.runResult.done',timeout=120000)
        if state['code']!=0:raise RuntimeError(state['stdout'])
        await page.screenshot(path=str(rec/'command_completed.png'));await hold('真实命令执行完成',3)
        output=(ROOT/Path(state['stdout'].strip().splitlines()[-1])).resolve();assert output.is_file()
        await page.goto(url+'/'+output.relative_to(ROOT).as_posix());await page.add_style_tag(content=CSS);await page.evaluate(VIEWER_JS)
        await page.mouse.move(1230,685);await page.screenshot(path=str(rec/'watermelon_full.png'))
        await hold('西瓜：输入、作者与本组全图及局部',7)
        await page.click('[data-view="roi"]');await page.mouse.move(1230,685);await hold('西瓜：相同局部细节',6)
        await page.click('[data-case="1"]');await page.click('[data-view="all"]');await page.mouse.move(1230,685);await page.screenshot(path=str(rec/'snail_full.png'));await hold('蜗牛：输入、作者与本组',7)
        await page.click('[data-view="roi"]');await page.mouse.move(1230,685);await hold('蜗牛：默认参数局部',6)
        await page.click('[data-view="strong"]');await page.mouse.move(1230,685);await page.screenshot(path=str(rec/'snail_strong.png'));await hold('蜗牛：强平滑对照',7)
        await page.click('[data-view="table"]');await page.mouse.move(1230,685);await page.screenshot(path=str(rec/'metrics.png'));await hold('全部参数与真实指标',6)
        await page.click('[data-view="all"]');await page.mouse.move(1230,685);await hold('演示结束',3)
        # Persist the exact viewer DOM; reattach controls for offline browsing.
        dom=await page.content();(rec/'browser_view.html').write_text(dom,encoding='utf-8')
        await context.close();raw=Path(await video.path());await browser.close()
    server.shutdown()
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    transcode=[ffmpeg,'-y','-i',str(raw),'-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p','-r','25','-movflags','+faststart','-an',str(args.output)]
    result=subprocess.run(transcode,capture_output=True,text=True,check=True);(rec/'ffmpeg.log').write_text(result.stderr)
    subprocess.run([ffmpeg,'-v','error','-i',str(args.output),'-f','null','-'],check=True,capture_output=True)
    probe=subprocess.run([ffmpeg,'-i',str(args.output)],capture_output=True,text=True).stderr
    match=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe);duration=int(match[1])*3600+int(match[2])*60+float(match[3])
    assert duration<75,(duration,'exceeds allocated slide time')
    # Poster is captured from the actual browser session, not an invented frame.
    poster=args.output.with_suffix('.png');shutil.copy2(rec/'snail_full.png',poster)
    payload={'created_at':datetime.now(timezone.utc).isoformat(),'recording':'Playwright Chromium browser video; actual local subprocess execution; not a desktop/PowerPoint recording','real_time':True,'speed_factor':1,'audio':False,'duration_seconds':duration,'width':1280,'height':720,'fps':25,'codec':'H.264','pixel_format':'yuv420p','cli_command':command,'cli_state':state,'experiment':str(output.parent.relative_to(ROOT)),'output_video':str(args.output.relative_to(ROOT)),'video_sha256':sha(args.output),'poster':str(poster.relative_to(ROOT)),'poster_sha256':sha(poster),'raw_video':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw),'timeline':events,'transcode_command':transcode,'full_video_decode_passed':True,'view_changes':'Browser CSS and tab controls added for recording; source images, output pixels and metrics unchanged. Saved DOM is a static snapshot.','browser_version':browser_version}
    (rec/'recording.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    args.output.with_suffix('.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'video':str(args.output),'seconds':duration,'record':str(rec/'recording.json')},ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'docs/media/demo_paper_comparison.mp4');args=parser.parse_args();args.output=args.output.resolve();asyncio.run(record(args))

if __name__=='__main__':main()
