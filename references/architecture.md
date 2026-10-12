# 架构与扩展点

本 Skill 的可复用部分在 `src/android_appium_test/`。`config.py` 验证项目 YAML 和环境变量；`driver.py` 根据显式设备/App 键创建 UiAutomator2 会话；`page.py` 提供显式等待、交互、截图和错误传播；`data.py` 加载项目 JSON/YAML；`casegen.py` 从已确认规格生成业务目录；`runner.py` 执行 Pytest、保存 Allure 结果并按实际结果回填状态。

生成的被测项目目录包含自己的 `pages/`、`data/`、`tests/`、`conftest.py` 和 `case_catalog.json`。页面 ID、操作流程、账号、App 包名与设备标识只属于被测项目。生成的页面对象可进一步拆成多个页面类，测试方法可加入真实导航、等待或更具体的断言；Skill 核心不预设某款 App 的业务行为。

用例状态链为 `not_run` → Pytest/Allure 原始结果 → `case_results.json` 中的实际状态。`runner.py` 只匹配真实 Allure result；未匹配的用例继续是 `not_run`。Pytest 退出码与报告生成退出码分别记录，避免报告失败被当作运行成功。没有 Allure CLI 时保留原始结果并明确标记 HTML 未生成。

当前执行类型仅为 Android 原生 App UI。扩展新的 App 时修改项目规格、配置和项目内页面/测试文件；扩展 API、Web UI 或 Jenkins 时应建立独立模块与验证流程，不能把这些能力写成当前已支持。
