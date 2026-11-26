"""Record the requested three sections using full images and consistent ROIs."""
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
        context=await browser.new_context(viewport={'width':1600,'height':1080},record_video_size={'width':1600,'height':1080},record_video_dir=str(rec/'raw'),locale='zh-CN')
        page=await context.new_page();video=page.video;page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(args.demo.as_uri());await page.wait_for_function('window.demoReady===true',timeout=60000)
        manifest=await page.locator('#demo-data').text_content()
        await page.evaluate('''()=>{window.recordRenderedFrames=[];document.querySelector('.badge').textContent='预录 · 本组真实预计算结果';let cursor=document.createElement('div');cursor.id='record-cursor';cursor.style='position:fixed;width:22px;height:22px;border:3px solid #ee9d28;border-radius:50%;pointer-events:none;z-index:9999;transform:translate(-50%,-50%);';document.body.append(cursor);document.addEventListener('mousemove',e=>{cursor.style.left=e.clientX+'px';cursor.style.top=e.clientY+'px';});}''')
        async def ready():await page.wait_for_function('window.demoReady===true && !document.querySelector("#stage").classList.contains("loading")',timeout=60000)
        async def mark(label,hold=0):
            state=await page.evaluate('window.currentFrame');events.append({'seconds':time.perf_counter()-start,'label':label,'frame':state});print(label,state,flush=True)
            if hold:await asyncio.sleep(hold)
        async def choose(task,source,axis='lambda',view='full',kind='jpeg'):
            # Configure the next view before navigation, avoiding a full-image
            # flash when entering the edge/ROI sections.
            await page.evaluate('(v)=>{view=v;document.querySelector("#full").classList.toggle("active",v==="full");document.querySelector("#roi").classList.toggle("active",v==="roi");}',view)
            if task=='jpeg':
                # Set paper selection before entering, avoiding any public-artwork flash.
                await page.locator('#jpegKind').evaluate('(el)=>el.value="paper"')
            await page.click('#task-'+task);await ready()
            if task=='jpeg':
                await page.select_option('#jpegKind',kind);await ready()
            await page.select_option('#sourceSelect',source);await ready()
            await page.select_option('#sweep',axis);await ready()
            await page.click('#'+view);await ready()
        sweeps=[]
        async def drag(label,seconds,section):
            await ready()
            expected=await page.evaluate("entries().map(e=>({id:e.f.id,value:value(e)}))")
            box=await page.locator('#parameter').bounding_box()
            x0=box['x']+8;x1=box['x']+box['width']-8;y=box['y']+box['height']/2
            await page.mouse.move(x0,y);await page.mouse.down()
            visited=[]
            await mark(label+'：起点')
            for i,item in enumerate(expected):
                await page.mouse.move(x0+(x1-x0)*i/(len(expected)-1),y)
                await page.wait_for_function('(n)=>Number(document.querySelector("#parameter").value)===n && !document.querySelector("#stage").classList.contains("loading")',arg=i)
                state=await page.evaluate('window.currentFrame')
                assert state['id']==item['id'],(label,i,state,item)
                assert state['view']==('full' if section==1 else 'roi')
                assert state['case'].startswith('paper_') if section==3 else state['case'].startswith('photo_')
                assert await page.locator('#grid img').evaluate_all('(ims)=>ims.every(im=>im.complete&&im.naturalWidth>0)')
                visited.append({'index':i,'value':item['value'],'frame':state})
                await asyncio.sleep(seconds/len(expected))
                if section==3 and item['value']==.008:await asyncio.sleep(.8)
            await page.mouse.up();await mark(label+'：终点',.7)
            await page.screenshot(path=str(rec/(label+'.png')))
            sweeps.append({'section':section,'label':label,'expected_points':len(expected),'visited':visited})
        await mark('01 结构平滑 · 全图',1)
        await choose('smooth','photo_beach','lambda','full');await drag('01_结构平滑lambda全图',5.5,1)
        await choose('smooth','photo_beach','kappa','full');await drag('02_结构平滑kappa全图',3,1)
        await choose('smooth','photo_beach','iteration','full');await drag('03_实际迭代全图',3,1)
        await choose('edge','photo_brick_window_gray','lambda','roi');await drag('04_边缘提取lambda同局部',5.5,2)
        await choose('edge','photo_brick_window_gray','canny','roi');await drag('05_Canny同参阈值同局部',2.5,2)
        await choose('jpeg','paper_9','lambda','roi','paper');await drag('06_论文西瓜同局部连续参数',6,3)
        await choose('jpeg','paper_20','lambda','roi','paper');await drag('07_论文蜗牛同局部连续参数',6,3)
        await mark('演示结束',1)
        history=await page.evaluate('window.recordRenderedFrames');await context.close();raw=Path(await video.path());await browser.close()
    if errors:raise RuntimeError(errors)
    assert all(f['view']==('full' if f['task']=='smooth' else 'roi') for f in history)
    assert all(f['case'].startswith('paper_') for f in history if f['task']=='jpeg')
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();command=[ffmpeg,'-y','-i',str(raw),'-c:v','libx264','-crf','20','-preset','medium','-pix_fmt','yuv420p','-r','25','-movflags','+faststart','-an',str(args.output)]
    r=subprocess.run(command,capture_output=True,text=True,check=True);(rec/'ffmpeg.log').write_text(r.stderr)
    subprocess.run([ffmpeg,'-v','error','-i',str(args.output),'-f','null','-'],capture_output=True,check=True)
    probe=subprocess.run([ffmpeg,'-i',str(args.output)],capture_output=True,text=True).stderr
    m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe);duration=int(m[1])*3600+int(m[2])*60+float(m[3]);assert duration<75,duration
    poster=args.output.with_suffix('.png');shutil.copy2(rec/'01_结构平滑lambda全图.png',poster)
    payload={'created_at':datetime.now(timezone.utc).isoformat(),'demo_kind':'three_sections','source_scope':'real_photos_and_paper_website_only','duration_seconds':duration,'width':1600,'height':1080,'fps':25,'codec':'H.264','audio':False,'speed_factor':1,'recording':'actual Chromium mouse drags across every sampled point; full-image smoothing, same-ROI edges, same-ROI paper JPEG; precomputed genuine outputs, no interpolation','browser_version':version,'video_sha256':sha(args.output),'poster_sha256':sha(poster),'output_video':str(args.output.relative_to(ROOT)),'poster':str(poster.relative_to(ROOT)),'raw_video':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw),'demo_page':str(args.demo.relative_to(ROOT)),'demo_manifest_sha256':hashlib.sha256(manifest.encode()).hexdigest(),'timeline':events,'sweeps':sweeps,'demo_html_sha256':sha(args.demo),'rendered_frames':history,'full_decode_passed':True,'browser_errors':errors,'transcode_command':command}
    args.output.with_suffix('.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(rec/'recording.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'video':str(args.output),'seconds':duration,'record':str(rec)},ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--demo',type=Path,default=ROOT/'docs/demo_interactive.html');p.add_argument('--output',type=Path,default=ROOT/'docs/media/demo_three_sections_v2.mp4');a=p.parse_args();a.demo=a.demo.resolve();a.output=a.output.resolve();asyncio.run(record(a))
if __name__=='__main__':main()
