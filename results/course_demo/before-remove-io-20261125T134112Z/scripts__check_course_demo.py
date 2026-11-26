"""Browser checks for the four-task course Demo (optional Playwright tools).

Uses actual file:// browsing and a temporary loopback DemoServer; no virtualenv.
Writes evidence into a unique results/course_demo/browser_checks directory.
"""
import asyncio
import hashlib
import json
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright
from l0_smoothing.workflow import _new_run_directory
from scripts.demo_server import DemoServer, DemoHandler

ROOT = Path(__file__).resolve().parents[1]


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def run():
    out = _new_run_directory(ROOT / 'results/course_demo/browser_checks', 'check')
    evidence = {'started_at': datetime.now(timezone.utc).isoformat(), 'executor': 'AI; not member or classroom review',
                'page_sha256': hashlib.sha256((ROOT / 'docs/demo_interactive.html').read_bytes()).hexdigest(),
                'visual_checks': [], 'io_runs': [], 'downloads': [], 'browser_errors': [], 'external_requests': [], 'passed': False}
    server = None
    browser = None
    page = None
    server_thread = None
    original_logging = DemoHandler.log_message
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            evidence['browser_version'] = browser.version
            context = await browser.new_context(viewport={'width': 1600, 'height': 1000}, accept_downloads=True)
            page = await context.new_page()
            page.on('pageerror', lambda e: evidence['browser_errors'].append(str(e)))
            page.on('request', lambda req: evidence['external_requests'].append(req.url) if req.url.startswith(('https://', 'http://')) and not req.url.startswith('http://127.0.0.1:') else None)
            await page.goto((ROOT / 'docs/demo_interactive.html').as_uri())

            async def ready():
                await page.wait_for_function('window.demoReady===true && !document.querySelector("#stage").classList.contains("loading")', timeout=60000)

            async def state():
                await ready()
                return await page.evaluate('window.currentFrame')

            await ready()
            assert await page.locator('#taskTabs button').count() == 4
            data = json.loads(await page.locator('#demo-data').text_content())
            evidence['frame_count'] = len(data['frames'])
            evidence['groups'] = [g['id'] for g in data['groups']]
            assert all('synthetic' not in c['id'] for c in data['cases'])
            tasks = [
                ('smooth', 'photo', ['photo_beach', 'photo_brick_window_gray', 'photo_sunflower'], ['lambda', 'kappa', 'iteration']),
                ('edge', 'photo', ['photo_beach', 'photo_brick_window_gray', 'photo_sunflower'], ['lambda', 'kappa', 'iteration', 'canny']),
                ('jpeg', 'jpeg', ['jpeg_openmoji_fox_q30', 'jpeg_openmoji_turtle_q30'], ['lambda', 'kappa', 'quality']),
                ('jpeg', 'paper', ['paper_9', 'paper_20'], ['lambda', 'kappa']),
            ]
            for task, mode, sources, axes in tasks:
                await page.click('#task-' + task)
                await ready()
                if task == 'jpeg':
                    await page.select_option('#jpegKind', mode)
                    await ready()
                for source in sources:
                    await page.select_option('#sourceSelect', source)
                    await ready()
                    for axis in axes:
                        await page.select_option('#sweep', axis)
                        await ready()
                        for view in ['full', 'roi']:
                            before_view = await state()
                            await page.click('#' + view)
                            await ready()
                            after_view = await state()
                            assert before_view['id'] == after_view['id'] and before_view['canny_low'] == after_view['canny_low'], 'view switch changed parameters'
                            maximum = int(await page.locator('#parameter').get_attribute('max'))
                            for index in [0, maximum // 2, maximum]:
                                await page.locator('#parameter').fill(str(index))
                                f = await state()
                                expected = await page.evaluate('selected().f.id')
                                assert f['id'] == expected and f['task'] == task and f['axis'] == axis and f['view'] == view, f
                                assert f['case'] == source if axis != 'quality' else f['case'].startswith(source.rsplit('_q', 1)[0] + '_q')
                                if axis == 'lambda':
                                    assert f['kappa'] == 2
                                    if mode == 'jpeg': assert f['quality'] == 30
                                elif axis == 'kappa':
                                    assert f['lambda'] == (.02 if mode == 'photo' else .008)
                                    if mode == 'jpeg': assert f['quality'] == 30
                                elif axis == 'quality': assert f['lambda'] == .008 and f['kappa'] == 2
                                elif axis == 'iteration': assert f['lambda'] == .02 and f['kappa'] == 2 and f['iteration'] == index + 1
                                elif axis == 'canny': assert f['lambda'] == .02 and f['kappa'] == 2 and f['canny_low'] == 20 + index * 10
                                image_check = await page.evaluate('''()=>{const actual=[...document.querySelectorAll('#grid img')]; const wanted=parts(selected()).map(([_,p])=>new URL(p[view],document.baseURI).href); return actual.every((im,i)=>im.complete&&im.naturalWidth>0&&im.src===wanted[i]) && actual.length===wanted.length;}''')
                                assert image_check, f
                                assert await page.locator('#chart path').count() >= 2
                                evidence['visual_checks'].append(f)
                        await page.screenshot(path=str(out / f'{task}_{source}_{axis}.png'))
                print('checked visual task', task, mode, flush=True)
            # PSNR/SSIM plot selector and true deterioration marker.
            await page.click('#task-jpeg'); await ready()
            await page.select_option('#jpegKind', 'jpeg'); await ready()
            await page.select_option('#sourceSelect', 'jpeg_openmoji_turtle_q30'); await ready()
            await page.select_option('#sweep', 'lambda'); await ready()
            await page.click('#full'); await ready()
            await page.locator('#parameter').fill(await page.locator('#parameter').get_attribute('max')); await ready()
            assert '指标下降' in await page.locator('#metrics').inner_text()
            before_svg = await page.locator('#chart').inner_html()
            await page.select_option('#chartMetric', 'ssim')
            assert before_svg != await page.locator('#chart').inner_html()
            evidence['negative_case_and_ssim_chart'] = True
            # Actual chart click selects another result.
            before = await state()
            box = await page.locator('#chart').bounding_box()
            await page.mouse.click(box['x'] + box['width'] * .45, box['y'] + box['height'] * .5)
            after = await state()
            assert before['id'] != after['id']
            evidence['chart_click_changes_frame'] = {'before': before, 'after': after}
            # Comparison wipe and cached autoplay.
            await page.click('#task-smooth'); await ready()
            await page.click('#compare'); await ready()
            assert await page.locator('#wipeWrap').is_visible()
            for position in [23, 77]:
                await page.locator('#wipe').fill(str(position))
                assert await page.locator('#wipeLine').evaluate('(e)=>e.style.left') == f'{position}%'
                assert f'{position}%' in await page.locator('#wipeAfter').evaluate('(e)=>e.style.clipPath')
            await page.screenshot(path=str(out / 'smooth_wipe.png'))
            await page.click('#compare'); await ready()
            before = await state(); await page.click('#play')
            await page.wait_for_timeout(650)
            await page.click('#play'); after = await state()
            assert before['id'] != after['id'] and before['kappa'] == after['kappa']
            evidence['autoplay_keeps_fixed_parameter'] = True
            # Offline I/O must not pretend to execute Python.
            await page.click('#task-io')
            assert await page.locator('#run').is_disabled() and await page.locator('#replay').is_disabled()
            assert 'python3 -m scripts.demo_server' in await page.locator('#ioLiveInfo').inner_text()
            await page.locator('#ioLayout details summary').click()
            for index in ['0', '1']:
                await page.select_option('#ioExample', index); await page.click('#showExample')
                assert '非本次运行' in await page.locator('#ioMessage').inner_text()
                await page.wait_for_function('document.querySelector("#ioOutput").complete && document.querySelector("#ioOutput").naturalWidth>0')
            await page.screenshot(path=str(out / 'offline_io_evidence.png'))
            evidence['offline_io_explicit_archive_and_disabled_compute'] = True
            assert not evidence['external_requests']
            # Start a loopback server with an OS-selected free port.
            log_file = (out / 'server.log').open('w', encoding='utf-8')
            def log(handler, fmt, *args):
                log_file.write(fmt % args + '\n'); log_file.flush()
            DemoHandler.log_message = log
            server = DemoServer(0)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True); server_thread.start()
            url = f'http://127.0.0.1:{server.server_address[1]}/docs/demo_interactive.html'
            await page.goto(url); await ready(); await page.click('#task-io')
            await page.wait_for_function('!document.querySelector("#run").disabled')
            async def execute_and_replay(label, mode):
                await page.click('#run')
                await page.wait_for_function('window.ioResult && !document.querySelector("#run").disabled', timeout=60000)
                d = await page.evaluate('window.ioResult')
                assert d['ok'] and d['record']['input']['mode'] == mode
                assert (ROOT / d['record_path']).is_file()
                await page.wait_for_function('document.querySelector("#ioOutput").complete && document.querySelector("#ioOutput").naturalWidth>0')
                async with page.expect_download() as info:
                    await page.locator('#ioFiles a').filter(has_text='下载显示PNG').click()
                download = await info.value
                destination = out / (label + '_download.png'); await download.save_as(destination)
                expected = ROOT / d['files']['display'].lstrip('/')
                assert hashlib.sha256(destination.read_bytes()).digest() == hashlib.sha256(expected.read_bytes()).digest()
                evidence['downloads'].append({'label': label, 'file': str(destination.relative_to(ROOT)), 'same_bytes_as_actual_output': True})
                await page.click('#replay')
                await page.wait_for_function('window.ioReplay && !document.querySelector("#replay").disabled', timeout=60000)
                r = await page.evaluate('window.ioReplay')
                assert r['passed'] and r['comparison']['different_pixel_count'] == 0 and r['comparison']['max_float_abs_error'] <= 1e-12
                evidence['io_runs'].append({'label': label, 'run': d, 'replay': r})
                await page.screenshot(path=str(out / (label + '_io.png')))
            await page.select_option('#ioSample', 'beach')
            await execute_and_replay('live_rgb_sample', 'RGB')
            await page.select_option('#ioSample', 'brick_window_gray')
            await execute_and_replay('live_gray_sample', 'L')
            await page.locator('#ioFile').set_input_files(str(ROOT / 'data/structure_smoothing/inputs/sunflower.png'))
            await page.wait_for_function('document.querySelector("#ioInputTitle").textContent.includes("sunflower.png")')
            await execute_and_replay('live_rgb_upload', 'RGB')
            assert not evidence['browser_errors'], evidence['browser_errors']
            assert not evidence['external_requests'], evidence['external_requests']
            evidence['passed'] = True
            evidence['finished_at'] = datetime.now(timezone.utc).isoformat()
            save(out / 'checks.json', evidence)
            print(json.dumps({'passed': True, 'visual_checks': len(evidence['visual_checks']), 'live_runs_and_replays': len(evidence['io_runs']), 'evidence': str(out)}, ensure_ascii=False), flush=True)
            await context.close(); await browser.close(); browser = None
            log_file.close()
    except BaseException as exc:
        evidence['error'] = repr(exc); evidence['traceback'] = traceback.format_exc()
        save(out / 'checks.json', evidence)
        if page:
            try: await page.screenshot(path=str(out / 'failure.png'))
            except Exception: pass
        print('FAILED; evidence:', out, flush=True)
        raise
    finally:
        if server:
            server.shutdown(); server.server_close()
        if server_thread: server_thread.join(timeout=3)
        DemoHandler.log_message = original_logging


if __name__ == '__main__':
    asyncio.run(run())
