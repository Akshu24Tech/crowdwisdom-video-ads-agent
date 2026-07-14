# CrowdWisdomTrading Video Ads Agent

A Hermes-based multi-agent pipeline that scrapes successful Meta ads in a niche,
extracts their marketing psychology, writes three grounded ad scripts for
CrowdWisdomTrading, and renders a 30-60s video ad from the winning script.

## Architecture

```
Telegram (or CLI) -> Orchestrator (Hermes coordinator)
                          |
        +-----------------+-----------------+
        v                 v                 v
  Ads Manager       Script Agent       Video Agent
  (Apify scrape,    (3 script types    (OpenMontage or
   pain extraction)  + hook +          Remotion render)
                      groundedness
                      validator loop)
        |                 |                 |
        +--------- Kanban board (SQLite) ---+
                    TODO -> SCRAPING -> SCRIPTING -> VIDEO -> REVIEW -> DONE
```

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
```

You'll need:
- **Apify token** - use a scoped/free-tier account, not a paid one (see note below)
- **OpenRouter API key** - openrouter.ai
- **A Meta Ad Library scraper actor** - search "Meta Ad Library" or "Facebook Ads Scraper" in the Apify store, pick a free/cheap one, set its ID as `APIFY_META_ADS_ACTOR`
- **OpenMontage cloned locally** (`git clone https://github.com/calesthio/OpenMontage`) OR a scaffolded Remotion project - see `agents/video_agent.py` docstring for why this is an either/or choice

## Running it standalone (no Hermes/Telegram yet)

```bash
python orchestrator.py
```

This runs the full pipeline once with hardcoded search terms and prints the
kanban board state at the end. Good for verifying each stage works before
wiring Telegram/Hermes on top.

## Wiring into Hermes

Hermes Agent (Nous Research) extends itself two ways: **MCP servers** for
new capabilities, and **markdown skills** (agentskills.io standard) for
workflow/behavior. There's no "register this Python function as a
subagent" API - `mcp_server.py` and `skills/crowdwisdom_ad_pipeline.skill.md`
in this repo are the actual integration points:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
hermes setup                                   # configure OpenRouter/Nous Portal + model
hermes mcp add crowdwisdom-ads --command "python mcp_server.py"
                                                # verify exact flags: `hermes mcp --help`
                                                # (CLI surface may have shifted since docs)
hermes gateway setup                           # choose Telegram, follow the OAuth/token flow
hermes gateway start
```

Copy `skills/crowdwisdom_ad_pipeline.skill.md` into wherever your Hermes
install expects custom skills (check `hermes doctor` output or the Skills
docs for the exact path - typically under `~/.hermes/skills/`). Once loaded,
message the Telegram bot: "run the ad pipeline for trading signals" - Hermes
reads the skill, calls the four MCP tools in order, and reports kanban
progress back through the same chat. This satisfies "loops and skills" and
"telegram" together, since it's one skill driving a multi-step tool-call
loop, not three separate scripts glued together by hand.

If MCP/skill wiring eats too much of your timeline, `telegram_bot.py` in
this repo is a standalone fallback (`python-telegram-bot`) exposing `/run`,
`/board`, `/approve` directly against the same `orchestrator.py` - it
demonstrates the same Telegram-driven workflow without depending on
Hermes's gateway specifically.

## Video rendering note

OpenMontage (github.com/calesthio/OpenMontage) is agent-driven - it expects
an AI coding assistant reading its skill files and calling its tools, not a
plain `import` call. `video_agent.py` shells out to it via subprocess and
documents exactly where to verify the real CLI syntax against the cloned
repo. If that integration proves too heavy inside the timeline, the same
file falls back to a Remotion-based render path (more mature, purely
programmatic). Ship whichever actually renders a video - the brief asks for
the output, not a specific tool at all costs.

## Groundedness validator (the differentiator)

`script_agent.py` includes a lightweight validation loop (capped at 3
iterations) that checks each generated script actually addresses the
identified pain point and doesn't invent CrowdWisdomTrading stats beyond
what's listed in `CWT_UNIQUE_DATA_POINTS`. This isn't required by the brief
but demonstrates the reliability/verification layer this candidate brings
to agent pipelines beyond just "generate and ship."

## Submission checklist

- [ ] GitHub repo link
- [ ] Apify token - **use a scoped/free-tier token**, not one tied to any
      paid account or other production credentials
- [ ] Video recording of the kanban board updating live through a full run
      (screen-record `orchestrator.py` running, or the Telegram `/board`
      output updating turn by turn)
- [ ] `.md` output of agent reasoning/skill traces (Hermes can export this;
      if running standalone, `data/scripts.json` + the kanban `log` field
      per card cover the same ground - format into markdown before sending)

## Repo layout

```
orchestrator.py         # Hermes coordinator, ties all stages together
agents/
  ads_manager.py        # Apify scrape + ranking + pain/concept extraction
  script_agent.py        # 3 script types + hook + groundedness validator
  video_agent.py          # OpenMontage (primary) / Remotion (fallback) render
kanban/board.py          # SQLite-backed kanban board
telegram_bot.py           # Standalone Telegram fallback (if not using Hermes gateway)
data/                     # scraped_ads.json, scripts.json, video_outputs.json, outputs/
```
