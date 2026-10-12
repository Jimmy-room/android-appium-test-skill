import sys
from pathlib import Path


# 从源码目录导入，不依赖安装到全局 Python。
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
