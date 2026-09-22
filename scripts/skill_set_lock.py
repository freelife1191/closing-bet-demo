#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vendor/skills 의 고정 vendor 스킬 사본을 sources.lock.json 과 대조한다.

기본 실행은 검증이다. 파일이 하나라도 어긋나면 어긋난 항목을 출력하고 종료 코드 1 로 끝난다.
`--write` 는 현재 파일로 lock 을 다시 만든다. 고정 커밋을 올릴 때는 아래 SOURCES 표를 먼저
고치고 새 사본을 vendor/skills/ 에 넣은 뒤 `--write` 를 실행한다. 절차는 vendor/skills/README.md.

표준 라이브러리만 쓴다. 폴더 해시는 docs/reference/skill-set 의 설치기와 같은 규칙이다.
파일별 SHA-256 을 경로의 casefold 순으로 정렬한 정규 JSON 의 SHA-256 이라서, 같은 파일
집합이면 어느 기기에서 계산해도 같은 값이 나온다. macOS 가 만드는 .DS_Store 만 무시한다.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = REPO_ROOT / "vendor" / "skills"
LOCK_PATH = VENDOR_DIR / "sources.lock.json"
TREE_HASH_ALGORITHM = "sha256-canonical-path-sha256-casefold-v1"
IGNORED_FILE_NAMES = {".DS_Store"}

# 고정 원본. 커밋을 바꾸면 사본을 새로 받고 --write 로 lock 을 다시 만든다.
SOURCES: list[dict[str, Any]] = [
    {
        "name": "next-dev-loop",
        "repository": "https://github.com/vercel/next.js",
        "commit": "ca2c75eb7f8d9dd012a8bb83c06132149fe221f9",
        "ref": "v16.3.5",
        "source_path": "skills/next-dev-loop",
        "license": {"source_path": "license.md", "local_path": "licenses/next-LICENSE.txt"},
    },
    {
        "name": "vercel-react-best-practices",
        "repository": "https://github.com/vercel-labs/agent-skills",
        "commit": "063bee94c3f4df8453406c830b0a7df0f2860278",
        "ref": None,
        "source_path": "skills/react-best-practices",
        # 그 커밋의 저장소 루트에 LICENSE 파일이 없다. 임의로 만들지 않는다.
        "license": None,
    },
    {
        "name": "vercel-composition-patterns",
        "repository": "https://github.com/vercel-labs/agent-skills",
        "commit": "063bee94c3f4df8453406c830b0a7df0f2860278",
        "ref": None,
        "source_path": "skills/composition-patterns",
        "license": None,
    },
    {
        "name": "web-design-guidelines",
        "repository": "https://github.com/vercel-labs/agent-skills",
        "commit": "063bee94c3f4df8453406c830b0a7df0f2860278",
        "ref": None,
        "source_path": "skills/web-design-guidelines",
        "license": None,
    },
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_digests(root: Path) -> list[dict[str, str]]:
    """폴더 안 모든 파일의 상대 경로와 SHA-256. 심볼릭 링크는 고정 사본에 있을 수 없어 거부한다."""
    if root.is_symlink():
        raise ValueError(f"symbolic link is not allowed: {root}")
    digests: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symbolic link is not allowed: {path}")
        if not path.is_file() or path.name in IGNORED_FILE_NAMES:
            continue
        relative = path.relative_to(root).as_posix()
        digests.append({"path": relative, "sha256": _sha256(path)})
    return sorted(digests, key=lambda item: (item["path"].casefold(), item["path"]))


def tree_sha256(digests: list[dict[str, str]]) -> str:
    canonical = sorted(digests, key=lambda item: (item["path"].casefold(), item["path"]))
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_lock() -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for source in SOURCES:
        destination = VENDOR_DIR / source["name"]
        digests = file_digests(destination)
        entry: dict[str, Any] = {
            "name": source["name"],
            "repository": source["repository"],
            "commit": source["commit"],
            "ref": source["ref"],
            "source_path": source["source_path"],
            "destination": destination.relative_to(REPO_ROOT).as_posix(),
            "tree_sha256": tree_sha256(digests),
            "files": digests,
            "license": None,
        }
        if source["license"]:
            local = VENDOR_DIR / source["license"]["local_path"]
            entry["license"] = {
                "source_path": source["license"]["source_path"],
                "local_path": local.relative_to(REPO_ROOT).as_posix(),
                "sha256": _sha256(local),
            }
        sources.append(entry)
    return {
        "kind": "skill-set-source-lock",
        "tree_hash_algorithm": TREE_HASH_ALGORITHM,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "sources": sources,
    }


def verify() -> list[str]:
    """lock 과 실제 파일의 차이. 비어 있으면 일치한다."""
    problems: list[str] = []
    if not LOCK_PATH.is_file():
        return [f"lock 파일이 없다: {LOCK_PATH}"]
    try:
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"lock 파일을 읽을 수 없다: {exc}"]
    if lock.get("tree_hash_algorithm") != TREE_HASH_ALGORITHM:
        problems.append(f"해시 규칙이 다르다: {lock.get('tree_hash_algorithm')!r}")

    locked = {entry["name"]: entry for entry in lock.get("sources", [])}
    expected = {source["name"] for source in SOURCES}
    for missing in sorted(expected - set(locked)):
        problems.append(f"lock 에 없는 원본: {missing} (--write 로 다시 만든다)")
    for extra in sorted(set(locked) - expected):
        problems.append(f"SOURCES 표에 없는 lock 항목: {extra}")

    for source in SOURCES:
        entry = locked.get(source["name"])
        if entry is None:
            continue
        destination = VENDOR_DIR / source["name"]
        if not destination.is_dir():
            problems.append(f"사본이 없다: {destination.relative_to(REPO_ROOT)}")
            continue
        for key in ("repository", "commit", "source_path"):
            if entry.get(key) != source[key]:
                problems.append(f"{source['name']}: lock 의 {key} 가 SOURCES 표와 다르다")
        try:
            actual = tree_sha256(file_digests(destination))
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if actual != entry.get("tree_sha256"):
            problems.append(
                f"{source['name']}: 폴더 해시가 다르다 (lock {entry.get('tree_sha256')}, 실제 {actual})"
            )
        license_spec = source["license"]
        if license_spec:
            local = VENDOR_DIR / license_spec["local_path"]
            if not local.is_file():
                problems.append(f"{source['name']}: 라이선스 사본이 없다: {local.relative_to(REPO_ROOT)}")
            elif (entry.get("license") or {}).get("sha256") != _sha256(local):
                problems.append(f"{source['name']}: 라이선스 사본의 해시가 lock 과 다르다")

    known = expected | {"licenses"}
    for child in sorted(VENDOR_DIR.iterdir()):
        if child.is_dir() and child.name not in known:
            problems.append(f"lock 에 없는 폴더가 vendor/skills 에 있다: {child.name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--write"]:
        lock = build_lock()
        LOCK_PATH.write_text(
            json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        for entry in lock["sources"]:
            print(f"{entry['tree_sha256']}  {len(entry['files']):3d} files  {entry['name']}")
        print(f"wrote {LOCK_PATH.relative_to(REPO_ROOT)}")
        return 0
    if args:
        print(__doc__)
        return 2
    problems = verify()
    if problems:
        print("\n".join(problems))
        return 1
    print(f"vendor/skills matches {LOCK_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
