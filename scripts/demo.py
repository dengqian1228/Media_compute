"""Run the group's L0 implementation and create an offline, self-contained result page.

The HTML displays saved results. To change parameters and compute again, rerun
this CLI. No server, browser package or network access is required.
"""
import argparse
import base64
import hashlib
import html
import io
import json
import math
import shlex
import shutil
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from PIL import Image, features

from l0_smoothing.metrics import METRIC_SPEC, image_metrics
from l0_smoothing.workflow import (
    _environment, _new_run_directory, read_8bit_image, replay_record, run_and_save,
)
from scripts.jpeg_artifacts import SPECS, DATA, digest, load_json, write_json

ROOT = Path(__file__).resolve().parents[1]
CANNY = {'low': 60, 'high': 120, 'aperture': 3, 'l2': True}


def edges(pixels):
    gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY) if pixels.ndim == 3 else pixels
    return cv2.Canny(gray, 60, 120, apertureSize=3, L2gradient=True)


def data_uri(path):
    with Image.open(path) as im:
        stream = io.BytesIO()
        im.save(stream, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode('ascii')


def fig(path, title):
    return '<figure><figcaption>' + html.escape(title) + '</figcaption><img alt="' + html.escape(title, quote=True) + '" src="' + data_uri(path) + '"></figure>'


def crops(folder, paths, roi):
    result = []
    for i, path in enumerate(paths):
        target = folder / f'crop-{i}.png'
        with Image.open(path) as im:
            im.crop(roi).resize((384, 384), Image.Resampling.NEAREST).save(target)
        result.append(target)
    return result


def metrics(clean, candidate, roi):
    x0, y0, x1, y1 = roi
    return {'full': image_metrics(clean, candidate),
            'roi': image_metrics(clean[y0:y1, x0:x1], candidate[y0:y1, x0:x1])}


def smooth_demo(out, args):
    folder = out / 'smooth'
    folder.mkdir()
    source = Path(args.input).resolve()
    record_path = run_and_save(source, folder, lambda_=args.smooth_lambda,
                               kappa=args.kappa, beta_max=args.beta_max)
    record = load_json(record_path)
    saved_input = record_path.parent / record['input']['copy']
    saved_output = record_path.parent / record['output']['display']
    _, original, _ = read_8bit_image(saved_input)
    _, restored, _ = read_8bit_image(saved_output)
    height, width = original.shape[:2]
    roi = [int(width*.25), int(height*.25), max(int(width*.65), int(width*.25)+1), max(int(height*.65), int(height*.25)+1)]
    source_edges = folder / 'input_edges.png'
    result_edges = folder / 'output_edges.png'
    Image.fromarray(edges(original)).save(source_edges)
    Image.fromarray(edges(restored)).save(result_edges)
    zoom = crops(folder, [saved_input, saved_output, source_edges, result_edges], roi)
    custom = source != (ROOT/'data/structure_smoothing/inputs/beach.png').resolve()
    source_note = ('自选输入；来源和使用许可由运行者登记。' if custom else
                   'beach：论文官网 Input Images；归档来源见 data/structure_smoothing/README.md，官网未注明图片许可。')
    section = '<section id="smooth"><h2>① 结构平滑</h2><p>' + html.escape(source_note) + '</p>'
    section += f'<p>λ={args.smooth_lambda:g}，κ={args.kappa:g}，βmax={args.beta_max:g}；{record["iterations"]} 轮，核心耗时 {record["elapsed_seconds"]:.3f} 秒。</p>'
    section += '<div class="grid">'+fig(saved_input, '原图')+fig(saved_output, '本组 L0 平滑结果')+'</div>'
    section += '<h3>同一局部</h3><div class="grid">'+fig(zoom[0], '原图局部')+fig(zoom[1], '平滑局部')+'</div>'
    section += '<h2>② 相同参数 Canny 边缘对照</h2><p>两图均采用低阈值60、高阈值120、孔径3、L2梯度。RGB先统一转灰度，无额外模糊。少线不能单独证明效果更好。</p>'
    section += '<div class="grid">'+fig(source_edges, '原图 Canny')+fig(result_edges, '平滑后 Canny')+'</div>'
    section += '<div class="grid">'+fig(zoom[2], '原图局部 Canny')+fig(zoom[3], '平滑局部 Canny')+'</div></section>'
    return {'record': record_path.relative_to(out).as_posix(), 'roi_xyxy': roi,
            'canny': CANNY, 'input_edges': source_edges.relative_to(out).as_posix(),
            'output_edges': result_edges.relative_to(out).as_posix(), 'source_note': source_note}, section


def jpeg_demo(out, args):
    folder = out / 'jpeg'
    folder.mkdir()
    manifest = load_json(DATA/'manifest.json')
    source = DATA / manifest['images'][args.clipart]['file']
    if digest(source) != manifest['images'][args.clipart]['file_sha256']:
        raise ValueError('clean Clip-art source hash differs from manifest')
    clean_path = folder / 'clean.png'
    shutil.copyfile(source, clean_path)
    compressed_path = folder / 'compressed.jpg'
    _, clean, mode = read_8bit_image(clean_path)
    settings = {'quality': args.quality, 'optimize': False, 'progressive': False}
    if mode == 'RGB':
        settings['subsampling'] = 0
    with Image.open(clean_path) as im:
        im.save(compressed_path, format='JPEG', **settings)
    record_path = run_and_save(compressed_path, folder, lambda_=args.jpeg_lambda,
                               kappa=args.kappa, beta_max=args.beta_max)
    record = load_json(record_path)
    output_path = record_path.parent / record['output']['display']
    _, compressed, _ = read_8bit_image(compressed_path)
    _, restored, _ = read_8bit_image(output_path)
    roi = SPECS[args.clipart]['roi']
    scores = {'jpeg': metrics(clean, compressed, roi), 'restored': metrics(clean, restored, roi)}
    write_json(folder/'metrics.json', {'reference': 'clean.png', 'protocol': METRIC_SPEC, 'roi_xyxy': roi, **scores})
    zoom = crops(folder, [clean_path, compressed_path, output_path], roi)
    section = '<section id="jpeg"><h2>③ Clip-art JPEG 去伪影</h2><p>干净图由本项目程序确定性绘制，无外部素材；不是论文恢复图。以同一干净图为真值比较 JPEG 和恢复结果。</p>'
    section += f'<p>{args.clipart}，JPEG Q={args.quality}，λ={args.jpeg_lambda:g}，κ={args.kappa:g}，βmax={args.beta_max:g}；{record["iterations"]} 轮，核心耗时 {record["elapsed_seconds"]:.3f} 秒。</p>'
    section += '<div class="grid three">'+fig(clean_path, '干净真值')+fig(compressed_path, 'JPEG 输入')+fig(output_path, 'L0 恢复')+'</div>'
    section += '<h3>固定区域放大</h3><div class="grid three">'+fig(zoom[0], '干净局部')+fig(zoom[1], 'JPEG 局部')+fig(zoom[2], '恢复局部')+'</div>'
    section += '<table><thead><tr><th>候选图</th><th>全图 PSNR / dB</th><th>全图 SSIM</th><th>局部 PSNR / dB</th><th>局部 SSIM</th></tr></thead><tbody>'
    for key, name in [('jpeg','JPEG'), ('restored','L0恢复')]:
        score = scores[key]
        section += f'<tr><td>{name}</td><td>{score["full"]["psnr_db"]:.4f}</td><td>{score["full"]["ssim"]:.6f}</td><td>{score["roi"]["psnr_db"]:.4f}</td><td>{score["roi"]["ssim"]:.6f}</td></tr>'
    section += '</tbody></table><p>指标使用解码的8位像素。PSNR值域255；SSIM采用11×11高斯窗、σ=1.5、总体矩、舍弃边界5像素，RGB逐通道取均值。局部指标在同一裁剪区域重算。过大的λ可能同时抹掉伪影与真实细线。</p></section>'
    return {'record': record_path.relative_to(out).as_posix(), 'clipart': args.clipart,
            'clean': clean_path.relative_to(out).as_posix(), 'compressed': compressed_path.relative_to(out).as_posix(),
            'jpeg_settings': settings, 'libjpeg': features.version('jpg'), 'roi_xyxy': roi,
            'metrics': scores}, section


def run(args):
    started = perf_counter()
    out = _new_run_directory(Path(args.output_dir), 'demo')
    sections, records = [], {}
    if args.mode in ('all', 'smooth'):
        records['smooth'], section = smooth_demo(out, args)
        sections.append(section)
    if args.mode in ('all', 'jpeg'):
        records['jpeg'], section = jpeg_demo(out, args)
        sections.append(section)
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>L0 平滑 · 本地 Demo</title><style>
    *{box-sizing:border-box}body{font-family:system-ui,"Microsoft YaHei",sans-serif;color:#152431;background:#f4f6f5;margin:0;line-height:1.6}main{max-width:1280px;margin:auto;padding:32px}h1{font-size:34px}h2{font-size:26px;margin-top:36px}h3{font-size:20px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.three{grid-template-columns:repeat(3,minmax(0,1fr))}figure{margin:0;padding:12px;background:white;border-radius:8px}figcaption{font-weight:600;margin-bottom:8px}img{max-width:100%;display:block;margin:auto;max-height:540px;object-fit:contain}section{border-top:2px solid #cad8d1;margin-top:32px}table{border-collapse:collapse;width:100%;margin:20px 0;background:white}td,th{border:1px solid #cbd6cf;text-align:left;padding:10px}.note{background:#e4eee7;padding:14px}nav a{margin-right:18px;color:#185f43}code{overflow-wrap:anywhere} @media(max-width:650px){.grid,.three{grid-template-columns:1fr}main{padding:16px}}@media print{body{background:white}section{break-before:page}img{max-height:320px}}
    </style><main><h1>L0 梯度最小化 · 本地 Demo</h1><p>成员B：蒋天乐 2023010721 ｜ 本组L0核心 + 保存与复现</p><nav><a href="#smooth">结构平滑与边缘</a><a href="#jpeg">JPEG去伪影</a></nav><p class="note">此离线页展示CLI本次真实计算结果。调整参数后重新运行命令即可生成新页；本页不在浏览器中计算。检查由智能体执行，成员人工核验和课堂现场展示待本人完成。</p>'''
    page += ''.join(sections) + '<footer><p>生成命令：<code>' + html.escape(shlex.join([sys.executable, '-m', 'scripts.demo', *sys.argv[1:]])) + '</code></p></footer></main></html>'
    (out/'index.html').write_text(page, encoding='utf-8')
    inventory = {p.relative_to(out).as_posix(): digest(p) for p in sorted(out.rglob('*')) if p.is_file()}
    payload = {'created_at': datetime.now(timezone.utc).isoformat(), 'actor': '智能体执行；成员B 蒋天乐 2023010721',
        'command': [sys.executable, '-m', 'scripts.demo', *sys.argv[1:]], 'cwd': str(Path.cwd()),
        'environment': {**_environment(), 'opencv': cv2.__version__, 'libjpeg': features.version('jpg')},
        'mode': args.mode, 'records': records, 'artifact_sha256': inventory,
        'total_elapsed_seconds': perf_counter()-started, 'html': 'index.html'}
    write_json(out/'demo.json', payload)
    print(out/'index.html')
    print(out/'demo.json')
    return out


class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
    def handle_starttag(self, tag, attrs):
        if tag in ('img', 'script', 'link'):
            attrs = dict(attrs)
            if tag != 'img':
                if attrs.get('src') or attrs.get('href'):
                    raise ValueError('HTML depends on an external resource')
            else:
                uri = attrs['src']
                if not uri.startswith('data:image/png;base64,'):
                    raise ValueError('HTML image is not embedded')
                data = base64.b64decode(uri.split(',', 1)[1], validate=True)
                with Image.open(io.BytesIO(data)) as im:
                    im.verify()
                self.images.append(uri)


def check(directory):
    out = Path(directory).resolve()
    record = load_json(out/'demo.json')
    for relative, expected in record['artifact_sha256'].items():
        path = (out/relative).resolve()
        if not path.is_relative_to(out) or digest(path) != expected:
            raise ValueError(f'missing or changed demo artifact: {relative}')
    parser = ImageParser()
    parser.feed((out/'index.html').read_text(encoding='utf-8'))
    expected_count = (8 if 'smooth' in record['records'] else 0)+(6 if 'jpeg' in record['records'] else 0)
    if len(parser.images) != expected_count:
        raise ValueError('HTML image count differs from enabled demo sections')
    checks = _new_run_directory(out, 'checks')
    replay_results = []
    for kind, item in record['records'].items():
        if kind == 'smooth':
            run_record = load_json(out/item['record'])
            folder = (out/item['record']).parent
            for output, source in [('input_edges', folder/run_record['input']['copy']), ('output_edges', folder/run_record['output']['display'])]:
                _, pixels, _ = read_8bit_image(source)
                _, saved, _ = read_8bit_image(out/item[output])
                if not np.array_equal(saved, edges(pixels)):
                    raise ValueError('Canny differs from recorded parameters')
        else:
            _, clean, _ = read_8bit_image(out/item['clean'])
            _, jpeg, _ = read_8bit_image(out/item['compressed'])
            run_record = load_json(out/item['record'])
            _, restored, _ = read_8bit_image((out/item['record']).parent/run_record['output']['display'])
            actual = {'jpeg': metrics(clean, jpeg, item['roi_xyxy']), 'restored': metrics(clean, restored, item['roi_xyxy'])}
            for stage in actual:
                for region in actual[stage]:
                    for metric, value in actual[stage][region].items():
                        if not math.isclose(item['metrics'][stage][region][metric], value, rel_tol=0, abs_tol=1e-10):
                            raise ValueError('JPEG demo metric mismatch')
        replay, passed = replay_record(out/item['record'], checks)
        replay_results.append({'kind': kind, 'record': replay.relative_to(out).as_posix(),
                               'passed': passed, 'comparison': load_json(replay)['comparison']})
    result = {'created_at': datetime.now(timezone.utc).isoformat(), 'actor': '智能体执行验证',
              'command': [sys.executable, '-m', 'scripts.demo', *sys.argv[1:]],
              'artifact_count': len(record['artifact_sha256']), 'embedded_images': len(parser.images),
              'browser_visual_check': 'not performed; HTML resources parsed and decoded without browser',
              'replays': replay_results, 'passed': all(r['passed'] for r in replay_results)}
    write_json(checks/'checks.json', result)
    print(checks/'checks.json')
    if not result['passed']:
        raise ValueError('demo replay comparison failed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', nargs='?', choices=['run','check'], default='run')
    p.add_argument('directory', nargs='?', help='saved demo directory, required for check')
    p.add_argument('--mode', choices=['all','smooth','jpeg'], default='all')
    p.add_argument('--input', default=str(ROOT/'data/structure_smoothing/inputs/beach.png'), help='8-bit L/RGB input for smooth mode')
    p.add_argument('--clipart', choices=list(SPECS), default='house_rgb')
    p.add_argument('--quality', type=int, default=30, help='JPEG quality 1..95 (default 30)')
    p.add_argument('--lambda', dest='lambda_', type=float, help='lambda for a SINGLE mode; use stage-specific flags with all')
    p.add_argument('--smooth-lambda', type=float, default=.02, help='photo smoothing lambda (default .02)')
    p.add_argument('--jpeg-lambda', type=float, default=.008, help='JPEG restoration lambda (default .008)')
    p.add_argument('--kappa', type=float, default=2)
    p.add_argument('--beta-max', type=float, default=1e5)
    p.add_argument('--output-dir', type=Path, default=ROOT/'results/demo')
    args = p.parse_args()
    if args.action == 'check':
        if not args.directory:
            p.error('check requires a saved demo directory')
    else:
        if args.directory:
            p.error('directory positional argument is only valid for check')
        if args.lambda_ is not None:
            if args.mode == 'all':
                p.error('--lambda with all is ambiguous; use --smooth-lambda and --jpeg-lambda')
            if args.mode == 'smooth':
                args.smooth_lambda = args.lambda_
            else:
                args.jpeg_lambda = args.lambda_
        if not 1 <= args.quality <= 95:
            p.error('--quality must be in 1..95')
        for name, value in [('smooth-lambda',args.smooth_lambda), ('jpeg-lambda',args.jpeg_lambda), ('kappa',args.kappa), ('beta-max',args.beta_max)]:
            if not math.isfinite(value) or value <= 0:
                p.error(f'--{name} must be finite and positive')
        if args.kappa <= 1:
            p.error('--kappa must be greater than 1')
        active_lambdas = ([args.smooth_lambda, args.jpeg_lambda] if args.mode == 'all'
                          else [args.smooth_lambda] if args.mode == 'smooth' else [args.jpeg_lambda])
        if args.beta_max <= 2*max(active_lambdas):
            p.error('--beta-max must be greater than 2*lambda')
    try:
        check(args.directory) if args.action == 'check' else run(args)
    except (ValueError, OSError, KeyError) as exc:
        p.exit(2, f'demo error: {exc}\n')


if __name__ == '__main__':
    main()
