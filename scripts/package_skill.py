"""生成可分发 ZIP；仅收录源码、文档和示例，排除本机路径与运行数据。"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP_FILES = {"SKILL.md", "README.md", "VALIDATION.md", "ACCEPTANCE_V2.md", "pyproject.toml"}
FOLDERS = {"src", "scripts", "references", "assets", "tests"}


def included_files() -> list[Path]:
    files = [ROOT / name for name in TOP_FILES]
    for folder in FOLDERS:
        files.extend(path for path in (ROOT / folder).rglob("*") if path.is_file())
    return sorted(path for path in files if path.is_file() and "__pycache__" not in path.parts
                  and path.suffix not in {".pyc", ".pyo"})


def package(destination: Path) -> int:
    if destination.exists():
        raise FileExistsError(f"拒绝覆盖已有 ZIP：{destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = included_files()
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, arcname="android-appium-test/" + file.relative_to(ROOT).as_posix())
    return len(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(f"已打包 {package(args.destination)} 个文件：{args.destination}")
