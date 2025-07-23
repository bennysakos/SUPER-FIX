"""
RTanks Online Discord Bot
Core bot functionality with slash commands.
"""

import discord
from discord.ext import commands
import aiohttp
import asyncio
import time
import psutil
import os
from datetime import datetime, timedelta
import logging

from scraper import RTanksScraper
from utils import format_number, format_exact_number, get_rank_emoji, format_duration
from config import RANK_EMOJIS, PREMIUM_EMOJI, GOLD_BOX_EMOJI, RTANKS_BASE_URL

logger = logging.getLogger(__name__)

class RTanksBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        # Bot statistics
        self.start_time = datetime.now()
        self.commands_processed = 0
        self.scraping_successes = 0
        self.scraping_failures = 0
        self.total_scraping_time = 0.0
        
        # Initialize scraper
        self.scraper = RTanksScraper()
    
    async def setup_hook(self):
        """Setup hook called when bot is starting up."""
        # Register commands with the command tree
        self.tree.command(name="player", description="Get RTanks player statistics")(self.player_command_handler)
        self.tree.command(name="botstats", description="Display bot performance statistics")(self.botstats_command_handler)
        
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Set bot status
        activity = discord.Game(name="RTanks Online")
        await self.change_presence(activity=activity)

    @discord.app_commands.describe(username="RTanks player username to lookup")
    async def player_command_handler(self, interaction: discord.Interaction, username: str):
        """Slash command to get player statistics."""
        await interaction.response.defer()
        
        start_time = time.time()
        self.commands_processed += 1
        
        try:
            # Scrape player data
            player_data = await self.scraper.get_player_data(username.strip())
            
            if not player_data:
                embed = discord.Embed(
                    title="❌ Player Not Found",
                    description=f"Could not find player data for `{username}`. Please check the username and try again.",
                    color=0xff0000
                )
                await interaction.followup.send(embed=embed)
                self.scraping_failures += 1
                return
            
            # Create player embed
            embed = await self._create_player_embed(player_data)
            await interaction.followup.send(embed=embed)
            
            # Update statistics
            scraping_time = time.time() - start_time
            self.total_scraping_time += scraping_time
            self.scraping_successes += 1
            
        except Exception as e:
            logger.error(f"Error processing player command: {e}")
            
            embed = discord.Embed(
                title="⚠️ Error",
                description="An error occurred while fetching player data. The RTanks website might be temporarily unavailable.",
                color=0xffa500
            )
            await interaction.followup.send(embed=embed)
            self.scraping_failures += 1

    async def botstats_command_handler(self, interaction: discord.Interaction):
        """Slash command to display bot statistics."""
        await interaction.response.defer()
        
        self.commands_processed += 1
        
        # Calculate bot latency
        bot_latency = round(self.latency * 1000, 2)
        
        # Calculate average scraping latency
        avg_scraping_latency = 0
        if self.scraping_successes > 0:
            avg_scraping_latency = round((self.total_scraping_time / self.scraping_successes) * 1000, 2)
        
        # Calculate uptime
        uptime = datetime.now() - self.start_time
        uptime_str = format_duration(uptime.total_seconds())
        
        # Get system stats
        process = psutil.Process(os.getpid())
        memory_usage = round(process.memory_info().rss / 1024 / 1024, 2)  # MB
        cpu_usage = round(process.cpu_percent(interval=1), 1)
        
        # Calculate success rate
        total_scrapes = self.scraping_successes + self.scraping_failures
        success_rate = 0
        if total_scrapes > 0:
            success_rate = round((self.scraping_successes / total_scrapes) * 100, 1)
        
        embed = discord.Embed(
            title="🤖 Bot Statistics",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        # Performance metrics
        embed.add_field(
            name="📡 Latency",
            value=f"**Discord API:** {bot_latency}ms\n**Scraping Avg:** {avg_scraping_latency}ms",
            inline=True
        )
        
        embed.add_field(
            name="⏱️ Uptime",
            value=uptime_str,
            inline=True
        )
        
        embed.add_field(
            name="🌐 Servers",
            value=f"{len(self.guilds)}",
            inline=True
        )
        
        # Command statistics
        embed.add_field(
            name="📊 Commands",
            value=f"**Total Processed:** {format_number(self.commands_processed)}\n**Success Rate:** {success_rate}%",
            inline=True
        )
        
        # Scraping statistics
        embed.add_field(
            name="🔍 Scraping Stats",
            value=f"**Successful:** {format_number(self.scraping_successes)}\n**Failed:** {format_number(self.scraping_failures)}",
            inline=True
        )
        
        # System resources
        embed.add_field(
            name="💻 System Resources",
            value=f"**Memory:** {memory_usage} MB\n**CPU:** {cpu_usage}%",
            inline=True
        )
        
        # Website status
        website_status = await self._check_website_status()
        embed.add_field(
            name="🌍 Website Status",
            value=website_status,
            inline=False
        )
        
        embed.set_footer(text="RTanks Online Bot", icon_url=self.user.display_avatar.url if self.user else None)
        
        await interaction.followup.send(embed=embed)

        async def _create_player_embed(self, player_data):
        """Create a formatted embed for player data."""
        # Create embed with activity status
        activity_status = "Online" if player_data['is_online'] else "Offline"
        profile_url = f"{RTANKS_BASE_URL}/user/{player_data['username']}"
        embed = discord.Embed(
            title=f"{player_data['username']}",
            url=profile_url,
            description=f"**Activity:** {activity_status}",
            color=0x00ff00 if player_data['is_online'] else 0x808080,
            timestamp=datetime.now()
        )
        
        # Player rank and basic info - make rank emoji bigger
        rank_emoji = get_rank_emoji(player_data['rank'])
        
        # Extract the emoji ID from the custom Discord emoji and use it as thumbnail
        import re
        emoji_match = re.search(r':(\d+)>', rank_emoji)
        if emoji_match:
            emoji_id = emoji_match.group(1)
            emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
            embed.set_thumbnail(url=emoji_url)
        
        # Rank field with just the rank name, no emoji
        embed.add_field(
            name="Rank",
            value=f"**{player_data['rank']}**",
            inline=True
        )
        
        # Experience - show current/max format like "105613/125000"
        if 'max_experience' in player_data and player_data['max_experience']:
            exp_display = f"{format_exact_number(player_data['experience'])}/{format_exact_number(player_data['max_experience'])}"
        else:
            exp_display = f"{format_exact_number(player_data['experience'])}"
        
        embed.add_field(
            name="Experience",
            value=exp_display,
            inline=True
        )
        
        # Premium status - always show premium emoji
        premium_status = "Yes" if player_data['premium'] else "No"
        embed.add_field(
            name="Premium",
            value=f"{PREMIUM_EMOJI} {premium_status}",
            inline=True
        )
        
        # Combat Stats - remove non-custom emojis
        combat_stats = (
            f"**Kills:** {format_exact_number(player_data['kills'])}\n"
            f"**Deaths:** {format_exact_number(player_data['deaths'])}\n"
            f"**K/D:** {player_data['kd_ratio']}"
        )
        embed.add_field(
            name="Combat Stats",
            value=combat_stats,
            inline=True
        )
        
        # Other Stats - always show gold box emoji
        other_stats = (
            f"{GOLD_BOX_EMOJI} **Gold Boxes:** {player_data['gold_boxes']}\n"
            f"**Group:** {player_data['group']}"
        )
        embed.add_field(
            name="Other Stats",
            value=other_stats,
            inline=True
        )
        
        # Equipment - show all equipment with exact modification levels including protections
        if player_data['equipment']:
            equipment_text = ""
            
            if player_data['equipment'].get('turrets'):
                turrets = ", ".join(player_data['equipment']['turrets'])  # Show all turrets
                equipment_text += f"**Turrets:** {turrets}\n"
            
            if player_data['equipment'].get('hulls'):
                hulls = ", ".join(player_data['equipment']['hulls'])  # Show all hulls
                equipment_text += f"**Hulls:** {hulls}\n"
            
            # Add protections section
            if player_data['equipment'].get('protections'):
                protections = ", ".join(player_data['equipment']['protections'])
                equipment_text += f"**Protections:** {protections}"
            else:
                equipment_text += f"**Protections:** None"
            
            if equipment_text:
                embed.add_field(
                    name="Equipment",
                    value=equipment_text,
                    inline=False
                )
        
        embed.set_footer(text="Data from ratings.ranked-rtanks.online")
        return embed

        

    async def _check_website_status(self):
        """Check if the RTanks website is accessible."""
        try:
            start_time = time.time()
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get('https://ratings.ranked-rtanks.online/') as response:
                    response_time = round((time.time() - start_time) * 1000, 2)
                    if response.status == 200:
                        return f"🟢 Online ({response_time}ms)"
                    else:
                        return f"🟡 Partial ({response.status})"
        except Exception:
            return "🔴 Offline"

    async def on_command_error(self, ctx, error):
        """Global error handler."""
        logger.error(f"Command error: {error}")
        
    async def close(self):
        """Clean up when bot is closing."""
        await self.scraper.close()
        await super().close()
