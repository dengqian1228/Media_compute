"""Controlled JPEG experiment from credited public OpenMoji SVG artwork.

Prepare once with optional CairoSVG installed; build/check need only project deps.
No third-party smoothing implementation is used.
"""
import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, JpegImagePlugin, features
from l0_smoothing import smooth_l0
from l0_smoothing.metrics import image_metrics, METRIC_SPEC
from l0_smoothing.workflow import _display_pixels, _environment, _new_run_directory

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/public_clipart'
REVISION = '5acb7f049c45c57a98449122d470de9f09bb6794'
REPOSITORY = 'https://github.com/hfg-gmuend/openmoji'
LICENSE_URL = 'https://creativecommons.org/licenses/by-sa/4.0/'
LAMBDAS = sorted(set([round(float(x), 6) for x in np.geomspace(.001, .08, 41)] + [.005, .008, .02, .04]))
KAPPAS = [round(1.5 + i * .05, 2) for i in range(21)]
QUALITIES = list(range(5, 96, 5))
SPECS = [
    {'id': 'openmoji_fox', 'title': 'OpenMoji 狐狸（彩色）', 'code': '1F98A', 'variant': 'color', 'mode': 'RGB', 'roi': [64, 64, 192, 192]},
    {'id': 'openmoji_turtle', 'title': 'OpenMoji 乌龟（线稿）', 'code': '1F422', 'variant': 'black', 'mode': 'L', 'roi': [80, 80, 208, 208]},
]


def now(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path, value): Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
def pixels(path):
    with Image.open(path) as image: return np.array(image)
def scores(reference, image, roi):
    x0, y0, x1, y1 = roi
    return {'full': image_metrics(reference, image), 'roi': image_metrics(reference[y0:y1, x0:x1], image[y0:y1, x0:x1])}
def pair(out, image, name, roi):
    full = out / 'assets' / (name + '.png')
    local = out / 'assets' / (name + '_roi.png')
    Image.fromarray(image).save(full)
    x0, y0, x1, y1 = roi
    Image.fromarray(image[y0:y1, x0:x1]).save(local)
    return {'full': full.relative_to(out).as_posix(), 'roi': local.relative_to(out).as_posix()}
def fetch(url, destination):
    request = urllib.request.Request(url, headers={'User-Agent': 'MediaCompute-course-source-audit'})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read()
        final = response.url
    destination.write_bytes(data)
    return {'url': url, 'final_url': final, 'retrieved_at': now(), 'file': destination.relative_to(SOURCE).as_posix(), 'sha256': sha(destination)}


