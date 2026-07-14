"""
Orchestrator - the Hermes coordinator agent.

Owns the kanban board and delegates each stage to a subagent:
  Ads Manager -> Script Agent -> Video Agent

This is written as a plain Python coordinator so the logic is testable
without Hermes running. To actually run it *as* a Hermes agent (so you get
delegation tracing, the skill system, and the Telegram gateway for free),
wrap `run_pipeline` as a Hermes tool/skill and register the three stage
functions as sub-agents in Hermes's AIAgent config - see README.md
"Wiring into Hermes" section for the exact registration snippet once you
have Hermes installed locally (its setup is a single curl per the docs).
"""

import json
import traceback
from pathlib import Path

from kanban.board import KanbanBoard
from agents import ads_manager, script_agent, video_agent

DATA_DIR = Path(__file__).parent / "data"


def run_pipeline(niche: str, search_terms: list[str]) -> dict:
    board = KanbanBoard()
    card_id = board.create_card(title=f"{niche}-run", payload={"niche": niche, "search_terms": search_terms})

    try:
        # Stage 1: Ads Manager
        board.move_card(card_id, "SCRAPING", note="Ads Manager: scraping Meta Ad Library via Apify")
        ads_result = ads_manager.run(search_terms=search_terms)
        board.update_payload(card_id, {"ads_summary": {
            "total_scraped": ads_result["total_scraped"],
            "total_recent": ads_result["total_recent"],
        }})

        # Stage 2: Script Agent
        board.move_card(card_id, "SCRIPTING", note="Script Agent: generating 3 script variants + hooks")
        script_result = script_agent.run()
        board.update_payload(card_id, {"scripts_summary": script_result})

        # Stage 3: Video Agent
        board.move_card(card_id, "VIDEO", note="Video Agent: rendering via OpenMontage/Remotion")
        video_result = video_agent.run()
        board.update_payload(card_id, {"video_summary": video_result})

        # Human review checkpoint
        board.move_card(card_id, "REVIEW", note="Awaiting human review before marking done")

        return {
            "card_id": card_id,
            "status": "awaiting_review",
            "ads": ads_result,
            "scripts": script_result,
            "video": video_result,
        }

    except Exception as e:
        board.update_payload(card_id, {"error": str(e), "traceback": traceback.format_exc()})
        board.move_card(card_id, "TODO", note=f"Failed: {e}")
        raise


def approve_card(card_id: int):
    """Call this once you've reviewed the output - moves card to DONE."""
    board = KanbanBoard()
    board.move_card(card_id, "DONE", note="Human approved")


def print_board():
    board = KanbanBoard()
    print(board.render_ascii())


if __name__ == "__main__":
    result = run_pipeline(
        niche="trading_signals",
        search_terms=["trading signals", "stock alerts", "day trading community"],
    )
    print(json.dumps({k: v for k, v in result.items() if k != "ads"}, indent=2, default=str))
    print_board()
