"""Appium UiAutomator2 驱动创建与释放。"""

from __future__ import annotations

from typing import Any

from .config import AppConfig


class DriverFactory:
    """按指定设备和 App 构建远程会话。"""

    def __init__(self, config: AppConfig):
        self.config = config

    def create(self, device_key: str, app_key: str) -> Any:
        # 延迟导入，配置检查和用例生成无需连接设备或安装 Appium。
        from appium import webdriver
        from appium.options.android import UiAutomator2Options

        options = UiAutomator2Options()
        options.load_capabilities(self.config.capabilities(device_key, app_key))
        return webdriver.Remote(command_executor=self.config.server_url, options=options)

    @staticmethod
    def close(driver: Any) -> None:
        if driver is not None:
            driver.quit()
