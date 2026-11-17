"""Audit current delivery evidence without rerunning algorithms or claiming human approval.

Each invocation writes a new results/delivery/checks-.../checks.json. Original
member A assets, metrics, embedded report/slides images and 9-minute timing are
checked against real files. Historical AI_LOG Windows links are not reinterpreted.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag, urlparse

from PIL import Image
from l0_smoothing.workflow import _new_run_directory

ROOT = Path(__file__).resolve().parents[1]
BASE = 'b74eabc09cb9629542ec4831331b3bdda2ddf156'
JPEG = Path('results/jpeg_artifacts/jpeg-20261117T155122Z-e37cd961efa5')
PROTECTED = ['l0_smoothing/core.py','l0_smoothing/workflow.py','l0_smoothing/__init__.py',
             'l0_smoothing/__main__.py','scripts/structure_smoothing_experiment.py',
             'scripts/edge_comparison.py','tests/test_core.py','tests/test_workflow.py',
             'data/structure_smoothing','data/验证样例','results/structure_smoothing',
             'results/edge_comparison','results/验证运行','docs/algorithm.md','AGENTS.md']
REQUIRED = ['docs/report.md','docs/report.html','docs/presentation.md','docs/presentation.html',
            'docs/presentation_notes.md','docs/presentation_assets.json','docs/demo.md',
            'docs/delivery_checklist.md','docs/report_render.json']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def git(root, *args):
    p = subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True)
    if p.returncode:
        raise ValueError('git command failed: '+p.stderr.strip())
    return p.stdout


class OfflineDocument(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = 0
        self.image_fingerprints = []
        self.slide_seconds = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'section' and 'slide' in a.get('class','').split():
            self.slide_seconds.append(int(a['data-seconds']))
        if tag == 'img':
            uri = a.get('src','')
            if not uri.startswith('data:image/') or ';base64,' not in uri:
                raise ValueError('document image is not an embedded base64 image')
            data = base64.b64decode(uri.split(';base64,',1)[1],validate=True)
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
            with Image.open(io.BytesIO(data)) as im:
                self.image_fingerprints.append({'mode':im.mode,'size':list(im.size),
                                                'pixel_sha256':hashlib.sha256(im.tobytes()).hexdigest()})
            self.images += 1
        elif tag in ('script','link','iframe','audio','video','source','object','embed'):
            source = a.get('src') or a.get('href') or a.get('data')
            if source and not source.startswith('data:'):
                raise ValueError('document has nonembedded runtime resource: '+source)


def inspect_html(path):
    source = path.read_text(encoding='utf-8')
    p = OfflineDocument()
    p.feed(source)
    if p.images == 0:
        raise ValueError(f'no report/slide images found: {path}')
    for target in re.findall(r'url\(\s*[\'\"]?([^\)\'\"]+)',source):
        if not target.startswith('data:'):
            raise ValueError('nonembedded CSS resource: '+target)
    if re.search(r'@import\s|fetch\s*\(\s*[\'\"]https?://',source):
        raise ValueError('document contains external runtime import/request')
    return {'file':path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
            'images_decoded':p.images,'slide_seconds':p.slide_seconds,'self_contained_resources':True,
            'decoded_image_fingerprints':p.image_fingerprints}


def markdown_links(root):
    new_tracked = git(root,'diff','--name-only','--diff-filter=A',BASE,'--','*.md').splitlines()
    new_untracked = git(root,'ls-files','--others','--exclude-standard','--','*.md').splitlines()
    files = sorted(set(new_tracked+new_untracked+['README.md']))
    checked = []
    for relative in files:
        if relative == 'AI_LOG.md':
            continue
        path = root/relative
        for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            target = match.group(1).strip()
            if target.startswith('<') and '>' in target:
                target = target[1:target.index('>')]
            else:
                target = target.split(' "',1)[0]
            if not target or target.startswith('#') or urlparse(target).scheme:
                continue
            target = unquote(urldefrag(target)[0])
            target = re.sub(r':\d+$','',target)
            if target and not (path.parent/target).exists():
                raise ValueError(f'broken local Markdown link: {relative} -> {target}')
            checked.append({'document':relative,'target':target})
    return {'documents':files,'local_links_checked':len(checked),'links':checked}


def run(root):
    root = Path(root).resolve()
    out = _new_run_directory(root/'results/delivery','checks')
    result = {'created_at':datetime.now(timezone.utc).isoformat(),'actor':'智能体执行交付核对；非成员人工核验',
              'command':[sys.executable,'-m','scripts.delivery_check',*sys.argv[1:]],
              'cwd':str(Path.cwd()),'repository':str(root),'base_commit':BASE,
              'member_review':'pending; both members must review algorithm, outputs and classroom environment',
              'classroom_presentation':'pending; to be delivered by the two members',
              'checks':[],'passed':False}
    def audit(name, fn):
        try:
            detail = fn()
            result['checks'].append({'name':name,'passed':True,'detail':detail})
        except Exception as exc:
            result['checks'].append({'name':name,'passed':False,'error':f'{type(exc).__name__}: {exc}'})
    def protect():
        changed = git(root,'diff','--name-only',BASE,'--',*PROTECTED).splitlines()
        if changed:
            raise ValueError('member A files changed: '+', '.join(changed))
        return {'unchanged_paths':PROTECTED,'compared_with':BASE}
    audit('member_a_originals_unchanged',protect)
    def required():
        missing = [p for p in REQUIRED if not (root/p).is_file()]
        if missing:
            raise ValueError('missing delivery documents: '+', '.join(missing))
        return REQUIRED
    audit('required_documents_exist',required)
    def evidence():
        paths = sorted((root/JPEG).glob('checks-*/checks.json'))
        paths += sorted((root/'results/member_b_verification').glob('audit-*/audit.json'))
        paths += sorted((root/'results/member_b_verification').glob('jpeg-independent-*/metrics_audit.json'))
        if not paths or not any('metrics_audit.json'==p.name for p in paths):
            raise ValueError('missing independent audits/JPEG checks')
        for path in paths:
            if load(path).get('passed') is not True:
                raise ValueError('failed archived verification: '+str(path))
        exp = load(root/JPEG/'experiment.json')
        for relative, expected in exp['artifact_sha256'].items():
            p = root/JPEG/relative
            if sha(p) != expected:
                raise ValueError('JPEG archived artifact changed: '+relative)
        independent = load(next((root/'results/member_b_verification').glob('jpeg-independent-*/metrics_audit.json')))
        if independent['metrics_csv_sha256'] != sha(root/JPEG/'metrics.csv') or independent['rows_checked'] != 30:
            raise ValueError('independent audit CSV no longer matches')
        clean = load(root/'results/demo/clean_environment_verification.json')
        if (clean['installation']['include_system_site_packages'] is not False
            or clean['unit_tests']['passed'] is not True or clean['unit_tests']['tests_run'] != 14
            or clean['check']['passed'] is not True):
            raise ValueError('clean-environment verification incomplete')
        actual = load(root/clean['check']['record'])
        if actual['passed'] is not True or actual['embedded_images'] != 14:
            raise ValueError('clean demo check missing or failed')
        record = load(root/clean['demo']['record'])
        demo_root = (root/clean['demo']['record']).parent
        for relative, expected in record['artifact_sha256'].items():
            if sha(demo_root/relative) != expected:
                raise ValueError('clean demo artifact changed: '+relative)
        return {'archived_success_records':[p.relative_to(root).as_posix() for p in paths],
                'jpeg_artifacts_verified':len(exp['artifact_sha256']),
                'clean_environment_record':'results/demo/clean_environment_verification.json',
                'clean_demo_check':clean['check']['record'],'repeated_algorithm_runs':False}
    audit('experiments_and_clean_environment_evidence',evidence)
    audit('new_markdown_local_links',lambda:markdown_links(root))
    def report_html():
        rendered = load(root/'docs/report_render.json')
        if rendered['source_sha256'] != sha(root/'docs/report.md') or rendered['html_sha256'] != sha(root/'docs/report.html'):
            raise ValueError('report HTML is stale or altered relative to report_render.json')
        if rendered.get('passed') is not True:
            raise ValueError('report renderer validation failed')
        for figure in rendered['embedded_figures']:
            if sha(root/figure['path']) != figure['sha256']:
                raise ValueError('report source figure differs: '+figure['path'])
        return inspect_html(root/'docs/report.html')
    audit('report_offline_images_and_current_render',report_html)
    def slides():
        parsed = inspect_html(root/'docs/presentation.html')
        manifest = load(root/'docs/presentation_assets.json')
        seconds = parsed['slide_seconds']
        if len(seconds) != 10 or sum(seconds) != 540:
            raise ValueError('slides must have 10 sections totalling 540 seconds')
        if manifest['slides'] != 10 or manifest['total_seconds'] != 540 or manifest['speaker_seconds'] != {'A':270,'B':270}:
            raise ValueError('presentation timing manifest differs')
        for index, asset in enumerate(manifest['assets']):
            if sha(root/asset['source']) != asset['source_sha256']:
                raise ValueError('presentation source asset differs: '+asset['source'])
            roi = asset['roi_xyxy']
            if roi:
                if 'jpeg_artifacts' in Path(asset['source']).parts:
                    name = next(n for n in ('house_rgb','line_gray') if n in Path(asset['source']).parts)
                    expected_roi = load(root/JPEG/name/'roi.json')['xyxy']
                else:
                    name = next(n for n in ('beach','brick_window_gray','sunflower')
                                if n in Path(asset['source']).parts or n==Path(asset['source']).stem)
                    expected_roi = load(root/'results/structure_smoothing/experiment-20261117T102719Z-1b827758b270'/name/'roi.json')['xyxy']
                if roi != expected_roi:
                    raise ValueError('presentation crop differs from archived ROI: '+asset['source'])
            with Image.open(root/asset['source']) as image:
                image = image.crop(roi) if roi else image.copy()
                fingerprint = {'mode':image.mode,'size':list(image.size),
                               'pixel_sha256':hashlib.sha256(image.tobytes()).hexdigest()}
            if asset['embedded_size'] != fingerprint['size'] or fingerprint != parsed['decoded_image_fingerprints'][index]:
                raise ValueError('embedded slide pixels differ from declared source/crop: '+asset['source'])
        if parsed['images_decoded'] != len(manifest['assets']):
            raise ValueError('slide image count differs from source asset manifest')
        return {**parsed,'speaker_seconds':manifest['speaker_seconds'],'asset_sources_verified':len(manifest['assets'])}
    audit('presentation_assets_and_9_minute_schedule',slides)
    def key_metrics():
        rows = list(csv.DictReader((root/JPEG/'metrics.csv').open(encoding='utf-8-sig')))
        report = (root/'docs/report.md').read_text(encoding='utf-8')
        presentation = (root/'docs/presentation.md').read_text(encoding='utf-8')
        keys = [('house_rgb',30,None),('house_rgb',30,.008),('line_gray',70,None),('line_gray',70,.03)]
        values = []
        for name, quality, lam in keys:
            row = next(r for r in rows if r['image']==name and int(r['jpeg_quality'])==quality
                       and (float(r['lambda']) if r['lambda'] else None)==lam)
            for metric, places in [('psnr_db',4),('ssim',6),('roi_psnr_db',4),('roi_ssim',6)]:
                number = f'{float(row[metric]):.{places}f}'
                if number not in report:
                    raise ValueError(f'representative report metric missing/mismatched: {name} {quality} {lam} {metric} {number}')
                # Slide source deliberately omits the leading zero for SSIM.
                if metric in ('psnr_db','ssim') and number not in presentation and number.lstrip('0') not in presentation:
                    raise ValueError('representative presentation metric mismatch: '+number)
            values.append({'image':name,'quality':quality,'lambda':lam,
                           **{k:float(row[k]) for k in ('psnr_db','ssim','roi_psnr_db','roi_ssim')}})
        psnr_negative = sum(float(r['delta_psnr_db']) < 0 for r in rows if r['stage']=='l0')
        ssim_negative = sum(float(r['delta_ssim']) < 0 for r in rows if r['stage']=='l0')
        if len(rows)!=30 or psnr_negative!=8 or ssim_negative!=5:
            raise ValueError('CSV row/negative result counts differ from report')
        appendix = report.split('## 附录：JPEG 完整结果',1)[1]
        actual_lines = [line.strip() for line in appendix.splitlines()
                        if line.startswith('| house_rgb |') or line.startswith('| line_gray |')]
        expected_lines = ['| '+ ' | '.join([r['image'],r['jpeg_quality'],r['lambda'] or 'JPEG',
                          f'{float(r["psnr_db"]):.4f}',f'{float(r["ssim"]):.6f}',
                          f'{float(r["roi_psnr_db"]):.4f}',f'{float(r["roi_ssim"]):.6f}'])+' |' for r in rows]
        if actual_lines != expected_lines:
            raise ValueError('report appendix 30 rows differ from CSV formatted values/order')
        return {'representative_metrics':values,'rows':len(rows),'appendix_formatted_rows_verified':len(actual_lines),
                'negative_psnr_runs':psnr_negative,'negative_ssim_runs':ssim_negative}
    audit('representative_report_metrics_match_csv',key_metrics)
    result['passed'] = all(item['passed'] for item in result['checks'])
    target = out/'checks.json'
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(target)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=ROOT)
    args = p.parse_args()
    try:
        result = run(args.repo)
    except (ValueError,OSError) as exc:
        p.exit(2,f'delivery check error: {exc}\n')
    if not result['passed']:
        for check in result['checks']:
            if not check['passed']:
                print(check['name']+': '+check['error'],file=sys.stderr)
        p.exit(1)


if __name__ == '__main__':
    main()
