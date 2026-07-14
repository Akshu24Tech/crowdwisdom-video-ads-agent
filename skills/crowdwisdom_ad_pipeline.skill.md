---
name: crowdwisdom-ad-pipeline
description: Runs the full CrowdWisdomTrading video ad pipeline - scrape competitor ads, extract pain points, write scripts, render video - and reports progress via the kanban board.
---

# CrowdWisdomTrading Ad Pipeline Skill

Use this skill when the user asks to "run the ad pipeline", "generate a video
ad for [niche]", or similar. This project connects via the `crowdwisdom-ads`
MCP server (tools: `scrape_and_rank_ads`, `generate_ad_scripts`,
`render_video_ad`, `get_kanban_board`).

## Workflow (loop through in order, do not skip steps)

1. Call `scrape_and_rank_ads` with the user's niche/product as search terms.
   Report the count of ads found in the last 30 days.
2. Call `get_kanban_board` and show the user the card moved to SCRAPING, then
   SCRIPTING once step 3 starts.
3. Call `generate_ad_scripts`. This step internally loops up to 3 times per
   script to validate groundedness (the script must actually address the
   identified pain point and not invent stats) - if it reports
   `revision_loops > 1` for any script, mention that a revision happened.
4. Call `render_video_ad`. This may take several minutes - tell the user to
   expect a wait, don't repeat the call while it's running.
5. Call `get_kanban_board` again to confirm the card reached REVIEW.
6. Summarize for the user: how many ads were analyzed, the 3 script angles
   generated, the hook line, and the final video output path. Ask the user
   to review before it's marked DONE.

## Error handling

If any MCP call returns an error, do not silently retry more than once.
Report the specific failure (e.g. "Apify actor timed out" or "OpenMontage
render failed, falling back to Remotion") - the pipeline is designed to
surface failures on the kanban card rather than hide them.

## When NOT to use this skill

Don't invoke this for general marketing copywriting questions unrelated to
the CrowdWisdomTrading ad pipeline - this skill is scoped to running the
actual scrape -> script -> video pipeline via its MCP tools.
