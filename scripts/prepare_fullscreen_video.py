"""Place an existing recording on a 16:9 canvas without cropping or stretching.

Run with system Python and requirements-video.txt available on PYTHONPATH.
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'docs/media/demo_three_sections_v2.mp4')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/media/demo_three_sections_fullscreen.mp4')
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    assert source != output
    metadata = json.loads(source.with_suffix('.json').read_text())
    assert sha(source) == metadata['video_sha256']
    assert sha(source.with_suffix('.png')) == metadata['poster_sha256']
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    layout = 'scale=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xf5f9f9,setsar=1'
    command = [ffmpeg, '-y', '-i', str(source), '-vf', layout, '-an', '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output)]
    subprocess.run(command, check=True, capture_output=True)
    poster_command = [ffmpeg, '-y', '-i', str(source.with_suffix('.png')), '-vf', layout, '-frames:v', '1', str(output.with_suffix('.png'))]
    subprocess.run(poster_command, check=True, capture_output=True)
    subprocess.run([ffmpeg, '-v', 'error', '-xerror', '-i', str(output), '-f', 'null', '-'], check=True, capture_output=True)
    metadata['presentation_conversion'] = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source': str(source.relative_to(ROOT)), 'source_sha256': sha(source),
        'command': command, 'poster_command': poster_command,
        'layout': '16:9 canvas; original aspect ratio and complete image preserved; side padding only',
        'recording_timeline_unchanged': True,
    }
    metadata.update(width=1920, height=1080, output_video=str(output.relative_to(ROOT)),
                    poster=str(output.with_suffix('.png').relative_to(ROOT)),
                    video_sha256=sha(output), poster_sha256=sha(output.with_suffix('.png')),
                    full_decode_passed=True)
    output.with_suffix('.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
    print(output)


if __name__ == '__main__':
    main()
