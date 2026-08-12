import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def suite_inputs() -> Path:
    """外部验收测试套件输入目录（存在时使用；不存在则跳过相关测试）。"""
    p = Path(
        r"C:\Users\kunyu\Downloads\markitdown_converter_test_suite_v2"
        r"\markitdown_converter_test_suite_v2\inputs"
    )
    return p if p.is_dir() else Path("__missing_suite__")
