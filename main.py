import asyncio
import os
import logging
import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from keep_alive import start_http_server_sync, self_ping

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

COGS = [
    "cogs.leaderboard",
    "cogs.examiner",
    "cogs.general",
]


class CCExaminerBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        log.error(f"App command error: {error}", exc_info=error)
        embed = discord.Embed(
            title="Error",
            description="Something went wrong. Please try again.",
            color=discord.Color.red(),
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            pass

    async def setup_hook(self) -> None:
        try:
            await database.create_tables()
            log.info("Database tables initialized")
        except Exception as e:
            log.error(f"Failed to initialize database: {e}")

        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"Loaded cog: {cog}")
            except Exception as e:
                log.error(f"Failed to load cog {cog}: {e}")

        try:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info(f"Slash commands synced to guild {config.GUILD_ID}")
        except Exception as e:
            log.error(f"Failed to sync commands: {e}")

    async def close(self) -> None:
        log.info("Closing bot...")
        await super().close()

    async def on_ready(self) -> None:
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")


async def main() -> None:
    port = int(os.environ.get("PORT", 8080))
    start_http_server_sync(port)

    bot = CCExaminerBot()
    asyncio.create_task(self_ping())

    async with bot:
        try:
            await bot.start(config.DISCORD_TOKEN)
        except Exception as e:
            log.error(f"Failed to start bot: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
