"""
Telegram integration.

Hermes Agent ships a native, multi-platform messaging gateway (CLI, Telegram,
Discord, Slack, WhatsApp sharing one context) - see Hermes docs for
`hermes gateway telegram --token $TELEGRAM_BOT_TOKEN`. That's the intended
path for the "using telegram to chat with the agents" eval criterion: once
this project's orchestrator is registered as a Hermes agent (see
orchestrator.py docstring + README "Wiring into Hermes"), Hermes's own
gateway handles the Telegram transport for you - you don't need to hand-roll
a bot.

This file is a minimal STANDALONE fallback (using python-telegram-bot)
in case you want to demo the pipeline over Telegram before Hermes's gateway
is fully wired, or want a lighter-weight bot dedicated just to this project.

Commands:
  /run <niche> <search terms...>   -> kicks off run_pipeline()
  /board                            -> shows current kanban snapshot
  /approve <card_id>                -> marks a card DONE after review
"""

import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from orchestrator import run_pipeline, approve_card
from kanban.board import KanbanBoard

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /run <niche> <search terms...>\ne.g. /run trading_signals trading signals, stock alerts")
        return
    niche = context.args[0]
    search_terms = " ".join(context.args[1:]).split(",") if len(context.args) > 1 else [niche]
    search_terms = [t.strip() for t in search_terms if t.strip()]

    await update.message.reply_text(f"Starting pipeline for '{niche}'... this can take a few minutes.")
    try:
        result = run_pipeline(niche=niche, search_terms=search_terms)
        await update.message.reply_text(
            f"Done. Card #{result['card_id']} is in REVIEW.\n"
            f"Ads scraped: {result['ads']['total_recent']}\n"
            f"Scripts generated: {result['scripts']['generated']}\n"
            f"Video: {result['video']}"
        )
    except Exception as e:
        await update.message.reply_text(f"Pipeline failed: {e}")


async def cmd_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    board = KanbanBoard()
    await update.message.reply_text(f"```\n{board.render_ascii()}\n```", parse_mode="MarkdownV2")


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /approve <card_id>")
        return
    card_id = int(context.args[0])
    approve_card(card_id)
    await update.message.reply_text(f"Card #{card_id} marked DONE.")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("board", cmd_board))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.run_polling()


if __name__ == "__main__":
    main()
