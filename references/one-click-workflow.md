# 一键 Android UI 测试工作流

## 用户需要提供什么

提供 APK 或已安装 App 的包名，以及自然语言、Markdown、Word、Excel 或聊天消息中的测试步骤和预期。系统设置 App 可用 `settings` 标识。测试账号、关键预期与高风险动作需要明确；没有凭据时不能凭空生成。

## Codex 如何执行

1. 将聊天中的用例原文保存为本次运行的 Markdown；文件输入可直接使用。
2. 运行 `scripts/auto_test.py --app <输入> --cases <文件> --profile <本机配置> --output <输出根目录>`。`profile` 可省略；默认从 PATH 查找工具，设备必须唯一。配置样式见 `assets/local-profile.example.json`。
3. 对自然语言输入，脚本返回 `needs_agent` 和运行目录。Codex 读取该目录的 `cases-source.txt`、`evidence/initial.xml`、截图，按用户步骤逐屏取证，写出可审查的 `spec.json`。Python 脚本没有大模型语义能力；单次用户请求由 Codex 在内部继续到下一步。
4. 运行 `scripts/auto_test.py --resume <运行目录> --spec <spec.json> --profile <同一配置> --open-report`。生成的业务 Page Object、JSON 数据、Pytest 与报告均在运行目录。重试另建目录，保留首次失败。
5. 根据 `run-summary.json` 和 Allure 原始结果汇报。`counts` 为实际结果计数；`not_run` 永远不能当通过。

## 本机配置与依赖

核心依赖用 `python -m pip install -e .` 安装。读取 Word/Excel 可选 `python -m pip install -e ".[case-files]"`。Allure CLI、Android SDK/ADB、Appium Server 与 UiAutomator2 驱动需要已经安装。Skill 会尝试启动已有的模拟器和 Appium，不自动安装软件、不改系统设置。`profile` 可保存 ADB/Appium/Allure/LDPlayer 路径、实例索引、默认设备、本机 ADB TCP 端口与额外 Python 包目录；请勿保存密码。

## 可观察证据

每轮生成 `environment.json`、`app.json`、原始用例、UI XML/截图、规格、独立生成项目、Pytest 日志、Allure 原始结果与 HTML。失败截图和 Appium 页面源作为 Allure 附件。报告自动打开时使用本机 HTTP 服务，并在 `report-server.json` 记录 URL/PID。录屏不是本版必需能力；没有视频不会影响测试，但也不会声称录制完成。
