"""Record actual mouse drags through offline, one-factor L0 parameter sweeps."""
import argparse
import asyncio
import hashlib
import json
import re
import shutil
import subprocess
import time
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
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True);version=browser.version
        context=await browser.new_context(viewport={'width':1600,'height':900},record_video_size={'width':1600,'height':900},record_video_dir=str(rec/'raw'),locale='zh-CN')
        page=await context.new_page();video=page.video;page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(args.demo.as_uri());await page.wait_for_function('window.demoReady===true',timeout=60000)
        manifest=await page.locator('#demo-data').text_content()
        await page.evaluate('''()=>{window.recordRenderedFrames=[];document.querySelector('.badge').textContent='预录 · 本组算法预计算';let cursor=document.createElement('div');cursor.id='record-cursor';cursor.style='position:fixed;width:22px;height:22px;border:3px solid #ee9d28;border-radius:50%;pointer-events:none;z-index:9999;transform:translate(-50%,-50%);';document.body.append(cursor);document.addEventListener('mousemove',e=>{cursor.style.left=e.clientX+'px';cursor.style.top=e.clientY+'px';});}''')
        async def ready():await page.wait_for_function('window.demoReady===true && !document.querySelector("#stage").classList.contains("loading")',timeout=60000)
        async def mark(label,hold=0):
            state=await page.evaluate('window.currentFrame');events.append({'seconds':time.perf_counter()-start,'label':label,'frame':state});print(label,state,flush=True)
            if hold:await asyncio.sleep(hold)
        async def choose(mode,source,axis='lambda',view='full'):
            await page.select_option('#mode',mode);await ready()
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
            await mark(label+'：终点',.7)
            await page.screenshot(path=str(rec/(label+'.png')))
        await mark('离线参数交互演示',2)
        await choose('photo','photo_beach','lambda','full');await drag('01_照片固定kappa拖动lambda',7)
        await choose('photo','photo_beach','kappa','full');await drag('02_照片固定lambda拖动kappa',5)
        await choose('photo','photo_brick_window_gray','lambda','roi');await drag('03_砖墙局部与Canny',5)
        await choose('paper','paper_20','lambda','roi');await drag('04_论文蜗牛平滑强度',6)
        await choose('paper','paper_9','lambda','full');await drag('05_论文西瓜平滑强度',5)
        await choose('paper','paper_20','kappa','roi');await drag('06_论文蜗牛固定lambda拖动kappa',5)
        await mark('演示结束',2)
        history=await page.evaluate('window.recordRenderedFrames');await context.close();raw=Path(await video.path());await browser.close()
    if errors:raise RuntimeError(errors)
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();command=[ffmpeg,'-y','-i',str(raw),'-c:v','libx264','-crf','20','-preset','medium','-pix_fmt','yuv420p','-r','25','-movflags','+faststart','-an',str(args.output)]
    r=subprocess.run(command,capture_output=True,text=True,check=True);(rec/'ffmpeg.log').write_text(r.stderr)
    subprocess.run([ffmpeg,'-v','error','-i',str(args.output),'-f','null','-'],capture_output=True,check=True)
    probe=subprocess.run([ffmpeg,'-i',str(args.output)],capture_output=True,text=True).stderr
    m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe);duration=int(m[1])*3600+int(m[2])*60+float(m[3]);assert duration<75,duration
    poster=args.output.with_suffix('.png');shutil.copy2(rec/'01_照片固定kappa拖动lambda.png',poster)
    payload={'created_at':datetime.now(timezone.utc).isoformat(),'demo_kind':'precomputed_parameter_sweeps','source_scope':'real_photos_and_paper_website_only','duration_seconds':duration,'width':1600,'height':900,'fps':25,'codec':'H.264','audio':False,'speed_factor':1,'recording':'actual Chromium mouse drags and actual cached results; no online core execution or image interpolation','browser_version':version,'video_sha256':sha(args.output),'poster_sha256':sha(poster),'output_video':str(args.output.relative_to(ROOT)),'poster':str(poster.relative_to(ROOT)),'raw_video':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw),'demo_page':str(args.demo.relative_to(ROOT)),'demo_manifest_sha256':hashlib.sha256(manifest.encode()).hexdigest(),'timeline':events,'rendered_frames':history,'full_decode_passed':True,'browser_errors':errors,'transcode_command':command}
    args.output.with_suffix('.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(rec/'recording.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'video':str(args.output),'seconds':duration,'record':str(rec)},ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--demo',type=Path,default=ROOT/'docs/demo_interactive.html');p.add_argument('--output',type=Path,default=ROOT/'docs/media/demo_dynamic_real_sources.mp4');a=p.parse_args();a.demo=a.demo.resolve();a.output=a.output.resolve();asyncio.run(record(a))
if __name__=='__main__':main()
