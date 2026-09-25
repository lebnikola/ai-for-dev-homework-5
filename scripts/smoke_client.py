import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "bazhov_resolve",
    "bazhov_get",
    "bazhov_search",
    "bazhov_context",
}


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable, args=["server.py"], cwd="."
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert names == EXPECTED_TOOLS, names
            schemas = {t.name: t.input_schema for t in tools.tools}
            assert "query" in schemas["bazhov_resolve"]["properties"]
            assert "id" in schemas["bazhov_get"]["properties"]
            assert "year_from" in schemas["bazhov_search"]["properties"]
            assert "theme" in schemas["bazhov_context"]["properties"]

            calls = [
                ("bazhov_resolve", {"query": "хозяйка медной горы"}),
                ("bazhov_get", {"id": "story:kamenny-tsvetok"}),
                (
                    "bazhov_search",
                    {"keywords": "жадность", "entity_type": "story", "year_from": 1936},
                ),
                ("bazhov_context", {"theme": "самоцветы"}),
            ]
            for name, args in calls:
                result = await session.call_tool(name, args)
                assert not result.is_error, (name, result.content)
                structured = result.structured_content
                assert structured is not None, f"{name}: no structuredContent"
                text_payload = json.loads(result.content[0].text)
                assert isinstance(text_payload, dict)
                print(f"OK {name}: {json.dumps(structured, ensure_ascii=False)[:160]}...")

            typo = await session.call_tool("bazhov_search", {"keywords": "кокований"})
            assert typo.structured_content["results"] == []
            assert typo.structured_content["candidates"], "expected candidates on miss"
            print("OK search-miss candidates:", [c["id"] for c in typo.structured_content["candidates"]])


if __name__ == "__main__":
    asyncio.run(main())