def prepare():
    import cairosvg
    if (SOURCE / 'manifest.json').exists():
        raise ValueError('Source manifest already exists; original source archive is preserved.')
    (SOURCE / 'originals').mkdir(parents=True, exist_ok=True)
    (SOURCE / 'clean').mkdir(exist_ok=True)
    base = f'https://raw.githubusercontent.com/hfg-gmuend/openmoji/{REVISION}/'
    license_record = fetch(base + 'LICENSE.txt', SOURCE / 'LICENSE.txt')
    readme_record = fetch(base + 'README.md', SOURCE / 'upstream_README.md')
    metadata_record = fetch(base + 'data/openmoji.json', SOURCE / 'upstream_openmoji.json')
    metadata = load(SOURCE / 'upstream_openmoji.json')
    sources = []
    for spec in SPECS:
        item = dict(spec)
        path = f"{spec['variant']}/svg/{spec['code']}.svg"
        svg = SOURCE / 'originals' / (spec['id'] + '.svg')
        item['original'] = fetch(base + path, svg)
        entry = next(x for x in metadata if x['hexcode'] == spec['code'])
        item['upstream_metadata'] = entry
        item['author'] = entry.get('openmoji_author') or 'OpenMoji contributors / HfG Schwäbisch Gmünd'
        item['source_page'] = REPOSITORY + '/blob/' + REVISION + '/' + path
        item['license'] = 'CC BY-SA 4.0'
        item['license_url'] = LICENSE_URL
        png = cairosvg.svg2png(bytestring=svg.read_bytes(), output_width=256, output_height=256, background_color='#ffffff')
        with Image.open(io.BytesIO(png)) as image:
            clean = image.convert(spec['mode'])
            target = SOURCE / 'clean' / (spec['id'] + '.png')
            clean.save(target)
            item['clean'] = {'file': target.relative_to(SOURCE).as_posix(), 'sha256': sha(target), 'mode': clean.mode, 'size': list(clean.size)}
        item['preprocessing'] = ['Original OpenMoji SVG bytes unchanged', 'CairoSVG svg2png at 256x256 on opaque #ffffff, no JPEG stage', f"Pillow convert to 8-bit {spec['mode']}", 'Save lossless PNG as clean reference; no hand drawing, L0, sharpening or denoising']
        sources.append(item)
    manifest = {'created_at': now(), 'command': [sys.executable, '-m', 'scripts.public_jpeg_demo', *sys.argv[1:]], 'repository': REPOSITORY, 'revision': REVISION, 'license': license_record, 'upstream_readme': readme_record, 'upstream_metadata': metadata_record, 'environment': {**_environment(), 'cairosvg': cairosvg.__version__}, 'sources': sources, 'reference_definition': 'Rasterized external vector artwork before any JPEG compression; not paper author L0 outputs or group-drawn shapes.'}
    save(SOURCE / 'manifest.json', manifest)
    lines = ['# 公开 Clip-art 素材与处理说明\n\n这些图形来自 OpenMoji 官方仓库，是外部已公开作品，不是本组绘制或AI生成。用于有干净参考的受控 JPEG 压缩实验；不冒充论文原图。\n\n']
    for item in sources:
        lines.append(f"- **{item['title']}**：{item['author']}；[原作品]({item['source_page']})；[CC BY-SA 4.0]({LICENSE_URL})。\n")
    lines.append('\n原SVG、上游署名元数据与许可证完整归档。CairoSVG在白背景栅格化为256×256，狐狸保存RGB、乌龟线稿保存L；随后生成JPEG、L0恢复和展示裁剪。上述衍生图继续按CC BY-SA 4.0提供。精确版本、转换环境、时间、参数、摘要见manifest.json。干净参考定义为本组此次受控压缩之前的PNG，不是实拍真值。\n')
    (SOURCE / 'SOURCE_CREDITS.md').write_text(''.join(lines), encoding='utf-8')
    print(SOURCE / 'manifest.json', flush=True)


