import asyncio,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from playwright.async_api import async_playwright
from l0_smoothing.workflow import _new_run_directory
ROOT=Path.cwd();out=_new_run_directory(ROOT/'results/course_demo/browser_checks','view-check')
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(headless=True);page=await b.new_page(viewport={'width':1600,'height':1000})
  await page.goto((ROOT/'docs/demo_interactive.html').as_uri())
  async def ready():await page.wait_for_function('window.demoReady===true && !document.querySelector("#stage").classList.contains("loading")')
  await ready();checks=[]
  for task,axis in [('smooth','lambda'),('smooth','kappa'),('smooth','iteration'),('edge','canny'),('jpeg','quality')]:
   await page.click('#task-'+task);await ready()
   await page.select_option('#sweep',axis);await ready()
   await page.locator('#parameter').fill(await page.locator('#parameter').get_attribute('max'));await ready()
   before=await page.evaluate('window.currentFrame')
   for view in ['roi','full']:
    await page.click('#'+view);await ready();after=await page.evaluate('window.currentFrame')
    assert before['id']==after['id'] and before['lambda']==after['lambda'] and before['kappa']==after['kappa'] and before['quality']==after['quality'] and before['canny_low']==after['canny_low']
    checks.append({'before':before,'after':after})
  await page.screenshot(path=str(out/'jpeg_quality_full.png'))
  assert await page.locator('#chart').evaluate('(e)=>e.getBoundingClientRect().bottom<=window.innerHeight')
  await page.click('#task-io');assert await page.evaluate('window.currentTask')=='io'
  evidence={'checked_at':datetime.now(timezone.utc).isoformat(),'page_sha256':hashlib.sha256((ROOT/'docs/demo_interactive.html').read_bytes()).hexdigest(),'passed':True,'checks':checks,'chart_within_1000px_viewport':True,'current_task_io':True}
  (out/'checks.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n');print(out)
  await b.close()
asyncio.run(main())
