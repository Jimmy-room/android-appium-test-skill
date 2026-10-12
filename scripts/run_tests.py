"""对指定 Android App 项目运行 Pytest 并生成真实 Allure 报告。"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from android_appium_test.config import ConfigError
from android_appium_test.runner import run_project


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--device", required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        code, output = run_project(args.project, args.config, args.device, args.app, args.output)
    except ConfigError as exc:
        parser.error(str(exc))
    print(f"执行退出码：{code}；结果目录：{output}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
