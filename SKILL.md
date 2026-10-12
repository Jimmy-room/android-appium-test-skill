---
name: android-appium-test
description: 用户提供 Android APK 或已安装 App 与自然语言、Markdown、Word、Excel 测试用例后，自动准备设备/Appium，核对真实 UI，生成 Page Object/Pytest，在设备上执行并生成新的 Allure 报告。仅支持 Android App UI。
---

# Android Appium 一键测试

当用户说“使用 android-appium-test Skill，测试指定 App，按照上传用例执行并生成 Allure 报告”时，主动完成以下流程。用户只需提供 App 与测试目标；不要要求用户编写 Python、YAML、JSON 或定位符。技术栈固定为 Python、Pytest、Appium UiAutomator2、Page Object、Allure。

## 一次请求的执行顺序

1. 确认 App 输入（APK 路径、已安装包名，或设备自带系统设置）和用例文件/文字。若用例直接写在聊天中，先将原文保存到本次输出目录的 `.md` 文件。已有本机 profile 可复用；profile 只保存工具路径和默认设备，不放账号密码。测试账号或关键预期缺失时才询问用户，不猜测。
2. 从 Skill 根目录运行 `python scripts/auto_test.py --app <APK或包名> --cases <文件> --profile <本机配置JSON> --output <独立输出目录>`。入口检查 Python 依赖、ADB、设备、Appium、UiAutomator2 与 Allure，尝试连接用户配置的本机模拟器并启动已有服务，获取真实包名和 Activity，打开 App，保存首屏 XML、截图与原始用例。多设备且无默认设备时询问用户。环境安装、系统配置修改或管理员权限按实际权限取得确认。
   若首屏始终没有目标包名，入口自动执行独立 ADB 启动诊断，保存本次 Logcat、设备 API、App 最低 API、真实 Activity 和分类结果。返回 `startup_blocked` 时先阅读 `startup-diagnosis.json`，不得跳过诊断直接生成定位符或宣称测试通过。已存在的失败报告保留。
3. 若入口直接执行结构化规格，转第 6 步。若返回 `needs_agent`，Codex 必须继续处理，不能把它当成任务完成：读取 `cases-source.txt`、`evidence/initial.xml` 和 `initial.json`。逐屏定位用户指定操作；只根据实际 UI 证据形成定位符。可用 `android_appium_test.app_discovery.capture_ui()` 保存后续页面，必要时用 Appium/ADB 导航，但只做用例要求的安全操作。注意 ADB 和 Appium 的 XML 对空属性可能不同；最终以 Appium 页面源验证定位符。
4. 将原文逐项转换为 `references/spec-format.md` 规定的规格，写入本次 run 目录的 `spec.json`。保留原有步骤顺序与预期；进入页面后的断言放在对应的 `assert` 步骤，返回后的断言放在 `expected`。每个定位符要能追溯到本次 UI XML；不能复用别的 App 的定位符。账号、预期、业务规则不明确时暂停并询问，不擅自弱化断言。WebView 或无法导出节点的页面说明限制与证据。
5. 先审查生成规格与用户原文、UI 证据是否一致，并检查是否涉及删除数据、购买、付款、账号注销、密码/网络/安全配置修改。危险操作必须先获用户明确确认；不得执行用例外的设备操作。
6. 运行 `python scripts/auto_test.py --resume <run目录> --spec <规格文件> --profile <同一配置> --open-report`。它生成独立 Page Object、JSON 数据、Fixture、Pytest 并实际执行；每次重试使用独立项目和 Allure 结果目录。读取 `workflow.json`、`run-summary.json`、`pytest.log`、`case_results.json` 和 Allure 原始结果。只有设备真实执行并由 Allure 记录的用例才可说通过。
7. 失败时先保留首轮日志、截图、XML 和报告，分析环境、定位、脚本或业务行为。只修正有证据的框架或定位问题；不删除断言，不把业务失败改成通过。重跑后同时报告首次失败和重试状态。提供设备、时间、命令、通过/失败/跳过数量和报告路径；报告自动打开失败时提供 HTML 路径。
   启动失败还可单独运行 `python scripts/diagnose_startup.py --app <真实包名> --profile <本机配置JSON> --output <新目录>`。诊断不使用 Appium，也不清除数据、卸载或重装。若 App 的 minSdk 高于设备 API，或 ADB 启动也产生 App 进程 FATAL EXCEPTION，保持原断言与 blocked 用例；只有更换兼容设备或取得用户授权使用兼容 APK 后才重跑四条测试。详见 [启动诊断](references/startup-diagnostics.md)。

自然语言理解与代码生成由 Codex Agent 完成。普通 Python 脚本只执行确定性环境检查、文件提取、规格校验、代码生成、Pytest 与报告编排，不调用外部 AI API。Word/Excel 需当前 Python 有 `python-docx`/`openpyxl`；如缺少依赖，可由 Agent 使用已可用的文档工具读取，不要宣称脚本已理解业务语义。

详细使用见 [一键工作流](references/one-click-workflow.md)、[规格格式](references/spec-format.md) 和 [运行指南](references/android-runtime.md)。只支持 Android 原生 UI；不实现 Web UI、API、iOS 或 Jenkins。核心操作失败应保留真实错误，不伪造结果。
