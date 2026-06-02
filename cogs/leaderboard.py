import discord
from discord.ext import commands
import database
import config
from utils.formatting import build_leaderboard_embed

class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def update_leaderboard(self, season: dict | None = None) -> None:
        """Fetch scores and edit the pinned leaderboard message."""
        if season is None:
            season = await database.get_active_season()
        if season is None:
            return

        msg_id = season["leaderboard_message_id"]
        chan_id = season["leaderboard_channel_id"]
        if not msg_id or not chan_id:
            return

        channel = self.bot.get_channel(chan_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(chan_id)
            except Exception:
                return

        try:
            message = await channel.fetch_message(msg_id)
        except discord.NotFound:
            return

        scores = await database.get_all_scores(season["id"])
        embed = build_leaderboard_embed(season["month"], scores, channel.guild)
        await message.edit(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))