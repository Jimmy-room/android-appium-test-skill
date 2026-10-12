from __future__ import annotations

import json
from pathlib import Path

import pytest

from android_appium_test.config import ConfigError, load_config
from android_appium_test.data import load_cases
from android_appium_test.driver import DriverFactory
from android_appium_test.page import BasePage, ElementLookupError


def make_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_APPIUM_URL", "http://localhost:4723")
    monkeypatch.setenv("TEST_DEVICE", "emulator-1234")
    config = tmp_path / "config.yaml"
    config.write_text(
        "server:\n  url: ${TEST_APPIUM_URL}\n"
        "devices:\n  local:\n    platformName: Android\n"
        "    automationName: UiAutomator2\n    deviceName: ${TEST_DEVICE}\n"
        "apps:\n  demo:\n    appPackage: org.example.demo\n"
        "    appActivity: .MainActivity\ncommon:\n  noReset: true\n",
        encoding="utf-8",
    )
    return config


def test_config_resolves_environment_and_validates_selection(tmp_path, monkeypatch):
    config = load_config(make_config(tmp_path, monkeypatch))
    assert config.server_url == "http://localhost:4723"
    assert config.capabilities("local", "demo")["deviceName"] == "emulator-1234"
    with pytest.raises(ConfigError, match="未知设备"):
        config.capabilities("missing", "demo")
    with pytest.raises(ConfigError, match="未知 App"):
        config.capabilities("local", "missing")


def test_config_rejects_missing_environment_and_incomplete_app(tmp_path, monkeypatch):
    path = make_config(tmp_path, monkeypatch)
    monkeypatch.delenv("TEST_DEVICE")
    with pytest.raises(ConfigError, match="TEST_DEVICE"):
        load_config(path)
    monkeypatch.setenv("TEST_DEVICE", "emulator-1234")
    path.write_text(path.read_text(encoding="utf-8").replace("    appActivity: .MainActivity\n", ""), encoding="utf-8")
    with pytest.raises(ConfigError, match="App 需提供"):
        load_config(path).capabilities("local", "demo")


def test_data_loader_supports_json_and_yaml_without_embedded_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_SECRET", "temporary-value")
    json_file = tmp_path / "cases.json"
    json_file.write_text(json.dumps([{"name": "case", "token": "${TEST_SECRET}"}]), encoding="utf-8")
    yaml_file = tmp_path / "cases.yaml"
    yaml_file.write_text("- name: case\n  token: ${TEST_SECRET}\n", encoding="utf-8")
    assert load_cases(json_file) == load_cases(yaml_file)
    assert load_cases(json_file)[0]["token"] == "temporary-value"
    json_file.write_text("[]", encoding="utf-8")
    with pytest.raises(ConfigError, match="非空对象列表"):
        load_cases(json_file)


def test_driver_uses_selected_capabilities_and_closes(tmp_path, monkeypatch):
    config = load_config(make_config(tmp_path, monkeypatch))
    from appium import webdriver

    calls = {}

    class FakeDriver:
        def quit(self):
            calls["closed"] = True

    def fake_remote(*, command_executor, options):
        calls["url"] = command_executor
        calls["caps"] = options.to_capabilities()
        return FakeDriver()

    monkeypatch.setattr(webdriver, "Remote", fake_remote)
    driver = DriverFactory(config).create("local", "demo")
    assert calls["url"] == "http://localhost:4723"
    assert calls["caps"]["appium:appPackage"] == "org.example.demo"
    DriverFactory.close(driver)
    assert calls["closed"] is True


def test_page_operations_fail_loudly_and_capture_screenshot(tmp_path):
    from selenium.common import NoSuchElementException

    class FakeElement:
        text = "visible"
        def __init__(self):
            self.clicked = False
            self.sent = None
        def is_displayed(self):
            return True
        def click(self):
            self.clicked = True
        def send_keys(self, text):
            self.sent = text

    class FakeDriver:
        def __init__(self):
            self.element = FakeElement()
            self.missing = False
        def find_element(self, *locator):
            if self.missing:
                raise NoSuchElementException("absent")
            return self.element
        def get_screenshot_as_file(self, path):
            Path(path).write_bytes(b"image")
            return True

    driver = FakeDriver()
    page = BasePage(driver, tmp_path, timeout=0.01)
    page.click(("id", "button"))
    page.input_text(("id", "field"), "hello")
    assert driver.element.clicked and driver.element.sent == "hello"
    assert page.get_text(("id", "field")) == "visible"
    driver.missing = True
    with pytest.raises(ElementLookupError, match="等待元素超时"):
        page.click(("id", "missing"))
    assert len(list(tmp_path.glob("screenshot-*.png"))) == 1
