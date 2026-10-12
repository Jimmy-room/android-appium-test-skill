"""从被测 App 规格生成可审查的用例清单和 Pytest 起点。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .config import ConfigError


_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_ACTIONS = {"tap", "type", "back", "assert", "wait", "swipe"}
_CHECKS = {"visible", "absent", "text_contains"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _read_spec(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        spec = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        raise ConfigError(f"规格文件无法读取：{path}: {exc}") from exc
    _require(isinstance(spec, dict), "规格根节点必须是对象")
    _require(isinstance(spec.get("features"), list) and spec["features"], "features 必须是非空列表")
    return spec


def _validate_feature(feature: Any) -> None:
    _require(isinstance(feature, dict), "feature 必须是对象")
    key = feature.get("key")
    _require(isinstance(key, str) and bool(_KEY.fullmatch(key)), "feature.key 必须是小写英文标识")
    _require(isinstance(feature.get("name"), str) and bool(feature["name"].strip()), f"{key}.name 缺失")
    locators = feature.get("locators")
    _require(isinstance(locators, dict) and bool(locators), f"{key}.locators 必须是非空对象")
    for name, locator in locators.items():
        _require(bool(_KEY.fullmatch(name)) and isinstance(locator, list) and len(locator) == 2
                 and all(isinstance(v, str) and v for v in locator), f"{key}.locators.{name} 无效")
    scenarios = feature.get("scenarios")
    _require(isinstance(scenarios, list) and bool(scenarios), f"{key}.scenarios 必须是非空列表")
    for scenario in scenarios:
        _require(isinstance(scenario, dict), f"{key} 场景必须是对象")
        for field in ("name", "objective"):
            _require(isinstance(scenario.get(field), str) and bool(scenario[field].strip()), f"{key} 场景缺少 {field}")
        _require(scenario.get("category") in {"normal", "abnormal", "boundary"}, f"{key} 场景类别无效")
        _require(isinstance(scenario.get("preconditions"), list), f"{key} 场景缺少 preconditions 列表")
        steps = scenario.get("steps")
        checks = scenario.get("expected")
        _require(isinstance(steps, list) and bool(steps), f"{key} 场景缺少 steps")
        _require(isinstance(checks, list) and bool(checks), f"{key} 场景缺少 expected")
        for step in steps:
            _require(isinstance(step, dict) and step.get("action") in _ACTIONS, f"{key} 步骤动作无效")
            if step["action"] in {"tap", "type", "assert", "wait"}:
                _require(step.get("target") in locators, f"{key} 步骤定位符不存在")
            if step["action"] == "type":
                _require(isinstance(step.get("value"), str), f"{key} 输入步骤缺少 value")
            if step["action"] == "assert":
                _require(step.get("check") in _CHECKS, f"{key} 步骤断言无效")
                if step["check"] == "text_contains":
                    _require(isinstance(step.get("value"), str) and bool(step["value"]), f"{key} 步骤文本断言缺少 value")
            if step["action"] == "swipe":
                _require(step.get("direction") in {"up", "down", "left", "right"}, f"{key} 滑动方向无效")
        for check in checks:
            _require(isinstance(check, dict) and check.get("check") in _CHECKS, f"{key} 预期类型无效")
            _require(check.get("target") in locators, f"{key} 预期定位符不存在")
            if check["check"] == "text_contains":
                _require(isinstance(check.get("value"), str) and bool(check["value"]), f"{key} 文本预期缺少 value")


def generate(spec_path: str | Path, output_dir: str | Path) -> list[dict[str, Any]]:
    """生成业务独立目录；存在同名输出时拒绝覆盖。"""
    spec = _read_spec(Path(spec_path))
    output = Path(output_dir)
    _require(not output.exists(), f"输出目录已存在，拒绝覆盖：{output}")
    features = spec["features"]
    for feature in features:
        _validate_feature(feature)
    keys = [feature["key"] for feature in features]
    _require(len(keys) == len(set(keys)), "feature.key 重复")

    # 先完整校验，再写文件，避免留下半成品。
    output.mkdir(parents=True)
    for folder in ("pages", "tests", "data"):
        (output / folder).mkdir()
    (output / "pages" / "__init__.py").write_text("", encoding="utf-8")
    (output / "conftest.py").write_text(
        "\"\"\"每条测试独立创建和释放 Appium 会话。\"\"\"\n"
        "import os\nfrom pathlib import Path\nimport pytest\nimport allure\n"
        "from android_appium_test.config import load_config\n"
        "from android_appium_test.driver import DriverFactory\n\n"
        "@pytest.fixture\n"
        "def artifact_dir():\n"
        "    path = Path(os.environ.get('ANDROID_TEST_ARTIFACT_DIR', '.artifacts'))\n"
        "    path.mkdir(parents=True, exist_ok=True)\n"
        "    return path\n\n"
        "@pytest.fixture\n"
        "def driver():\n"
        "    required = ('ANDROID_TEST_CONFIG', 'ANDROID_TEST_DEVICE', 'ANDROID_TEST_APP')\n"
        "    missing = [name for name in required if not os.environ.get(name)]\n"
        "    if missing:\n"
        "        pytest.fail('缺少运行参数：' + ', '.join(missing))\n"
        "    config = load_config(os.environ['ANDROID_TEST_CONFIG'])\n"
        "    factory = DriverFactory(config)\n"
        "    session = factory.create(os.environ['ANDROID_TEST_DEVICE'], os.environ['ANDROID_TEST_APP'])\n"
        "    try:\n"
        "        yield session\n"
        "    finally:\n"
        "        factory.close(session)\n\n"
        "@pytest.hookimpl(hookwrapper=True)\n"
        "def pytest_runtest_makereport(item, call):\n"
        "    outcome = yield\n"
        "    report = outcome.get_result()\n"
        "    if report.when != 'call' or not report.failed:\n"
        "        return\n"
        "    driver = item.funcargs.get('driver')\n"
        "    if driver is None:\n"
        "        return\n"
        "    try:\n"
        "        allure.attach(driver.get_screenshot_as_png(), name='failure-screenshot', attachment_type=allure.attachment_type.PNG)\n"
        "    except Exception as exc:\n"
        "        allure.attach(str(exc), name='screenshot-error', attachment_type=allure.attachment_type.TEXT)\n"
        "    try:\n"
        "        allure.attach(driver.page_source, name='failure-page-source', attachment_type=allure.attachment_type.XML)\n"
        "    except Exception as exc:\n"
        "        allure.attach(str(exc), name='page-source-error', attachment_type=allure.attachment_type.TEXT)\n",
        encoding="utf-8",
    )
    (output / "pytest.ini").write_text("[pytest]\ntestpaths = tests\npython_files = test_*.py\n", encoding="utf-8")
    all_cases: list[dict[str, Any]] = []
    for feature in features:
        key = feature["key"]
        class_name = "".join(word.title() for word in key.split("_")) + "Page"
        locators = {name: tuple(value) for name, value in feature["locators"].items()}
        page_code = (
            "\"\"\"由规格生成的页面定位符；可按被测 App 调整。\"\"\"\n"
            "from android_appium_test.page import BasePage\n\n"
            f"class {class_name}(BasePage):\n"
            f"    LOCATORS = {locators!r}\n\n"
            "    def locator(self, name):\n"
            "        return self.LOCATORS[name]\n"
        )
        (output / "pages" / f"{key}_page.py").write_text(page_code, encoding="utf-8")
        cases = []
        for index, scenario in enumerate(feature["scenarios"], 1):
            case = {
                "id": f"{key.upper()}-{index:03d}",
                "name": scenario["name"],
                "feature": feature["name"],
                "category": scenario["category"],
                "objective": scenario["objective"],
                "preconditions": scenario["preconditions"],
                "steps": scenario["steps"],
                "test_data": scenario.get("test_data", {}),
                "expected": scenario["expected"],
                "actual_result": None,
                "status": "not_run",
            }
            cases.append(case)
            all_cases.append(case)
        (output / "data" / f"{key}_cases.json").write_text(
            json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        test_code = (
            "\"\"\"从用例数据执行当前 App 的页面场景。\"\"\"\n"
            "from pathlib import Path\nimport allure\nimport pytest\n"
            "from android_appium_test.data import load_cases, resolve_values\n"
            f"from pages.{key}_page import {class_name}\n\n"
            f"CASES = load_cases(Path(__file__).resolve().parents[1] / 'data' / '{key}_cases.json', resolve_env=False)\n\n"
            "@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])\n"
            "def test_scenario(driver, artifact_dir, case):\n"
            "    case = resolve_values(case)\n"
            "    allure.dynamic.id(case['id'])\n"
            f"    page = {class_name}(driver, artifact_dir)\n"
            "    allure.dynamic.title(f\"{case['id']} {case['name']}\")\n"
            "    for step in case['steps']:\n"
            "        with allure.step(str(step)):\n"
            "            action = step['action']\n"
            "            if action == 'tap':\n                page.click(page.locator(step['target']))\n"
            "            elif action == 'type':\n                page.input_text(page.locator(step['target']), step['value'], clear=step.get('clear', False))\n"
            "            elif action == 'back':\n                page.press_back()\n"
            "            elif action == 'wait':\n                page.find_element(page.locator(step['target']))\n"
            "            elif action == 'swipe':\n                page.swipe(step['direction'])\n"
            "            elif action == 'assert':\n"
            "                locator = page.locator(step['target'])\n"
            "                if step['check'] == 'visible':\n                    assert page.find_element(locator) is not None\n"
            "                elif step['check'] == 'absent':\n                    assert not page.find_elements(locator)\n"
            "                elif step['check'] == 'text_contains':\n                    assert step['value'] in page.get_text(locator)\n"
            "    for expected in case['expected']:\n"
            "        with allure.step(str(expected)):\n"
            "            locator = page.locator(expected['target'])\n"
            "            if expected['check'] == 'visible':\n                assert page.find_element(locator) is not None\n"
            "            elif expected['check'] == 'absent':\n                assert not page.find_elements(locator)\n"
            "            elif expected['check'] == 'text_contains':\n"
            "                assert expected['value'] in page.get_text(locator)\n"
        )
        (output / "tests" / f"test_{key}.py").write_text(test_code, encoding="utf-8")
    (output / "case_catalog.json").write_text(
        json.dumps(all_cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return all_cases
