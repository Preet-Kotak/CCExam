import discord
from discord.ext import commands
import database
import config
from utils.formatting import build_leaderboard_embed
import asyncio
from utils.formatting import build_leaderboard_embed

class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._update_task = None
        self._pending_season = None

    async def _scheduled_update(self) -> None:
        await asyncio.sleep(3)  # Debounce delay
        season = self._pending_season
        if season is None:
            return

        msg_id = season["leaderboard_message_id"]
        chan_id = season["leaderboard_channel_id"]
        if not msg_id or not chan_id:
            return

        channel = self.bot.get_channel(chan_id)
        if channel is None:
            channel = getattr(self.bot, "cached_channels", {}).get(chan_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(chan_id)
                    if hasattr(self.bot, "cached_channels"):
                        self.bot.cached_channels[chan_id] = channel
                except Exception:
                    return

        # Use partial message to avoid fetching the message object
        message = channel.get_partial_message(msg_id)
        scores = await database.get_all_scores(season["id"])
        embed = build_leaderboard_embed(season["month"], scores, channel.guild, season["is_active"])
        try:
            await message.edit(embed=embed)
        except discord.NotFound:
            pass
        except discord.HTTPException:
            pass

    async def update_leaderboard(self, season: dict | None = None) -> None:
        """Queue an update for the pinned leaderboard message."""
        if season is None:
            season = await database.get_active_season()
        if season is None:
            return

        self._pending_season = season
        if self._update_task is None or self._update_task.done():
            self._update_task = self.bot.loop.create_task(self._scheduled_update())

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))