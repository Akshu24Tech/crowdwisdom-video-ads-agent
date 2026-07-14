"""
MCP server for the CrowdWisdomTrading Video Ads pipeline.

Hermes Agent's real extension model is: (1) markdown skills for behavior/
workflow, and (2) MCP servers for anything Hermes doesn't have a native
tool for. It does NOT have a "register this Python function as a subagent"
API - that was wrong in an earlier draft of this project. This file is the
correct integration point: it exposes our three pipeline stages + kanban
board as MCP tools, which Hermes can then call like any other tool.

Wiring this into Hermes (once Hermes is installed):
    hermes mcp add crowdwisdom-ads --command "python mcp_server.py"
    (verify the exact `hermes mcp add` flags against `hermes mcp --help`
    in your installed version - CLI surface may have moved since these
    docs were written)

Then point Hermes at the skill in skills/crowdwisdom_ad_pipeline.skill.md
so it knows *when* and *in what order* to call these tools, and run:
    hermes gateway setup   # choose Telegram
    hermes gateway start
"""

import json
import asyncio
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from kanban.board import KanbanBoard
from agents import ads_manager, script_agent, video_agent

server = Server("crowdwisdom-ads-pipeline")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="scrape_and_rank_ads",
            description="Scrapes Meta Ad Library via Apify for the given niche/search terms, "
                        "filters to the last 30 days, ranks by days-running, and extracts "
                        "pain point / marketing concept / hook style per ad via LLM.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_terms": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["search_terms"],
            },
        ),
        Tool(
            name="generate_ad_scripts",
            description="Generates 3 script variants (pain-led, unique-data-led, "
                        "CWT-benefit-led) plus a hook per ad, using the most recent "
                        "scraped_ads.json. Includes a groundedness validator loop.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="render_video_ad",
            description="Renders a 30-60s video ad from the top generated script via "
                        "OpenMontage (or Remotion fallback).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_kanban_board",
            description="Returns the current kanban board state as ASCII, showing which "
                        "pipeline stage each ad-run card is in.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    board = KanbanBoard()

    if name == "scrape_and_rank_ads":
        result = ads_manager.run(search_terms=arguments["search_terms"])
        return [TextContent(type="text", text=json.dumps({
            "total_recent": result["total_recent"],
            "top_ads_count": len(result["top_ads"]),
        }))]

    if name == "generate_ad_scripts":
        result = script_agent.run()
        return [TextContent(type="text", text=json.dumps(result))]

    if name == "render_video_ad":
        result = video_agent.run()
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    if name == "get_kanban_board":
        return [TextContent(type="text", text=board.render_ascii())]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
