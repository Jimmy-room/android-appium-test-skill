"""将 Skill 打包为新的本地插件目录，不覆盖已安装版本。"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from package_skill import ROOT, included_files


def package(destination: Path) -> int:
    if destination.exists():
        raise FileExistsError(f"拒绝覆盖插件目录：{destination}")
    skill_dir = destination / "skills" / "android-appium-test"
    skill_dir.mkdir(parents=True)
    files = included_files()
    for source in files:
        target = skill_dir / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    metadata = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "android-appium-test", "version": "0.2.1",
        "description": "由 Codex 编排 Android Appium UI 测试，自动取证、生成用例、执行并报告。",
        "author": {"name": "Local User"},
        "extensions": {"com.openai": {"interface": {
            "displayName": "Android Appium Test", "shortDescription": "一键 Android UI 测试与 Allure 报告",
            "longDescription": "针对指定 APK 或已安装 App，结合自然语言用例和真实 UI 生成并运行 Pytest。",
            "developerName": "Local User", "category": "Productivity", "capabilities": ["Read", "Write"],
            "defaultPrompt": ["使用 android-appium-test Skill 测试我指定的 App，按上传用例自动执行并生成 Allure 报告。"],
        }}},
    }
    (destination / "plugin.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(f"已复制 {package(args.destination)} 个 Skill 文件：{args.destination}")
