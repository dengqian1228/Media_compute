import asyncio,json,hashlib,zipfile
from pathlib import Path
from datetime import datetime,timezone
import pymupdf
from pptx import Presentation
from playwright.async_api import async_playwright
ROOT=Path('/mnt/d/Myfiles/Mycode/2026/媒体计算/Big/Media_compute')
async def main():
 stem=ROOT/'docs/L0_图像结构平滑与边缘提取_全屏演示版'
 old=pymupdf.open(ROOT/'docs/L0_图像结构平滑与边缘提取_三段演示版.pdf');new=pymupdf.open(stem.with_suffix('.pdf'))
 assert len(new)==10
 for i in range(5):assert old[i].get_pixmap().samples==new[i].get_pixmap().samples
 # The result panels and all main text in slides 6-8 retain identical pixels.
 for i in range(5,8):
  clip=pymupdf.Rect(0,0,1152,612)
  assert old[i].get_pixmap(clip=clip).samples==new[i].get_pixmap(clip=clip).samples
  assert '成员 B' not in new[i].get_text() and '建议' not in new[i].get_text()
 assert not new[8].get_text().strip()
 assert new[9].get_text().strip()=='谢谢大家'
 ppt=Presentation(stem.with_suffix('.pptx'))
 movie=[s for s in ppt.slides[8].shapes if hasattr(s,'media_format')];assert len(movie)==1
 m=movie[0];assert (m.left,m.top,m.width,m.height)==(0,0,ppt.slide_width,ppt.slide_height)
 assert not any(s.has_text_frame and s.text.strip() for s in ppt.slides[8].shapes)
 assert [s.text for s in ppt.slides[9].shapes if s.has_text_frame and s.text.strip()]==['谢谢大家']
 video=ROOT/'docs/media/demo_three_sections_fullscreen.mp4';meta=json.loads(video.with_suffix('.json').read_text())
 with zipfile.ZipFile(stem.with_suffix('.pptx')) as z:
  vs=[n for n in z.namelist() if n.endswith('.mp4')];assert len(vs)==1
  assert hashlib.sha256(z.read(vs[0])).hexdigest()==meta['video_sha256']
  assert 'TargetMode="External"' not in z.read('ppt/slides/_rels/slide9.xml.rels').decode()
 async with async_playwright() as p:
  b=await p.chromium.launch(headless=True);page=await b.new_page()
  await page.goto((ROOT/'docs/media/demo_course_player.html').as_uri())
  await page.evaluate('(url)=>{const v=document.querySelector("video");v.src=url;v.load()}',video.as_uri())
  await page.wait_for_function('document.querySelector("video").readyState>=2')
  details=await page.evaluate('()=>{const v=document.querySelector("video");return {width:v.videoWidth,height:v.videoHeight,duration:v.duration}}')
  assert details['width']==1920 and details['height']==1080 and abs(details['duration']-43.64)<.1,details
  await page.evaluate('document.querySelector("video").play()');await page.wait_for_function('document.querySelector("video").currentTime>1')
  await page.evaluate('document.querySelector("video").pause()')
  for t in [7,23,33.64,41.64]:
   await page.evaluate('(t)=>document.querySelector("video").currentTime=t',t)
   await page.wait_for_function('(t)=>{const v=document.querySelector("video");return !v.seeking && Math.abs(v.currentTime-t)<.1 && v.readyState>=2}',arg=t)
  await b.close()
 result={'checked_at':datetime.now(timezone.utc).isoformat(),'passed':True,'slides':10,'A_pages_1_to_5_pixel_identical':True,'pages_6_to_8_main_content_pixel_identical':True,'B_metadata_footers_removed':True,'slide9_full_slide_movie_no_text':True,'slide10_only_thanks':True,'embedded_mp4_sha256_matches':True,'browser_playback_and_four_seeks_passed':True,'video':details,'executor':'AI; not PowerPoint/WPS or member review'}
 (ROOT/'results/demo_video/fullscreen_deck_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
asyncio.run(main())
