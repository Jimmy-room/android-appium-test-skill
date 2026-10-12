# android-appium-test Skill 0.2.1

在 Codex 中提供 Android App 和测试用例，Skill 自动检查环境、读取真实 UI、生成独立 Page Object/数据/Pytest、在设备上执行并生成 Allure 报告。业务页面、数据和结果均放在独立运行目录，原项目和原 ZIP 不受影响。

## 安装

需要 Python 3.10+。在 Skill 根目录执行：

```powershell
python -m pip install -e .
```

Word/Excel 文件读取可安装 `python -m pip install -e ".[case-files]"`。生成 HTML 还需 Allure CLI；真实 Android UI 执行需 Android SDK、设备或模拟器、Appium Server 和 UiAutomator2 驱动。现有安装路径可保存至本机 profile，格式见 [示例](assets/local-profile.example.json)。脚本只启动已有服务，不自动安装软件。

## 日常使用

在 Codex 中直接说：“使用 android-appium-test Skill，测试我指定的 App，按照上传的测试用例自动执行，最后生成 Allure 报告。”提供 APK 或已安装包名与用例即可。Codex 会自行完成自然语言理解和页面取证；必要时只询问缺失的账号、关键预期、设备选择或危险操作授权。

统一入口分两步在 Agent 内部完成：

```powershell
python scripts/auto_test.py --app settings --cases assets/settings-display-case.md --profile <本机profile.json> --output <独立运行目录>
# 对自然语言，Codex 读取 needs_agent 的证据、写出经过核对的规格，然后执行：
python scripts/auto_test.py --resume <本次run目录> --spec <本次spec.json> --profile <本机profile.json> --open-report
```

若用例已经是规范 JSON/YAML，第一条命令可直接生成并执行。普通 Python 脚本不具备大模型语义理解；自然语言工作流必须由 Codex 依据 `SKILL.md` 编排。每次运行都会新建结果目录，不会覆盖历史失败。

若目标 App 未能保持前台，入口会先用 ADB 独立启动并保存本次 Logcat，识别真实 Activity、设备 API 与 App 最低 API。可单独运行 `python scripts/diagnose_startup.py --app <包名> --profile <本机profile.json> --output <新诊断目录>`。诊断完成不代表用例通过；启动被确认阻塞时入口会停止后续代码生成与执行。参见 [启动诊断](references/startup-diagnostics.md)。

## 结构化规格与旧入口

```powershell
python scripts/inspect_target.py <被测项目目录> --output target-inventory.json
python scripts/generate_cases.py assets/example_project/spec.yaml example-generated
python -m pytest --collect-only -q example-generated/tests
```

示例规格的包名、定位符和预期均为占位内容。真实执行前，先根据新 App 的需求与页面验证并修改规格，再准备 `config.yaml`、设备、服务与凭据。不得用示例配置直接声称 UI 测试通过。

```powershell
python scripts/run_tests.py example-generated --config <实际配置.yaml> --device <设备键> --app <App键> --output <结果目录>
```

用例规格字段见 [references/spec-format.md](references/spec-format.md)，运行与报告规则见 [references/android-runtime.md](references/android-runtime.md)。运行输出 `run-summary.json` 给出真实退出码和报告路径。添加新页面时，在被测项目目录创建继承 `BasePage` 的页面对象，并将测试数据放在该项目的 `data/`，不要修改 Skill 核心。

完整编排见 [一键工作流](references/one-click-workflow.md)，架构与扩展方式见 [架构说明](references/architecture.md)。验证证据和已知限制见 [VALIDATION.md](VALIDATION.md)。

## 测试范围

当前实现 Android App UI。API、浏览器 Web UI、iOS 和 Jenkins 集成尚未实现。没有设备或 Appium 服务时，可以验证配置、生成、语法与测试收集，但不能执行真实 UI 场景。
