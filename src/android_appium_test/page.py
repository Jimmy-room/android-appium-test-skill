"""页面对象通用操作；失败即抛错，避免静默跳过测试步骤。"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any


class ElementLookupError(RuntimeError):
    """页面元素未找到或不可见。"""


class BasePage:
    """供具体 App 页面对象继承的基础类。"""

    def __init__(self, driver: Any, artifact_dir: str | Path, timeout: float = 10):
        if timeout <= 0:
            raise ValueError("timeout 必须大于 0")
        self.driver = driver
        self.artifact_dir = Path(artifact_dir)
        self.timeout = timeout
        self.logger = logging.getLogger("android_appium_test.page")

    def find_element(self, locator: tuple[str, str]) -> Any:
        # 显式等待失败时保存现场并继续抛错，让 Pytest 记录真实失败。
        from selenium.common import TimeoutException
        from selenium.webdriver.support import expected_conditions as conditions
        from selenium.webdriver.support.ui import WebDriverWait

        try:
            return WebDriverWait(self.driver, self.timeout).until(
                conditions.visibility_of_element_located(locator)
            )
        except TimeoutException as exc:
            try:
                screenshot = self.take_screenshot()
            except Exception:
                self.logger.exception("元素查找失败后截图失败")
                screenshot = None
            raise ElementLookupError(f"等待元素超时：{locator}；截图：{screenshot}") from exc

    def find_elements(self, locator: tuple[str, str]) -> list[Any]:
        return self.driver.find_elements(*locator)

    def click(self, locator: tuple[str, str]) -> None:
        self.find_element(locator).click()

    def input_text(self, locator: tuple[str, str], text: str, *, clear: bool = False, submit: bool = False) -> None:
        element = self.find_element(locator)
        if clear:
            element.clear()
        element.send_keys(text)
        if submit:
            self.driver.press_keycode(66)

    def get_text(self, locator: tuple[str, str]) -> str:
        return self.find_element(locator).text

    def press_back(self) -> None:
        self.driver.press_keycode(4)

    def swipe(self, direction: str) -> None:
        """按当前窗口大小滑动，不依赖固定屏幕像素。"""
        if direction not in {"up", "down", "left", "right"}:
            raise ValueError("direction 必须是 up/down/left/right")
        size = self.driver.get_window_size()
        width, height = int(size["width"]), int(size["height"])
        self.driver.execute_script("mobile: swipeGesture", {
            "left": int(width * .1), "top": int(height * .15),
            "width": int(width * .8), "height": int(height * .7),
            "direction": direction, "percent": .65,
        })

    def take_screenshot(self) -> Path:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifact_dir / f"screenshot-{datetime.now():%Y%m%d-%H%M%S-%f}.png"
        if not self.driver.get_screenshot_as_file(str(path)):
            raise RuntimeError("Appium 截图失败")
        return path

    def mobile_shell(self, command: str, args: list[str] | None = None, *, timeout_ms: int = 5000) -> Any:
        if not command or args is not None and (not isinstance(args, list) or any(not isinstance(a, str) for a in args)):
            raise ValueError("command 必须非空，args 必须是字符串列表")
        return self.driver.execute_script(
            "mobile: shell", {"command": command, "args": args or [], "timeout": timeout_ms}
        )
