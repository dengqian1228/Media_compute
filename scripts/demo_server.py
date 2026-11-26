"""Local, real L0 run/save/replay service for the classroom Demo.

Start with system Python: python3 -m scripts.demo_server --port 8765
The service binds only 127.0.0.1 and never executes shell commands.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import math
import mimetypes
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PIL import Image, UnidentifiedImageError

from l0_smoothing.workflow import _new_run_directory, replay_record, run_and_save

ROOT = Path(__file__).resolve().parents[1]
MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_BODY_BYTES = 6 * 1024 * 1024
MAX_PIXELS = 1024 * 1024
SAMPLES = {
    'beach': {'title': '沙滩（RGB）', 'mode': 'RGB', 'path': 'data/structure_smoothing/inputs/beach.png'},
    'brick_window_gray': {'title': '砖墙（灰度）', 'mode': 'L', 'path': 'data/structure_smoothing/inputs/brick_window_gray.png'},
    'sunflower': {'title': '向日葵（RGB）', 'mode': 'RGB', 'path': 'data/structure_smoothing/inputs/sunflower.png'},
}


class RequestError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def validate_image(raw: bytes) -> str:
    """Check dimensions before decoding; preserve the original eight-bit input."""
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise RequestError('图片为空或超过4 MiB上限')
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format not in ('PNG', 'JPEG') or im.mode not in ('L', 'RGB'):
                raise RequestError('仅支持8位灰度L或RGB的PNG/JPEG；请先转换调色板或带透明通道的图片')
            if im.width < 2 or im.height < 2 or im.width * im.height > MAX_PIXELS:
                raise RequestError('图像边长至少2像素，总像素不得超过1024×1024')
            if getattr(im, 'n_frames', 1) != 1:
                raise RequestError('仅支持单帧图片')
            extension = '.png' if im.format == 'PNG' else '.jpg'
            im.load()
            return extension
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise RequestError('图片无法解码或尺寸超过限制') from exc


def number(data: dict, name: str, default: float, minimum: float, maximum: float) -> float:
    value = data.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequestError(f'{name}必须是数值')
    value = float(value)
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise RequestError(f'{name}范围为{minimum}—{maximum}')
    return value


class DemoServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, root: Path = ROOT):
        self.root = root.resolve()
        self.output = self.root / 'results/demo_live'
        self.compute_lock = threading.Lock()
        super().__init__(('127.0.0.1', port), DemoHandler)


class DemoHandler(BaseHTTPRequestHandler):
    server: DemoServer
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def response(self, status: int, payload: bytes, content_type: str, head: bool = False):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.end_headers()
        if not head:
            self.wfile.write(payload)

    def json_response(self, status: int, data: dict, head: bool = False):
        self.response(status, json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8'), 'application/json; charset=utf-8', head)

    def local_request(self, allow_navigation: bool = False):
        port = self.server.server_address[1]
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if port == 80:
            hosts.update({'127.0.0.1', 'localhost'})
        if self.headers.get('Host') not in hosts:
            raise RequestError('只接受本机地址的请求', 403)
        # A link opened from chat is a cross-site document navigation. Allow
        # that entry-page visit, while keeping fetch/iframe/API requests checked.
        if (allow_navigation and self.command == 'GET'
                and self.headers.get('Sec-Fetch-Mode') == 'navigate'
                and self.headers.get('Sec-Fetch-Dest') == 'document'):
            return
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://{host}' for host in hosts}:
            raise RequestError('拒绝跨来源请求；请从本地Demo服务打开页面', 403)
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise RequestError('拒绝跨站请求', 403)

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head: bool = False):
        try:
            path = unquote(urlsplit(self.path).path)
            self.local_request(allow_navigation=path in ('/', '/docs/demo_interactive.html'))
            if path == '/api/status':
                self.json_response(200, {
                    'available': True,
                    'samples': [{'key': key, 'title': spec['title'], 'mode': spec['mode']} for key, spec in SAMPLES.items()],
                    'max_upload_bytes': MAX_UPLOAD_BYTES,
                    'max_pixels': MAX_PIXELS,
                    'lambda_range': [.0001, .2], 'kappa_range': [1.5, 3.0],
                    'beta_max': 100000,
                    'computation': '本机真实执行本组L0核心，并保存输入、PNG、NPY和run.json',
                }, head)
                return
            relative = path.lstrip('/') or 'docs/demo_interactive.html'
            parts = Path(relative).parts
            if not parts or any(part.startswith('.') for part in parts):
                raise RequestError('禁止访问该路径', 403)
            if relative not in {'AI_LOG.md', 'README.md'} and parts[0] not in {'docs', 'results', 'data', 'scripts', 'l0_smoothing'}:
                raise RequestError('文件不在Demo公开目录', 404)
            target = (self.server.root / relative).resolve()
            if not target.is_relative_to(self.server.root) or not target.is_file():
                raise RequestError('文件不存在', 404)
            content_type = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
            if content_type.startswith('text/'):
                content_type += '; charset=utf-8'
            self.response(200, target.read_bytes(), content_type, head)
        except RequestError as exc:
            self.json_response(exc.status, {'ok': False, 'error': str(exc)}, head)
        except OSError:
            self.json_response(404, {'ok': False, 'error': '文件无法读取'}, head)

    def do_OPTIONS(self):
        self.json_response(403, {'ok': False, 'error': '不允许跨来源API访问'})

    def read_json(self) -> dict:
        self.local_request()
        if self.headers.get('Transfer-Encoding'):
            raise RequestError('不接受分块上传')
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            raise RequestError('请求须使用application/json', 415)
        try:
            length = int(self.headers.get('Content-Length', ''))
        except ValueError as exc:
            raise RequestError('缺少有效Content-Length') from exc
        if not 0 < length <= MAX_BODY_BYTES:
            raise RequestError('请求过大或为空', 413)
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise RequestError('请求体不完整')
            value = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise RequestError('请求不是有效JSON') from exc
        if not isinstance(value, dict):
            raise RequestError('JSON必须为对象')
        return value

    def result(self, record_path: Path, started: float, **extra) -> dict:
        record = json.loads(record_path.read_text(encoding='utf-8'))
        def url(path):
            return '/' + path.relative_to(self.server.root).as_posix()
        folder = record_path.parent
        files = {
            'record': url(record_path),
            'input': url(folder / record['input']['copy']),
            'display': url(folder / record['output']['display']),
            'float': url(folder / record['output']['float']),
        }
        return {'ok': True, 'record_path': record_path.relative_to(self.server.root).as_posix(),
                'record': record, 'files': files, 'input_url': files['input'], 'output_url': files['display'],
                'wall_seconds': time.perf_counter() - started, **extra}

    def run_image(self, data: dict) -> dict:
        started = time.perf_counter()
        lam = number(data, 'lambda', .02, .0001, .2)
        kappa = number(data, 'kappa', 2., 1.5, 3.)
        if ('sample' in data) == ('file' in data):
            raise RequestError('请选择一个归档样例，或上传一个文件')
        if 'sample' in data:
            sample = data['sample']
            if not isinstance(sample, str) or sample not in SAMPLES:
                raise RequestError('未知归档样例')
            source = self.server.root / SAMPLES[sample]['path']
            validate_image(source.read_bytes())
            origin = {'sample': sample, 'archived_source': SAMPLES[sample]['path']}
        else:
            file = data['file']
            if not isinstance(file, dict) or not isinstance(file.get('base64'), str):
                raise RequestError('上传须包含file.base64字符串')
            try:
                raw = base64.b64decode(file['base64'], validate=True)
            except (ValueError, binascii.Error) as exc:
                raise RequestError('文件base64无效') from exc
            extension = validate_image(raw)
            upload = _new_run_directory(self.server.output, 'upload')
            source = upload / ('input' + extension)
            source.write_bytes(raw)
            label = file.get('name', '上传图像')
            origin = {'uploaded_name': str(label)[:200], 'note': '用户上传，原始文件字节保留；不推断图片来源或许可'}
        record_path = run_and_save(source, self.server.output, lambda_=lam, kappa=kappa, beta_max=100000)
        (record_path.parent / 'request.json').write_text(json.dumps({
            'created_at': datetime.now(timezone.utc).isoformat(), 'operation': 'run', 'origin': origin,
            'parameters': {'lambda': lam, 'kappa': kappa, 'beta_max': 100000},
            'executor': 'local Demo API; actual core execution',
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return self.result(record_path, started)

    def replay(self, data: dict) -> dict:
        started = time.perf_counter()
        relative = data.get('record_path')
        if not isinstance(relative, str) or Path(relative).is_absolute() or any(p.startswith('.') for p in Path(relative).parts):
            raise RequestError('复现记录必须是本服务结果目录内的相对路径')
        path = (self.server.root / relative).resolve()
        if not path.is_relative_to(self.server.output.resolve()) or path.name != 'run.json' or not path.is_file():
            raise RequestError('复现记录不在本服务结果目录或不存在')
        reference = json.loads(path.read_text(encoding='utf-8'))
        for section, key in [('input', 'copy'), ('output', 'float'), ('output', 'display')]:
            artifact = (path.parent / reference[section][key]).resolve()
            if not artifact.is_relative_to(path.parent) or not artifact.is_file():
                raise RequestError('复现记录包含不合法文件路径')
        params = reference['parameters']
        number(params, 'lambda', .02, .0001, .2)
        number(params, 'kappa', 2., 1.5, 3.)
        if params.get('beta_max') != 100000:
            raise RequestError('该记录的beta_max不属于本服务配置')
        validate_image((path.parent / reference['input']['copy']).read_bytes())
        new_record, passed = replay_record(path, self.server.output)
        result = self.result(new_record, started, passed=passed)
        result['comparison'] = result['record']['comparison']
        return result

    def do_POST(self):
        acquired = False
        try:
            data = self.read_json()
            route = urlsplit(self.path).path
            if route not in ('/api/run', '/api/replay'):
                raise RequestError('未知API', 404)
            acquired = self.server.compute_lock.acquire(blocking=False)
            if not acquired:
                raise RequestError('已有计算正在执行，请稍后再试', 409)
            result = self.run_image(data) if route == '/api/run' else self.replay(data)
            self.json_response(200, result)
        except RequestError as exc:
            self.close_connection = True
            self.json_response(exc.status, {'ok': False, 'error': str(exc)})
        except (ValueError, KeyError, TypeError, OSError) as exc:
            self.json_response(400, {'ok': False, 'error': '计算或记录校验失败：' + str(exc)})
        finally:
            if acquired:
                self.server.compute_lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be between 0 and 65535')
    server = DemoServer(args.port)
    print(f'本地 Demo：http://127.0.0.1:{server.server_address[1]}/docs/demo_interactive.html', flush=True)
    print('使用系统Python；按Ctrl+C停止。运行与复现结果保存在results/demo_live/。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
