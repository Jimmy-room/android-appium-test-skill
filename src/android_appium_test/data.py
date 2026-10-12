"""读取被测项目自己的 JSON/YAML 参数化测试数据。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .config import ConfigError, _expand


def load_cases(path: str | Path, *, resolve_env: bool = True) -> list[dict[str, Any]]:
    """加载用例数据；收集阶段可暂不展开环境变量。"""
    data_path = Path(path)
    if not data_path.is_file():
        raise ConfigError(f"测试数据不存在：{data_path}")
    try:
        content = data_path.read_text(encoding="utf-8")
        if data_path.suffix.lower() == ".json":
            result = json.loads(content)
        elif data_path.suffix.lower() in {".yaml", ".yml"}:
            result = yaml.safe_load(content)
        else:
            raise ConfigError("测试数据只支持 JSON、YAML")
    except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"测试数据无法读取：{data_path}: {exc}") from exc
    if not isinstance(result, list) or not result or any(not isinstance(row, dict) for row in result):
        raise ConfigError("测试数据根节点必须是非空对象列表")
    return _expand(result) if resolve_env else result


def resolve_values(case: dict[str, Any]) -> dict[str, Any]:
    """在实际执行用例时展开环境变量，缺失则使该用例失败。"""
    return _expand(case)
