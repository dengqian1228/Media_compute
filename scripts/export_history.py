"""Export a clean repository's real committed history without changing its refs.

Outputs git-history.txt, history.bundle and history-export.json outside the repo.
Existing output files are never overwritten. No commit, push or network operation
is performed. A temporary bare clone verifies that the bundle contains main/HEAD.
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ('git-history.txt', 'history.bundle', 'history-export.json')


def git(repo, *args):
    run = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if run.returncode:
        raise ValueError(f'git {args[0]} failed: {run.stderr.strip()}')
    return run.stdout, run.stderr


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_remote(value):
    parts = urlsplit(value)
    if parts.scheme in ('http', 'https') and parts.netloc:
        return urlunsplit((parts.scheme, parts.netloc.rsplit('@', 1)[-1], parts.path, parts.query, parts.fragment))
    return value


def export(repo, output_dir):
    repo = Path(repo).resolve()
    actual, _ = git(repo, 'rev-parse', '--show-toplevel')
    repo = Path(actual.strip()).resolve()
    out = Path(output_dir).resolve()
    if out.is_relative_to(repo):
        raise ValueError('output directory must be outside the repository')
    status, _ = git(repo, 'status', '--porcelain=v1', '--untracked-files=all')
    if status.strip():
        raise ValueError('tracked or untracked changes exist; commit requested work before final history export')
    for name in OUTPUTS:
        if (out/name).exists():
            raise ValueError(f'refusing to overwrite existing output: {out/name}')
    head, _ = git(repo, 'rev-parse', 'HEAD')
    main, _ = git(repo, 'rev-parse', 'refs/heads/main')
    if head != main:
        raise ValueError('HEAD differs from main; export the intended main revision first')
    out.mkdir(parents=True, exist_ok=True)
    log, _ = git(repo, 'log', '--all', '--stat', '--date=iso-strict', '--format=fuller')
    remotes, _ = git(repo, 'remote', '-v')
    remote_lines = []
    for line in remotes.splitlines():
        fields = line.split()
        if len(fields) >= 2:
            fields[1] = safe_remote(fields[1])
        remote_lines.append(' '.join(fields))
    with tempfile.TemporaryDirectory(prefix='media-history-export-', dir=out) as staging:
        staging = Path(staging)
        bundle = staging/'history.bundle'
        git(repo, 'bundle', 'create', str(bundle), '--all')
        verified_out, verified_err = git(repo, 'bundle', 'verify', str(bundle))
        with tempfile.TemporaryDirectory(prefix='media-history-clone-') as clone_parent:
            clone = Path(clone_parent)/'repo.git'
            result = subprocess.run(['git', 'clone', '--bare', str(bundle), str(clone)], capture_output=True, text=True)
            if result.returncode:
                raise ValueError('temporary bare clone failed: '+result.stderr.strip())
            clone_head, _ = git(clone, 'rev-parse', 'HEAD')
            clone_main, _ = git(clone, 'rev-parse', 'refs/heads/main')
            fsck_out, fsck_err = git(clone, 'fsck', '--full')
            if clone_main != main or clone_head != head:
                raise ValueError('bundle clone main/HEAD differs from source')
        (staging/'git-history.txt').write_text(log, encoding='utf-8')
        current_status, _ = git(repo, 'status', '--porcelain=v1', '--untracked-files=all')
        current_head, _ = git(repo, 'rev-parse', 'HEAD')
        if current_status.strip() or current_head != head:
            raise ValueError('repository changed during export; retry after completing work')
        artifacts = {name: {'sha256': sha256(staging/name), 'bytes': (staging/name).stat().st_size}
                     for name in ('git-history.txt','history.bundle')}
        record = {'created_at': datetime.now(timezone.utc).isoformat(), 'actor': '智能体执行历史导出与验证',
            'repository': str(repo), 'output_directory': str(out), 'head': head.strip(), 'main': main.strip(),
            'worktree_clean': True, 'includes_uncommitted_work': False,
            'history_command': ['git','log','--all','--stat','--date=iso-strict','--format=fuller'],
            'bundle_command': ['git','bundle','create','history.bundle','--all'],
            'bundle_verify': {'passed': True, 'stdout': verified_out, 'stderr': verified_err},
            'temporary_bare_clone': {'passed': True, 'head': clone_head.strip(), 'main': clone_main.strip(),
                                     'fsck_stdout': fsck_out, 'fsck_stderr': fsck_err},
            'remotes': remote_lines, 'artifacts': artifacts,
            'notes': ['All current refs exported; source refs and commits unchanged.',
                      'Git history does not replace missing historical AI conversations or member review.']}
        (staging/'history-export.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for name in OUTPUTS:
            # Check once more before exposing any final files; no overwrite.
            if (out/name).exists():
                raise ValueError(f'output appeared during export: {out/name}')
        for name in OUTPUTS:
            (staging/name).rename(out/name)
    print(out/'history-export.json')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT, help='repository root (default: this project)')
    parser.add_argument('--output-dir', type=Path, help='outside repository; default: its parent')
    args = parser.parse_args()
    try:
        export(args.repo, args.output_dir if args.output_dir else args.repo.resolve().parent)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'history export error: {exc}\n')


if __name__ == '__main__':
    main()
