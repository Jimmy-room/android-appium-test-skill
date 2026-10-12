# Android App 启动失败诊断

运行 `python scripts/diagnose_startup.py --app <真实包名> --profile <本机配置JSON> --output <新的空目录>`。脚本从设备解析启动 Activity，读取设备 API 与已安装 App 的 `minSdk`，写入唯一 Logcat 标记后用 `adb shell am start -n` 独立启动。随后记录前台窗口和标记后的原始 Logcat。诊断无需 Appium；退出码 0 仅表示证据收集完成，不代表 App 启动成功。

读取 `startup-diagnosis.json` 的 `classification`、`package_requirements`、`foreground`、`resolved_activity`，再对照 `adb-startup-logcat.txt` 的 `FATAL EXCEPTION`、`AndroidRuntime`、`ActivityManager`、`ActivityTaskManager`。若标记未出现在截取日志中，`log_marker_found=false`，日志归因存在不确定性，应增加采集范围重新诊断。

分类：`incompatible_android_version` 表示设备 API 低于已安装 App 的 `minSdk`；`app_crash` 表示 ADB 独立启动时目标进程崩溃；`adb_launch_error` 表示启动命令失败；`not_foreground` 表示未观察到目标前台；`foreground_unverified` 仅表示包名出现在前台，尚需 UI 与业务断言。若 ADB 正常而 Appium 异常，再查 Driver 配置；若真实 Activity 与测试配置不同，修正配置。不能通过放松前台断言掩盖崩溃。

对版本不兼容，选择运行符合 `minSdk` 的 Android 设备，或由用户明确授权换用支持当前 Android 的官方 APK；不得自行清数据、卸载、重装或更换 APK。每次修复后重新执行用例，使用新的 Allure 结果目录并保留原始失败记录。
