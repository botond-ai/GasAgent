import pytest

from infrastructure.tool_registry import ToolRegistry


def test_default_registry_has_tools():
    reg = ToolRegistry.default()
    descriptions = reg.get_descriptions()
    assert any("rag_search" in d for d in descriptions)
    assert any("jira_create" in d for d in descriptions)
    assert len(descriptions) >= 4


def test_execute_registered_tool():
    reg = ToolRegistry.default()
    result = reg.execute("calculator", expression="1+1")
    assert result["status"] == "success"
    assert result["tool"] == "calculator"


def test_register_custom_tool_and_schema():
    reg = ToolRegistry()

    def hello(name: str = "world"):
        return f"hello {name}"

    reg.register(
        name="hello",
        handler=hello,
        description="Say hello",
        schema={"type": "object", "properties": {"name": {"type": "string"}}}
    )

    schema = reg.get_schema("hello")
    assert "properties" in schema
    result = reg.execute("hello", name="tester")
    assert result["result"] == "hello tester"


def test_execute_missing_tool_raises():
    reg = ToolRegistry()
    with pytest.raises(ValueError):
        reg.get_schema("missing")
    with pytest.raises(ValueError):
        reg.execute("missing")
