#!/usr/bin/env python3
"""
RTanks Online Discord Bot
Main entry point for the Discord bot application.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from aiohttp import web

from bot import RTanksBot

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", lambda request: web.Response(text="Bot is alive!"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

async def main():
    """Main function to start the bot."""
    # Get Discord token from environment
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        return
    
        await start_web_server()  # Start ping server

    # Create and run the bot
    bot = RTanksBot()
    
    try:
        logger.info("Starting RTanks Discord Bot...")
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot encountered an error: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
