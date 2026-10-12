# Android 运行与报告

运行前需安装本 Skill 的 Python 依赖，并准备 Android SDK、已连接设备或模拟器、Appium Server 及 UiAutomator2 驱动。配置文件中的 Appium URL、设备名、UDID、包名和 Activity 必须来自实际环境；无通用默认值。敏感账号和令牌通过 `${ENV_NAME}` 引用，不写入配置或 ZIP。

`scripts/run_tests.py` 先校验配置及设备/App 选择，再创建独立时间戳目录，执行 Pytest，并将标准输出写入 `pytest.log`。结果目录包含 `allure-results/`、`artifacts/`、`run-summary.json` 和 `case_results.json`。用例状态只从实际 Allure 原始结果回填，未匹配的用例保持 `not_run`。若产生真实 Allure 原始结果且系统提供 Allure CLI，才尝试生成 `allure-report/`。`run-summary.json` 记录 Pytest、报告 CLI 和总体退出码；HTML 文件存在时才标记 `report_generated=true`。测试失败时仍保留结果并返回 Pytest 失败码；测试通过但已尝试的报告生成失败时返回报告错误码。未执行测试不会写成通过。

Allure CLI 是 HTML 报告的独立本机依赖。`allure-pytest` 负责生成原始结果；只有安装 Python 插件而没有 CLI 时，仍可归档原始数据，无法生成 HTML。浏览器自动打开功能不在批量运行入口中。

新项目页面对象继承 `BasePage`。元素定位超时会截图并抛出 `ElementLookupError`；点击与输入异常直接交给 Pytest 标记失败。不要在通用核心中加入固定坐标、固定等待、固定账号或特定 App 的元素 ID。若需要 WebView context 切换、Toast 检测或复杂手势，应在真实设备上验证后放入项目扩展。
