"""独立 ADB 启动诊断入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from android_appium_test.environment import connected_devices, executable, select_device
from android_appium_test.startup_diagnostics import diagnose_startup


def main() -> int:
    parser = argparse.ArgumentParser(description="ADB 独立启动并保存 Logcat 诊断证据")
    parser.add_argument("--app", required=True, help="已安装 App 的真实包名")
    parser.add_argument("--output", required=True, help="新的诊断目录")
    parser.add_argument("--profile", help="本机工具路径配置 JSON")
    parser.add_argument("--device", help="ADB 序列号，覆盖 profile 默认设备")
    args = parser.parse_args()
    try:
        profile = json.loads(Path(args.profile).read_text(encoding="utf-8")) if args.profile else {}
        adb = executable("adb", profile.get("adb"))
        if not adb:
            raise ValueError("找不到 ADB")
        serial = select_device(connected_devices(adb), args.device or profile.get("device_serial"))
        result = diagnose_startup(adb, serial, args.app, Path(args.output).resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        # 退出码仅表示诊断是否完成；classification 才是 App 状态。
        return 0
    except (OSError, ValueError) as exc:
        print(f"启动诊断失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
