import json
import os
import re
import subprocess
import sys
from pathlib import Path

DOUYIN_SCRIPT = Path(r'C:\Users\ye302\.openclaw\workspace\skills\douyin-video\scripts\douyin.js')


def parse_json_block(text: str):
    m = re.search(r'---JSON RESULT---\s*(\{.*\})\s*$', text, re.S)
    return json.loads(m.group(1)) if m else None


def main() -> int:
    if len(sys.argv) < 2:
        sys.stdout.buffer.write(json.dumps({"success": False, "message": "missing_url"}, ensure_ascii=False).encode('utf-8'))
        sys.stdout.buffer.write(b'\n')
        return 1

    url = sys.argv[1]
    proc = subprocess.run(
        ['node', str(DOUYIN_SCRIPT), url],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=300,
    )

    parsed = parse_json_block(proc.stdout)
    file_path = (parsed or {}).get('file_path', '')
    raw_exists = bool((parsed or {}).get('file_exists'))
    raw_size = int((parsed or {}).get('file_size_bytes') or 0)
    exists = raw_exists or (bool(file_path) and os.path.exists(file_path))
    size = raw_size or (os.path.getsize(file_path) if (bool(file_path) and os.path.exists(file_path)) else 0)

    payload = {
        'platform': 'douyin',
        'source_url': url,
        'success': bool((parsed or {}).get('success')) and exists,
        'file_path': file_path,
        'file_size_bytes': size,
        'raw_result': parsed,
        'notes': 'success requires real file metadata, not printed success alone',
    }
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8', errors='replace'))
    sys.stdout.buffer.write(b'\n')
    return 0 if payload['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
