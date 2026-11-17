"""Render docs/report.md into a printable HTML with embedded image assets.

Optional documentation helper: needs markdown-it-py, which is available in the
agent's authoring environment. Application/Demo runtime does not require it.
The generated HTML needs no Python, server, JavaScript, fonts, or remote assets.
"""

import base64
import hashlib
import html
import importlib.metadata
import io
import json
import platform
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

from markdown_it import MarkdownIt
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/report.md"
TARGET = ROOT / "docs/report.html"


class ValidateDocument(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = 0
        self.local_links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "link", "iframe"):
            raise ValueError("report must have no scripts, stylesheets or iframes")
        if tag == "img":
            uri = attrs["src"]
            assert uri.startswith("data:image/png;base64,")
            binary = base64.b64decode(uri.split(",", 1)[1], validate=True)
            with Image.open(io.BytesIO(binary)) as image:
                image.verify()
            self.images += 1
        if tag == "a":
            path = urlparse(attrs["href"])
            if not path.scheme and path.path:
                target = (SOURCE.parent / unquote(path.path)).resolve()
                assert target.is_relative_to(ROOT) and target.is_file(), target
                self.local_links.append(str(target.relative_to(ROOT)))


def main():
    source = SOURCE.read_text(encoding="utf-8")
    body = MarkdownIt("commonmark").enable("table").render(source)
    figures = []

    def embed(match):
        path = (SOURCE.parent / html.unescape(unquote(match.group(1)))).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError("image escapes repository")
        binary = path.read_bytes()
        figures.append({"path": str(path.relative_to(ROOT)),
                        "sha256": hashlib.sha256(binary).hexdigest()})
        return '<img src="data:image/png;base64,' + base64.b64encode(binary).decode("ascii") + '"'

    body = re.sub(r'<img src="([^"]+)"', embed, body)
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    stylesheet = """
    *{box-sizing:border-box}body{margin:0;color:#18232d;background:#f1f3f4;
    font-family:system-ui,"Microsoft YaHei","Noto Sans CJK SC",sans-serif;line-height:1.75}
    main{max-width:1120px;margin:24px auto;padding:48px 56px;background:white}
    h1{font-size:30px;line-height:1.4}h2{font-size:23px;margin-top:36px;border-bottom:2px solid #d7e2dc;padding-bottom:6px}
    h3{font-size:19px;margin-top:28px}p{margin:13px 0}a{color:#1b6553;overflow-wrap:anywhere}
    table{border-collapse:collapse;width:100%;font-size:13px;margin:20px 0;line-height:1.6}
    th,td{border:1px solid #bdcfc5;padding:7px;vertical-align:top;text-align:left}th{background:#e9f1ed}
    pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f3;padding:14px;font-size:13px;line-height:1.55}
    code{font-family:ui-monospace,Consolas,monospace;font-size:.92em;overflow-wrap:anywhere}
    img{display:block;max-width:100%;height:auto;margin:18px auto;border:1px solid #dde3df}
    footer{font-size:12px;border-top:1px solid #d7e2dc;margin-top:32px;padding-top:14px;color:#4b5d53}
    @media(max-width:700px){main{margin:0;padding:20px}table{font-size:11px}th,td{padding:4px}}
    @page{size:A4;margin:16mm}
    @media print{body{background:white}main{max-width:none;margin:0;padding:0}h1{font-size:23pt}
    h2{font-size:17pt;break-after:avoid}h3{font-size:13pt;break-after:avoid}p{font-size:10pt}
    table{font-size:8pt}tr,img,pre{break-inside:avoid}thead{display:table-header-group}
    a{color:inherit;text-decoration:none}img{max-height:115mm;object-fit:contain}}
    """
    page = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
    page += '<meta name="viewport" content="width=device-width,initial-scale=1">'
    page += '<meta name="source-sha256" content="' + digest + '">'
    page += '<title>L0结构平滑与JPEG去伪影课程报告</title><style>' + stylesheet + '</style></head><body><main>'
    page += body
    page += '<footer>正文与图像均包含在此文件中，可离线打开或打印。证据链接指向原项目文件，需连同仓库核查；参考文献链接需网络。Markdown来源SHA-256：' + digest + '</footer>'
    page += '</main></body></html>'
    validator = ValidateDocument()
    validator.feed(page)
    assert validator.images == len(figures) == 6
    TARGET.write_text(page, encoding="utf-8")
    record = {"created_at": datetime.now(timezone.utc).isoformat(), "actor": "智能体执行文档渲染与结构检查；非浏览器视觉或成员人工核验",
              "command": [sys.executable, "-m", "scripts.render_report"], "python": platform.python_version(),
              "optional_documentation_package": {"markdown-it-py": importlib.metadata.version("markdown-it-py")},
              "source": "docs/report.md", "source_sha256": digest, "html": "docs/report.html",
              "html_sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
              "embedded_figures": figures, "embedded_pngs_decoded": validator.images,
              "local_evidence_links_checked": sorted(set(validator.local_links)),
              "external_loads_required": False, "browser_visual_check": False,
              "passed": True}
    (ROOT / "docs/report_render.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{TARGET}: {len(TARGET.read_bytes())} bytes, {validator.images} embedded PNGs; source/evidence checks passed")


if __name__ == "__main__":
    main()
