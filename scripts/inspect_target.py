"""盘点被测项目文件并标注 Android 项目线索，不推测业务预期。"""

import argparse
import json
from pathlib import Path


SKIP = {".git", ".gradle", "build", "dist", ".venv", "__pycache__", "node_modules"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.project.resolve()
    if not root.is_dir():
        parser.error(f"项目目录不存在：{root}")
    files = sorted(
        str(path.relative_to(root)).replace("\\", "/") for path in root.rglob("*")
        if path.is_file() and not SKIP.intersection(path.relative_to(root).parts)
    )
    hints = {
        "android_manifest": [name for name in files if name.endswith("AndroidManifest.xml")],
        "gradle": [name for name in files if name.endswith(("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"))],
        "apk": [name for name in files if name.lower().endswith(".apk")],
        "existing_tests": [name for name in files if "test" in Path(name).name.lower()],
    }
    result = {"project": str(root), "files": files, "hints": hints,
              "unknowns": ["测试范围", "可验证的预期行为", "设备及 Appium 地址", "设备标识", "App 包名/启动 Activity 或 APK", "定位符", "测试账号与环境"]}
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"项目盘点已保存：{args.output}")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