def build(output):
    started = time.perf_counter()
    source_manifest = load(SOURCE / 'manifest.json')
    out = _new_run_directory(output, 'public-jpeg')
    for folder in ['inputs', 'assets', 'source_archive']: (out / folder).mkdir()
    shutil.copy2(SOURCE / 'manifest.json', out / 'source_archive' / 'manifest.json')
    shutil.copy2(SOURCE / 'SOURCE_CREDITS.md', out / 'SOURCE_CREDITS.md')
    shutil.copy2(SOURCE / 'LICENSE.txt', out / 'source_archive' / 'LICENSE.txt')
    cases, frames, groups, sources, rows = [], [], [], [], []
    for source in source_manifest['sources']:
        clean_file = SOURCE / source['clean']['file']
        assert sha(clean_file) == source['clean']['sha256']
        assert sha(SOURCE / source['original']['file']) == source['original']['sha256']
        original_copy = out / 'source_archive' / Path(source['original']['file']).name
        shutil.copy2(SOURCE / source['original']['file'], original_copy)
        clean_copy = out / 'inputs' / clean_file.name
        shutil.copy2(clean_file, clean_copy)
        reference = pixels(clean_copy)
        roi = source['roi']
        sources.append({'source': clean_file.relative_to(ROOT).as_posix(), 'archived': clean_copy.relative_to(out).as_posix(), 'sha256': sha(clean_copy), 'source_page': source['source_page'], 'author': source['author'], 'license': source['license'], 'original_svg': original_copy.relative_to(out).as_posix(), 'group_source': source['id']})
        for quality in QUALITIES:
            case_id = f"jpeg_{source['id']}_q{quality}"
            jpeg = out / 'inputs' / (case_id + '.jpg')
            Image.fromarray(reference).save(jpeg, format='JPEG', quality=quality, subsampling=0, optimize=False, progressive=False)
            with Image.open(jpeg) as image:
                encoding = {'quality': quality, 'sampling': JpegImagePlugin.get_sampling(image), 'quantization': image.quantization, 'libjpeg': features.version('jpg'), 'optimize': False, 'progressive': False}
            degraded = pixels(jpeg)
            case = {'id': case_id, 'group_source': source['id'], 'mode': 'jpeg', 'title': source['title'], 'quality': quality, 'roi': roi, 'input': jpeg.relative_to(out).as_posix(), 'reference': clean_copy.relative_to(out).as_posix(), 'source_note': f"{source['author']} / OpenMoji / CC BY-SA 4.0；{source['source_page']}", 'reference_kind': 'clean_ground_truth', 'jpeg_encoding': encoding, 'baseline_metrics': scores(reference, degraded, roi)}
            case['shared'] = {'input': pair(out, degraded, case_id + '_input', roi), 'reference': pair(out, reference, case_id + '_reference', roi)}
            cases.append(case)
            settings = list(dict.fromkeys([(lam, 2.0) for lam in LAMBDAS] + [(.008, k) for k in KAPPAS])) if quality == 30 else [(.008, 2.0)]
            for lam, kappa in settings:
                result = smooth_l0(degraded.astype(np.float64) / 255, lambda_=lam, kappa=kappa, beta_max=1e5)
                display = _display_pixels(result.image)
                frame = {'id': len(frames), 'case': case_id, 'lambda': lam, 'kappa': kappa, 'beta_max': 1e5, 'iterations': result.iterations, 'elapsed_seconds': result.elapsed_seconds, 'output': pair(out, display, f'frame_{len(frames):03d}', roi), 'float64_shape': list(result.image.shape), 'float64_sha256': hashlib.sha256(result.image.tobytes()).hexdigest(), 'input_sha256': sha(jpeg), 'reused_from': None, 'metrics': scores(reference, display, roi)}
                frames.append(frame)
                row = {'case': case_id, 'source': source['id'], 'mode': source['mode'], 'quality': quality, 'lambda': lam, 'kappa': kappa, 'iterations': result.iterations, 'elapsed_seconds': result.elapsed_seconds}
                for region in ['full', 'roi']:
                    for metric in ['psnr_db', 'ssim']:
                        row[f'{region}_baseline_{metric}'] = case['baseline_metrics'][region][metric]
                        row[f'{region}_restored_{metric}'] = frame['metrics'][region][metric]
                        row[f'{region}_delta_{metric}'] = frame['metrics'][region][metric] - case['baseline_metrics'][region][metric]
                rows.append(row)
            print(source['id'], 'Q', quality, 'total', len(frames), flush=True)
        base_id = f"jpeg_{source['id']}_q30"
        group = {'id': base_id, 'mode': 'jpeg', 'title': source['title'], 'group_source': source['id'], 'sweeps': {}}
        group['sweeps']['lambda'] = [f['id'] for lam in LAMBDAS for f in frames if f['case'] == base_id and f['lambda'] == lam and f['kappa'] == 2]
        group['sweeps']['kappa'] = [f['id'] for k in KAPPAS for f in frames if f['case'] == base_id and f['lambda'] == .008 and f['kappa'] == k]
        group['sweeps']['quality'] = [f['id'] for q in QUALITIES for f in frames if f['case'] == f"jpeg_{source['id']}_q{q}" and f['lambda'] == .008 and f['kappa'] == 2]
        groups.append(group)
    with (out / 'metrics.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    negatives = {region: {metric: sum(r[f'{region}_delta_{metric}'] < 0 for r in rows) for metric in ['psnr_db', 'ssim']} for region in ['full', 'roi']}
    manifest = {'created_at': now(), 'command': [sys.executable, '-m', 'scripts.public_jpeg_demo', *sys.argv[1:]], 'cwd': str(Path.cwd()), 'environment': _environment(), 'core_sha256': sha(ROOT / 'l0_smoothing/core.py'), 'script_sha256': sha(Path(__file__)), 'source_manifest_sha256': sha(SOURCE / 'manifest.json'), 'metric_spec': METRIC_SPEC, 'lambdas': LAMBDAS, 'kappas': KAPPAS, 'qualities': QUALITIES, 'cases': cases, 'groups': groups, 'frames': frames, 'sources': sources, 'negative_metric_counts': negatives, 'frame_count': len(frames), 'build_seconds': time.perf_counter() - started, 'storage': 'Original external SVGs, clean PNGs, encoded JPEGs, lossless display PNGs, float64 shape and digest. Float arrays can be regenerated by the own core.', 'display': 'lambda at Q30/kappa2; kappa at Q30/lambda.008; quality at lambda.008/kappa2. Discrete computed frames; no image interpolation.', 'artifacts': {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*') if p.is_file()}}
    save(out / 'manifest.json', manifest)
    print(out, flush=True)
    return out


def check(out):
    m = load(out / 'manifest.json')
    for name, digest in m['artifacts'].items():
        path = (out / name).resolve()
        assert path.is_relative_to(out.resolve()) and sha(path) == digest
    assert len(m['frames']) == 166 and len(m['groups']) == 2
    cases = {c['id']: c for c in m['cases']}
    all_ids = set()
    for group in m['groups']:
        for axis, ids in group['sweeps'].items():
            selected = [m['frames'][i] for i in ids]
            all_ids.update(ids)
            if axis == 'lambda':
                assert [f['lambda'] for f in selected] == LAMBDAS and all(f['kappa'] == 2 and cases[f['case']]['quality'] == 30 for f in selected)
            elif axis == 'kappa':
                assert [f['kappa'] for f in selected] == KAPPAS and all(f['lambda'] == .008 and cases[f['case']]['quality'] == 30 for f in selected)
            else:
                assert [cases[f['case']]['quality'] for f in selected] == QUALITIES and all(f['lambda'] == .008 and f['kappa'] == 2 for f in selected)
    assert all_ids == set(range(len(m['frames'])))
    replayed = []
    max_error = 0.0
    for case in m['cases']:
        reference = pixels(out / case['reference']); degraded = pixels(out / case['input'])
        computed = scores(reference, degraded, case['roi'])
        for region in ['full', 'roi']:
            for metric in ['psnr_db', 'ssim']:
                error = abs(computed[region][metric] - case['baseline_metrics'][region][metric]); max_error = max(max_error, error); assert error < 1e-10
    for f in m['frames']:
        case = cases[f['case']]; reference = pixels(out / case['reference']); restored = pixels(out / f['output']['full']); roi = case['roi']; x0, y0, x1, y1 = roi
        assert np.array_equal(restored[y0:y1, x0:x1], pixels(out / f['output']['roi']))
        computed = scores(reference, restored, roi)
        for region in ['full', 'roi']:
            for metric in ['psnr_db', 'ssim']:
                error = abs(computed[region][metric] - f['metrics'][region][metric]); max_error = max(max_error, error); assert error < 1e-10
        if case['quality'] == 30 and f['lambda'] == .008 and f['kappa'] == 2:
            r = smooth_l0(pixels(out / case['input']).astype(np.float64) / 255, lambda_=.008, kappa=2, beta_max=1e5)
            assert np.array_equal(_display_pixels(r.image), restored)
            assert hashlib.sha256(r.image.tobytes()).hexdigest() == f['float64_sha256']
            replayed.append(f['id'])
    assert len(replayed) == 2
    result = {'checked_at': now(), 'passed': True, 'artifacts_checked': len(m['artifacts']), 'frames_checked': len(m['frames']), 'jpeg_baselines_checked': len(m['cases']), 'float_and_display_replayed_frames': replayed, 'max_metric_error': max_error, 'all_sweep_conditions_verified': True, 'negative_metric_counts': m['negative_metric_counts'], 'executed_by': 'AI; not member review'}
    dest = _new_run_directory(out, 'checks') / 'checks.json'; save(dest, result); print(dest, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'build', 'check'])
    parser.add_argument('directory', nargs='?', type=Path)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'results/public_jpeg_demo')
    args = parser.parse_args()
    if args.action == 'prepare': prepare()
    elif args.action == 'build': build(args.output_dir.resolve())
    elif not args.directory: parser.error('directory required for check')
    else: check(args.directory.resolve())


if __name__ == '__main__': main()
