"""检查公开仓库中不应出现的地址、凭据和本机路径。"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PRIVATE_IP = re.compile(
    r"\b(?:10|127|192)\.(?:\d{1,3}\.){2}\d{1,3}\b"
    r"|\b172\.(?:1[6-9]|2\d|3[0-1])\.(?:\d{1,3}\.)\d{1,3}\b"
)
SENSITIVE_PATTERNS = (
    ("private_ip", PRIVATE_IP),
    ("linux_private_path", re.compile(r"/home/|/root/")),
    ("windows_private_path", re.compile(r"[A-Za-z]:\\(?:Users|home|0简历)\\")),
    ("github_token", re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}")),
    ("secret_key", re.compile(r"\b(?:sk|AKIA)[-_][A-Za-z0-9_-]{16,}\b")),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._-]{24,}")),
)
SKIP_DIRS = {".git", ".pytest_cache", "__pycache__", ".venv", "build", "dist"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".zip"}


def _files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path != SELF
        and not any(part in SKIP_DIRS for part in path.parts)
        and path.suffix.lower() not in SKIP_SUFFIXES
    ]


def find_violations() -> list[str]:
    violations: list[str] = []
    for path in _files():
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for label, pattern in SENSITIVE_PATTERNS:
                if pattern.search(line):
                    relative = path.relative_to(ROOT).as_posix()
                    violations.append(f"{relative}:{line_number}: {label}")
    return violations


def main() -> int:
    violations = find_violations()
    if violations:
        print("\n".join(violations))
        return 1
    print("public surface scan: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
