import asyncio,json,threading,traceback
from pathlib import Path
from datetime import datetime,timezone
from playwright.async_api import async_playwright
from scripts.demo_server import DemoServer,DemoHandler
from l0_smoothing.workflow import _new_run_directory
ROOT=Path.cwd();out=_new_run_directory(ROOT/'results/course_demo/browser_checks','io-error-check')
async def main():
 server=DemoServer(0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 original=DemoHandler.log_message;DemoHandler.log_message=lambda *args:None
 evidence={'started_at':datetime.now(timezone.utc).isoformat(),'executor':'AI browser check','passed':False,'checks':[]};page=None
 try:
  async with async_playwright() as p:
   browser=await p.chromium.launch(headless=True);page=await browser.new_page(viewport={'width':1600,'height':1000})
   errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto(f'http://127.0.0.1:{server.server_address[1]}/docs/demo_interactive.html');await page.click('#task-io')
   await page.wait_for_function('!document.querySelector("#run").disabled')
   await page.locator('#ioFile').set_input_files({'name':'too-large.png','mimeType':'image/png','buffer':b'x'*(4*1024*1024+1)})
   assert await page.locator('#run').is_disabled() and await page.locator('#replay').is_disabled()
   assert await page.locator('#ioFiles a').count()==0
   evidence['checks'].append('oversize file disables run/replay, clears prior output links')
   await page.select_option('#ioSample','beach');assert await page.locator('#run').is_enabled()
   await page.locator('#ioFile').set_input_files({'name':'invalid.png','mimeType':'image/png','buffer':b'not a PNG'})
   await page.wait_for_function('!document.querySelector("#run").disabled')
   await page.click('#run');await page.wait_for_function('document.querySelector("#ioMessage").textContent.startsWith("运行失败")')
   assert await page.evaluate('window.ioResult===null')
   assert await page.locator('#ioOutput').is_hidden() and await page.locator('#ioFiles a').count()==0
   assert await page.locator('#replay').is_disabled()
   evidence['checks'].append('malformed uploaded PNG rejected by real server; no stale output/result/replay')
   await page.select_option('#ioSample','beach')
   await page.locator('#ioLambda').fill('0')
   await page.click('#run');await page.wait_for_function('document.querySelector("#ioMessage").textContent.startsWith("运行失败")')
   assert await page.evaluate('window.ioResult===null') and await page.locator('#ioOutput').is_hidden()
   evidence['checks'].append('invalid lambda rejected; failure shown with no prior result')
   await page.locator('#ioLambda').fill('0.001');await page.locator('#ioKappa').fill('1.5')
   locked=await page.evaluate('''()=>{document.querySelector('#run').click();return ['run','replay','ioSample','ioFile','ioLambda','ioKappa','ioExample','showExample'].every(id=>document.getElementById(id).disabled);}''')
   assert locked
   await page.wait_for_function('window.ioResult && !document.querySelector("#run").disabled',timeout=60000)
   d=await page.evaluate('window.ioResult');assert d['record']['parameters']['lambda']==.001 and d['record']['parameters']['kappa']==1.5
   evidence['checks'].append('all I/O selectors and actions disabled while request pending; true run completes with submitted params')
   evidence['run']=d
   await page.screenshot(path=str(out/'recovered_actual_run.png'))
   assert not errors; evidence['browser_errors']=errors;evidence['passed']=True
   await browser.close()
 except Exception as e:
  evidence['error']=repr(e);evidence['traceback']=traceback.format_exc();raise
 finally:
  (out/'checks.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
  server.shutdown();server.server_close();thread.join();DemoHandler.log_message=original
  print(out)
asyncio.run(main())
