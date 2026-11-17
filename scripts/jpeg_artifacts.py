"""Reproducible Clip-art JPEG experiments using this group's existing L0 core.

All inputs are deterministic geometric drawings made by this script, not a
paper's restored output, downloaded art, or a member's hand-drawn work.
"""
import argparse
import csv
import hashlib
import json
import math
import shlex
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, JpegImagePlugin, features

from l0_smoothing.metrics import image_metrics
from l0_smoothing.workflow import (
    _display_pixels, _environment, _new_run_directory, _sha256_pixels,
    read_8bit_image, replay_record, run_and_save,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'jpeg_artifacts'
QUALITIES = (10, 30, 70)
LAMBDAS = (0.0005, 0.002, 0.008, 0.03)
KAPPA, BETA_MAX = 2.0, 100000.0
SPECS = {
    'house_rgb': {'mode': 'RGB', 'roi': [30, 90, 126, 186]},
    'line_gray': {'mode': 'L', 'roi': [94, 52, 190, 148]},
}
METRIC_PROTOCOL = {
    'reference': 'decoded clean.png uint8, identical reference for JPEG and every output',
    'candidate': 'decoded JPEG for baseline; clipped-rounded saved output.png for restoration',
    'data_range': 255,
    'psnr': '10*log10(255^2 / mean((reference-candidate)^2)); mean includes all channels',
    'ssim': '11x11 Gaussian sigma=1.5; K1=.01 K2=.03; population moments; valid domain excludes 5-pixel border',
    'rgb': 'PSNR pools RGB samples; SSIM averages the three channel SSIMs, without grayscale conversion',
    'roi': 'same xyxy crop for every candidate; PSNR/SSIM recomputed on crop, including SSIM valid border within crop',
    'float_output': 'uncropped/unclipped output.npy retained; not used in main uint8 metric table',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def draw_clean(name):
    """Fixed integer geometry on a 3x canvas, downsampled once for antialiasing."""
    scale = 3
    mode = SPECS[name]['mode']
    image = Image.new(mode, (256 * scale, 256 * scale), (248, 246, 236) if mode == 'RGB' else 248)
    d = ImageDraw.Draw(image)
    def xy(coords):
        return tuple(int(round(v * scale)) for v in coords)
    def line(coords, fill, width=1):
        d.line(xy(coords), fill=fill, width=width * scale)
    if name == 'house_rgb':
        dark = (27, 39, 50)
        d.ellipse(xy((178, 20, 225, 67)), fill=(247, 186, 52), outline=dark, width=3*scale)
        d.rectangle(xy((0, 211, 256, 256)), fill=(84, 159, 117))
        d.rectangle(xy((42, 111, 194, 211)), fill=(78, 151, 196), outline=dark, width=4*scale)
        d.polygon(xy((26, 115, 117, 43, 210, 115)), fill=(213, 80, 64), outline=dark, width=4*scale)
        d.rectangle(xy((62, 132, 101, 170)), fill=(246, 221, 116), outline=dark, width=3*scale)
        line((81, 133, 81, 169), dark, 2)
        line((63, 151, 100, 151), dark, 2)
        d.rectangle(xy((133, 148, 172, 211)), fill=(237, 210, 161), outline=dark, width=3*scale)
        d.ellipse(xy((158, 179, 163, 184)), fill=dark)
        # Thin, low-contrast decorative marks deliberately test detail loss.
        for y in (180, 186, 192):
            line((57, y, 103, y), (94, 165, 202), 1)
        line((12, 224, 238, 224), (48, 120, 81), 1)
        for x in range(18, 238, 15):
            line((x, 237, x+5, 229), (54, 128, 86), 1)
    else:
        d.rounded_rectangle(xy((27, 24, 228, 231)), radius=10*scale, fill=237, outline=24, width=3*scale)
        d.ellipse(xy((56, 52, 137, 133)), fill=252, outline=26, width=3*scale)
        line((69, 115, 122, 64), 30, 2)
        line((69, 65, 122, 116), 30, 2)
        d.rectangle(xy((54, 157, 139, 202)), fill=175, outline=25, width=3*scale)
        d.polygon(xy((156, 201, 190, 146, 216, 201)), fill=225, outline=35, width=2*scale)
        for y in (56, 65, 74, 83, 92, 101, 110, 119):
            line((155, y, 205, y), 204 if y % 2 else 185, 1)
        line((43, 143, 211, 143), 220, 1)
        for x in (147, 153, 159, 165):
            line((x, 125, x, 137), 212, 1)
    return image.resize((256, 256), Image.Resampling.LANCZOS)


def prepare():
    DATA.mkdir(parents=True, exist_ok=True)
    manifest_path = DATA / 'manifest.json'
    existing = load_json(manifest_path) if manifest_path.exists() else None
    images = {}
    for name, spec in SPECS.items():
        generated = draw_clean(name)
        target = DATA / f'{name}.png'
        if target.exists():
            with Image.open(target) as saved:
                if saved.mode != generated.mode or not np.array_equal(np.asarray(saved), np.asarray(generated)):
                    raise ValueError(f'existing clean input differs from deterministic generator: {target}')
        else:
            if existing:
                raise ValueError(f'archived clean input missing: {target}')
            generated.save(target)
        images[name] = {'file': target.name, 'file_sha256': digest(target), 'mode': spec['mode'],
                        'size': [256, 256], 'pixel_sha256': _sha256_pixels(np.asarray(generated), spec['mode']),
                        'roi_xyxy': spec['roi']}
    if existing:
        if existing['images'] != images:
            raise ValueError('source manifest mismatch; existing archive is never overwritten')
    else:
        write_json(manifest_path, {'created_at': datetime.now(timezone.utc).isoformat(),
            'actor': '智能体执行生成；成员B任务，蒋天乐 2023010721',
            'source': 'scripts/jpeg_artifacts.py:draw_clean, generator version 1; original deterministic Pillow geometric drawings',
            'external_assets': False, 'randomness': 'none; fixed integer coordinates; 3x supersampling then LANCZOS',
            'preprocessing': 'clean images are directly rendered PNGs; no prior JPEG encoding',
            'environment': _environment(), 'images': images})
    print(DATA / 'manifest.json', flush=True)


def panel(images, labels, roi, zoom=False):
    width, height = 256, 256
    margin, label_h = 8, 48
    out = Image.new('RGB', (len(images)*(width+margin)+margin, height+label_h+2*margin), 'white')
    d = ImageDraw.Draw(out)
    for i, (im, label) in enumerate(zip(images, labels)):
        if zoom:
            im = im.crop(roi).resize((width, height), Image.Resampling.NEAREST)
        im = im.convert('RGB')
        left = margin + i*(width+margin)
        d.text((left, margin), label, fill='black')
        out.paste(im, (left, margin+label_h))
        if not zoom:
            x0, y0, x1, y1 = roi
            d.rectangle((left+x0, margin+label_h+y0, left+x1-1, margin+label_h+y1-1), outline='red', width=1)
    return out


def measure(clean, candidate, roi):
    full = image_metrics(clean, candidate)
    x0, y0, x1, y1 = roi
    local = image_metrics(clean[y0:y1, x0:x1], candidate[y0:y1, x0:x1])
    return {**full, 'roi_psnr_db': local['psnr_db'], 'roi_ssim': local['ssim']}


def row_for(image, quality, lam, relative, clean, candidate, roi, baseline, record=None):
    scores = measure(clean, candidate, roi)
    return {'image': image, 'jpeg_quality': quality, 'stage': 'jpeg' if lam is None else 'l0',
        'lambda': '' if lam is None else lam, 'kappa': '' if lam is None else KAPPA,
        'beta_max': '' if lam is None else BETA_MAX,
        'iterations': 0 if record is None else record['iterations'],
        'elapsed_seconds': 0 if record is None else record['elapsed_seconds'],
        **scores, 'delta_psnr_db': scores['psnr_db']-baseline['psnr_db'],
        'delta_ssim': scores['ssim']-baseline['ssim'],
        'display_result': relative, 'record': '' if record is None else str(Path(relative).parent/'run.json')}


def run(output_root):
    manifest = load_json(DATA / 'manifest.json')
    for item in manifest['images'].values():
        if digest(DATA/item['file']) != item['file_sha256']:
            raise ValueError('clean source hash mismatch')
    experiment = _new_run_directory(Path(output_root), 'jpeg')
    shutil.copyfile(DATA/'manifest.json', experiment/'source_manifest.json')
    rows = []
    settings = []
    for name, spec in SPECS.items():
        image_dir = experiment/name
        image_dir.mkdir()
        shutil.copyfile(DATA/manifest['images'][name]['file'], image_dir/'clean.png')
        clean_float, clean, mode = read_8bit_image(image_dir/'clean.png')
        del clean_float
        roi = spec['roi']
        write_json(image_dir/'roi.json', {'xyxy': roi, 'same_for_all_qualities_and_parameters': True,
                   'reason': 'fixed before runs; includes prominent boundaries and thin/internal structures'})
        for quality in QUALITIES:
            folder = image_dir/f'q{quality}'
            folder.mkdir()
            jpeg_path = folder/'compressed.jpg'
            with Image.open(image_dir/'clean.png') as im:
                # subsampling=0 deliberately isolates quantization/ringing from chroma downsampling.
                kwargs = {'quality': quality, 'optimize': False, 'progressive': False}
                if mode == 'RGB':
                    kwargs['subsampling'] = 0
                im.save(jpeg_path, format='JPEG', **kwargs)
            _, compressed, _ = read_8bit_image(jpeg_path)
            with Image.open(jpeg_path) as jpeg:
                encoding = {'quality_argument': quality, 'subsampling_argument': 0 if mode == 'RGB' else None,
                    'decoded_sampling': JpegImagePlugin.get_sampling(jpeg),
                    'quantization_tables': jpeg.quantization, 'optimize': False, 'progressive': False,
                    'encoder': 'Pillow JPEG', 'libjpeg_version': features.version('jpg'),
                    'sha256': digest(jpeg_path), 'bytes': jpeg_path.stat().st_size}
            write_json(folder/'jpeg.json', encoding)
            settings.append({'image': name, 'quality': quality, **encoding})
            baseline = image_metrics(clean, compressed)
            jpeg_relative = jpeg_path.relative_to(experiment).as_posix()
            rows.append(row_for(name, quality, None, jpeg_relative, clean, compressed, roi, baseline))
            ims = [Image.fromarray(clean), Image.fromarray(compressed)]
            labels = ['Clean reference', f'JPEG Q={quality}\nPSNR {baseline["psnr_db"]:.2f} / SSIM {baseline["ssim"]:.4f}']
            for lam in LAMBDAS:
                record_path = run_and_save(jpeg_path, folder, lambda_=lam, kappa=KAPPA, beta_max=BETA_MAX)
                record = load_json(record_path)
                output_path = record_path.parent/record['output']['display']
                _, candidate, _ = read_8bit_image(output_path)
                row = row_for(name, quality, lam, output_path.relative_to(experiment).as_posix(), clean, candidate, roi, baseline, record)
                rows.append(row)
                ims.append(Image.fromarray(candidate))
                labels.append(f'L0 lambda={lam:g}\nPSNR {row["psnr_db"]:.2f} / SSIM {row["ssim"]:.4f}')
                print(f'{name} Q{quality} lambda={lam:g}: {row["psnr_db"]:.4f}dB SSIM={row["ssim"]:.6f}, {row["elapsed_seconds"]:.3f}s', flush=True)
            panel(ims, labels, roi).save(folder/'full_comparison.png')
            panel(ims, labels, roi, True).save(folder/'same_region_zoom.png')
    with (experiment/'metrics.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    inventory = {path.relative_to(experiment).as_posix(): digest(path) for path in sorted(experiment.rglob('*')) if path.is_file()}
    write_json(experiment/'experiment.json', {
        'created_at': datetime.now(timezone.utc).isoformat(), 'actor': '智能体执行实验；成员B 蒋天乐 2023010721',
        'command': shlex.join([sys.executable, '-m', 'scripts.jpeg_artifacts', *sys.argv[1:]]),
        'working_directory': str(Path.cwd()), 'script_sha256': digest(Path(__file__)), 'environment': {**_environment(), 'opencv': cv2.__version__, 'libjpeg': features.version('jpg')},
        'parameters': {'qualities': QUALITIES, 'lambdas': LAMBDAS, 'kappa': KAPPA, 'beta_max': BETA_MAX},
        'metric_protocol': METRIC_PROTOCOL, 'row_count': len(rows), 'l0_run_count': len(SPECS)*len(QUALITIES)*len(LAMBDAS),
        'jpeg_settings': settings, 'artifact_sha256': inventory,
        'notes': ['Every tested result retained, including metric decreases.', 'ROI chosen from generator geometry before runs; no post-hoc crop selection.',
                  'No parameter selected on held-out data; per-image best values are descriptive, not generalization claims.']})
    print(experiment, flush=True)
    return experiment


def check(experiment):
    experiment = Path(experiment).resolve()
    config = load_json(experiment/'experiment.json')
    if config['parameters'] != {'qualities': list(QUALITIES), 'lambdas': list(LAMBDAS), 'kappa': KAPPA, 'beta_max': BETA_MAX}:
        raise ValueError('experiment parameter grid differs from supported protocol')
    for relative, expected in config['artifact_sha256'].items():
        path = (experiment/relative).resolve()
        if not path.is_relative_to(experiment) or digest(path) != expected:
            raise ValueError(f'artifact missing or hash mismatch: {relative}')
    with (experiment/'metrics.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    expected = {(n, q, l) for n in SPECS for q in QUALITIES for l in ('', *LAMBDAS)}
    observed = {(r['image'], int(r['jpeg_quality']), float(r['lambda']) if r['lambda'] else '') for r in rows}
    if len(rows) != len(expected) or observed != expected:
        raise ValueError('metric grid missing or duplicate cases')
    sources = load_json(experiment/'source_manifest.json')
    for name in SPECS:
        if digest(experiment/name/'clean.png') != sources['images'][name]['file_sha256']:
            raise ValueError('clean reference hash mismatch')
        if load_json(experiment/name/'roi.json')['xyxy'] != SPECS[name]['roi']:
            raise ValueError('ROI mismatch')
    for row in rows:
        name, quality = row['image'], int(row['jpeg_quality'])
        _, clean, mode = read_8bit_image(experiment/name/'clean.png')
        candidate_path = experiment/row['display_result']
        _, candidate, candidate_mode = read_8bit_image(candidate_path)
        if candidate_mode != mode:
            raise ValueError('candidate mode differs from reference')
        scores = measure(clean, candidate, SPECS[name]['roi'])
        for key, value in scores.items():
            if not math.isclose(float(row[key]), value, rel_tol=0, abs_tol=1e-10):
                raise ValueError(f'metric mismatch: {row["display_result"]} {key}')
        _, jpeg_pixels, _ = read_8bit_image(experiment/name/f'q{quality}'/'compressed.jpg')
        baseline = image_metrics(clean, jpeg_pixels)
        for key in ('psnr_db', 'ssim'):
            if abs((scores[key]-baseline[key])-float(row[f'delta_{key}'])) > 1e-10:
                raise ValueError('baseline delta mismatch')
        if row['stage'] == 'l0':
            record_path = experiment/row['record']
            record = load_json(record_path)
            if record['parameters'] != {'lambda': float(row['lambda']), 'kappa': float(row['kappa']), 'beta_max': float(row['beta_max'])}:
                raise ValueError('L0 parameters differ')
            if record['iterations'] != int(row['iterations']) or record['elapsed_seconds'] != float(row['elapsed_seconds']):
                raise ValueError('L0 iteration/time summary differs')
            _, saved_input, input_mode = read_8bit_image(record_path.parent/record['input']['copy'])
            if input_mode != mode or not np.array_equal(saved_input, jpeg_pixels):
                raise ValueError('saved run input differs from encoded JPEG')
            if digest(record_path.parent/record['input']['copy']) != record['input']['file_sha256']:
                raise ValueError('saved input file hash differs from run record')
            if _sha256_pixels(saved_input, input_mode) != record['input']['pixel_sha256']:
                raise ValueError('saved input pixel hash differs')
            floats = np.load(record_path.parent/record['output']['float'], allow_pickle=False)
            if floats.dtype != np.float64 or floats.shape != clean.shape or not np.isfinite(floats).all():
                raise ValueError('invalid float output')
            if not np.array_equal(candidate, _display_pixels(floats)):
                raise ValueError('display output does not match float quantization')
            if _sha256_pixels(candidate, mode) != record['output']['display_pixel_sha256']:
                raise ValueError('display pixel hash differs')
        else:
            with Image.open(candidate_path) as jpeg:
                encoding = load_json(candidate_path.parent/'jpeg.json')
                if jpeg.format != 'JPEG' or JpegImagePlugin.get_sampling(jpeg) != encoding['decoded_sampling']:
                    raise ValueError('compressed input is not recorded JPEG format/sampling')
                if {str(k): v for k, v in jpeg.quantization.items()} != encoding['quantization_tables']:
                    raise ValueError('quantization tables differ')
    checks = _new_run_directory(experiment, 'checks')
    replay_rows = []
    for name in SPECS:
        row = next(r for r in rows if r['image'] == name and r['stage'] == 'l0' and int(r['jpeg_quality']) == 30 and float(r['lambda']) == .002)
        replay_path, passed = replay_record(experiment/row['record'], checks)
        replay_rows.append({'image': name, 'record': replay_path.relative_to(experiment).as_posix(),
                            **load_json(replay_path)['comparison']})
    result = {'created_at': datetime.now(timezone.utc).isoformat(), 'actor': '智能体执行验证',
              'command': shlex.join([sys.executable, '-m', 'scripts.jpeg_artifacts', *sys.argv[1:]]),
              'environment': {**_environment(), 'opencv': cv2.__version__},
              'audited_rows': len(rows), 'artifact_hashes_verified': len(config['artifact_sha256']),
              'metrics_recomputed': True, 'replays': replay_rows,
              'passed': len(replay_rows) == len(SPECS) and all(r['passed'] for r in replay_rows)}
    write_json(checks/'checks.json', result)
    print(checks/'checks.json', flush=True)
    if not result['passed']:
        raise ValueError('replay failed')
    return checks/'checks.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'check'])
    parser.add_argument('experiment', nargs='?', type=Path)
    parser.add_argument('--output-root', type=Path, default=ROOT/'results'/'jpeg_artifacts')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'run':
        run(args.output_root)
    elif args.experiment is None:
        parser.error('check requires an experiment directory')
    else:
        check(args.experiment)


if __name__ == '__main__':
    main()
