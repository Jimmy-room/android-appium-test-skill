"""启动诊断的证据判断与无设备单元测试。"""

import json

from android_appium_test import startup_diagnostics as diagnosis


def test_requirements_and_incompatible_version():
    metadata = diagnosis.parse_package_requirements(
        "versionCode=1925 minSdk=29 targetSdk=34\nversionName=5.163.6")
    assert metadata == {"versionCode": 1925, "minSdk": 29,
                        "targetSdk": 34, "versionName": "5.163.6"}
    assert diagnosis.classify_startup(28, metadata, "", "launcher", "com.duolingo") == \
        "incompatible_android_version"


def test_target_process_fatal_is_not_success():
    log = "FATAL EXCEPTION: main\nProcess: com.duolingo, PID: 123\nNoSuchMethodError"
    assert diagnosis.classify_startup(34, {}, log, "com.duolingo", "com.duolingo") == "app_crash"
    assert diagnosis.classify_startup(34, {}, "", "com.duolingo", "com.duolingo") == \
        "foreground_unverified"


def test_collects_marker_scoped_log_without_appium(monkeypatch, tmp_path):
    monkeypatch.setattr(diagnosis, "resolve_installed", lambda *args: ("com.example", ".Main"))
    commands = []

    def fake_command(argv, timeout=30):
        commands.append(argv)
        if "ro.build.version.sdk" in argv:
            return "28"
        if "dumpsys" in argv and "package" in argv:
            return "versionCode=1 minSdk=29 targetSdk=34"
        if "window" in argv:
            return "mCurrentFocus=Window{com.android.launcher3}"
        if "logcat" in argv:
            marker = next(x[-1] for x in commands if "CODEX_STARTUP_DIAG" in x)
            return f"old unrelated error\n{marker}\nFATAL EXCEPTION: main\nProcess: com.example, PID: 1"
        return "Starting: Intent"

    monkeypatch.setattr(diagnosis, "run_command", fake_command)
    monkeypatch.setattr(diagnosis.time, "sleep", lambda _: None)
    result = diagnosis.diagnose_startup("adb", "serial", "com.example", tmp_path)
    assert result["classification"] == "incompatible_android_version"
    assert result["resolved_activity"] == ".Main"
    assert "old unrelated error" not in (tmp_path / "adb-startup-logcat.txt").read_text()
    assert json.loads((tmp_path / "startup-diagnosis.json").read_text())["device_api"] == 28
    assert not any("appium" in " ".join(x).lower() for x in commands)
