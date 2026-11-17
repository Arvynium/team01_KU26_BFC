from __future__ import annotations

import argparse
from pathlib import Path


def normalize(root: Path) -> int:
    count = 0
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(2) != b"#!":
                continue
            data = b"#!" + stream.read()
        if b"\x00" in data:
            continue
        normalized = data.replace(b"\r\n", b"\n")
        if normalized != data:
            path.write_bytes(normalized)
            count += 1
        path.chmod(path.stat().st_mode | 0o111)
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--require", action="append", default=[])
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"Native source directory is missing: {args.root}")
    for relative in args.require:
        if not (args.root / relative).is_file():
            parser.error(f"Required native build script is missing: {relative}")
    count = normalize(args.root)
    print(f"Normalized {count} native scripts; restored script execute permissions.")


if __name__ == "__main__":
    main()
