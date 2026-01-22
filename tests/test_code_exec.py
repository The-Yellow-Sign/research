
import pytest

from src.application.tools.code_exec import CodeExecTool


@pytest.fixture
def code_tool():
    return CodeExecTool()

@pytest.mark.asyncio
async def test_valid_code(code_tool):
    code = "result = 2 + 2"
    res = await code_tool.execute(code)
    assert res.success is True
    assert "4" in res.data

@pytest.mark.asyncio
async def test_valid_math(code_tool):
    code = "import math\nresult = math.sqrt(16)"
    res = await code_tool.execute(code)
    assert res.success is True
    assert "4.0" in res.data

@pytest.mark.asyncio
async def test_restricted_import(code_tool):
    code = "import os\nresult = os.getcwd()"
    res = await code_tool.execute(code)
    assert res.success is False
    assert "запрещён" in res.error

@pytest.mark.asyncio
async def test_infinite_loop(code_tool):
    # Shorten timeout for test
    code_tool.TIMEOUT_SEC = 0.1
    code = "import time\ntime.sleep(1)"
    res = await code_tool.execute(code)
    assert res.success is False
    assert "Превышен лимит времени" in res.error

@pytest.mark.asyncio
async def test_output_formatting(code_tool):
    code = "print('Hello')\nresult = 'World'"
    res = await code_tool.execute(code)
    assert "Hello" in res.data
    assert "result = World" in res.data
