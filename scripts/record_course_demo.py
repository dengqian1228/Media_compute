"""Record all four course tasks: cached parameter sweeps and actual run/save/replay."""
import argparse
import asyncio
import hashlib
import json
import re
import shutil
import subprocess
import time
import threading
from scripts.demo_server import DemoServer
from datetime import datetime,timezone
from pathlib import Path
import imageio_ffmpeg
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

async def record(args):
    if args.output.exists():raise ValueError('choose a new video filename; existing recordings are preserved')
    rec=ROOT/'results/demo_video'/('dynamic-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));rec.mkdir(parents=True,exist_ok=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    events=[];start=time.perf_counter();errors=[]
    server=DemoServer(0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_address[1]}/docs/demo_interactive.html'
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True);version=browser.version
        context=await browser.new_context(viewport={'width':1600,'height':1080},record_video_size={'width':1600,'height':1080},record_video_dir=str(rec/'raw'),locale='zh-CN')
        page=await context.new_page();video=page.video;page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(url);await page.wait_for_function('window.demoReady===true',timeout=60000)
        manifest=await page.locator('#demo-data').text_content()
        await page.evaluate('''()=>{window.recordRenderedFrames=[];document.querySelector('.badge').textContent='预录 · 参数缓存 / 读写真运行';let cursor=document.createElement('div');cursor.id='record-cursor';cursor.style='position:fixed;width:22px;height:22px;border:3px solid #ee9d28;border-radius:50%;pointer-events:none;z-index:9999;transform:translate(-50%,-50%);';document.body.append(cursor);document.addEventListener('mousemove',e=>{cursor.style.left=e.clientX+'px';cursor.style.top=e.clientY+'px';});}''')
        async def ready():await page.wait_for_function('window.demoReady===true && !document.querySelector("#stage").classList.contains("loading")',timeout=60000)
        async def mark(label,hold=0):
            state=await page.evaluate("window.currentTask==='io'?{task:'io'}:window.currentFrame");events.append({'seconds':time.perf_counter()-start,'label':label,'frame':state});print(label,state,flush=True)
            if hold:await asyncio.sleep(hold)
        async def choose(task,source,axis='lambda',view='full',kind='jpeg'):
            await page.click('#task-'+task);await ready()
            if task=='jpeg':
                await page.select_option('#jpegKind',kind);await ready()
            await page.select_option('#sourceSelect',source);await ready()
            await page.select_option('#sweep',axis);await ready()
            await page.click('#'+view);await ready()
        async def drag(label,seconds):
            await ready();box=await page.locator('#parameter').bounding_box()
            x0=box['x']+7;x1=box['x']+box['width']-7;y=box['y']+box['height']/2
            await page.mouse.move(x0,y);await page.mouse.down();await asyncio.sleep(.25)
            await mark(label+'：起点')
            steps=80
            for i in range(1,steps+1):
                await page.mouse.move(x0+(x1-x0)*i/steps,y);await asyncio.sleep(seconds/steps)
            await page.mouse.up();await page.wait_for_function('!document.querySelector("#stage").classList.contains("loading")')
            await mark(label+'：终点',.4)
            await page.screenshot(path=str(rec/(label+'.png')))
        await mark('四项课程功能',1)
        await choose('smooth','photo_beach','lambda');await drag('01_结构平滑lambda',4)
        await choose('smooth','photo_beach','kappa');await drag('02_结构平滑kappa',3)
        await choose('smooth','photo_beach','iteration');await drag('03_本组核心实际迭代',3)
        await page.click('#task-io');await page.wait_for_function('!document.querySelector("#run").disabled')
        io_records=[]
        for name in ['brick_window_gray','beach']:
            await page.select_option('#ioSample',name)
            await page.click('#run');await page.wait_for_function('window.ioResult && window.ioResult.ok',timeout=60000)
            await page.click('#replay');await page.wait_for_function('window.ioReplay && window.ioReplay.passed===true',timeout=60000)
            io_records.append(await page.evaluate('({run:window.ioResult,replay:window.ioReplay})'))
            await mark('真实读写复现_'+name,1)
        await page.screenshot(path=str(rec/'04_真实读写与复现.png'))
        await choose('edge','photo_brick_window_gray','lambda','roi');await drag('05_同参Canny与平滑',4)
        await choose('edge','photo_brick_window_gray','canny','roi');await drag('06_两图相同阈值对',3)
        await choose('jpeg','jpeg_openmoji_fox_q30','quality');await drag('07_公开干净素材JPEG质量',4)
        await choose('jpeg','jpeg_openmoji_fox_q30','lambda','roi');await drag('08_JPEG恢复与指标',4)
        await choose('jpeg','jpeg_openmoji_turtle_q30','lambda','roi');await drag('09_过平滑负例',3)
        paper_steps=[]
        for source,label in [('paper_9','10_西瓜局部'),('paper_20','11_蜗牛局部')]:
            await choose('jpeg',source,'lambda','roi','paper')
            fixed_columns=None
            for lam in [.001,.008,.08]:
                await page.locator(f'[data-paper-lambda="{lam}"]').click()
                await page.wait_for_function('(v)=>window.currentFrame.lambda===v && !document.querySelector("#stage").classList.contains("loading")',arg=lam)
                state=await page.evaluate('window.currentFrame')
                assert state['case']==source and state['view']=='roi' and state['kappa']==2
                sources=await page.locator('#grid img').evaluate_all('(ims)=>ims.map(im=>im.src)')
                if fixed_columns is not None:assert sources[:2]==fixed_columns
                fixed_columns=sources[:2]
                assert await page.locator('#grid img').evaluate_all('(ims)=>ims.every(im=>im.complete && im.naturalWidth>0)')
                paper_steps.append({'frame':state,'fixed_columns':sources[:2],'output':sources[2]})
                await mark(label+f'：lambda={lam}',2)
                await page.screenshot(path=str(rec/(label+f'_lambda_{lam}.png')))

        await mark('演示结束',1)
        history=await page.evaluate('window.recordRenderedFrames');await context.close();raw=Path(await video.path());await browser.close()
    if errors:raise RuntimeError(errors)
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();command=[ffmpeg,'-y','-i',str(raw),'-c:v','libx264','-crf','20','-preset','medium','-pix_fmt','yuv420p','-r','25','-movflags','+faststart','-an',str(args.output)]
    r=subprocess.run(command,capture_output=True,text=True,check=True);(rec/'ffmpeg.log').write_text(r.stderr)
    subprocess.run([ffmpeg,'-v','error','-i',str(args.output),'-f','null','-'],capture_output=True,check=True)
    probe=subprocess.run([ffmpeg,'-i',str(args.output)],capture_output=True,text=True).stderr
    m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe);duration=int(m[1])*3600+int(m[2])*60+float(m[3]);assert duration<75,duration
    poster=args.output.with_suffix('.png');shutil.copy2(rec/'01_结构平滑lambda.png',poster)
    payload={'created_at':datetime.now(timezone.utc).isoformat(),'demo_kind':'course_tasks','source_scope':'real_photos_paper_and_attributed_public_clipart','duration_seconds':duration,'width':1600,'height':1080,'fps':25,'codec':'H.264','audio':False,'speed_factor':1,'recording':'actual Chromium parameter drags plus actual local Python run/save/replay; parameter images precomputed, no interpolation','browser_version':version,'video_sha256':sha(args.output),'poster_sha256':sha(poster),'output_video':str(args.output.relative_to(ROOT)),'poster':str(poster.relative_to(ROOT)),'raw_video':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw),'demo_page':str(args.demo.relative_to(ROOT)),'demo_manifest_sha256':hashlib.sha256(manifest.encode()).hexdigest(),'timeline':events,'paper_comparison_presets':paper_steps,'demo_html_sha256':sha(args.demo),'live_io_records':io_records,'rendered_frames':history,'full_decode_passed':True,'browser_errors':errors,'transcode_command':command}
    args.output.with_suffix('.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(rec/'recording.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    server.shutdown();server.server_close();thread.join(timeout=5)
    print(json.dumps({'video':str(args.output),'seconds':duration,'record':str(rec)},ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--demo',type=Path,default=ROOT/'docs/demo_interactive.html');p.add_argument('--output',type=Path,default=ROOT/'docs/media/demo_course_roi.mp4');a=p.parse_args();a.demo=a.demo.resolve();a.output=a.output.resolve();asyncio.run(record(a))
if __name__=='__main__':main()
