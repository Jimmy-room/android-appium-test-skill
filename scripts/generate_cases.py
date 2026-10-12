"""根据已确认的 App 规格生成页面对象、用例和测试数据。"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from android_appium_test.casegen import generate
from android_appium_test.config import ConfigError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        cases = generate(args.spec, args.output)
    except ConfigError as exc:
        parser.error(str(exc))
    print(f"已生成 {len(cases)} 条待执行用例：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
