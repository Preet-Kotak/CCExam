import asyncio
import os
import discord
from discord.ext import commands
import config
import database

from keep_alive import start_http_server_sync, self_ping

COGS = [
    "cogs.leaderboard",
    "cogs.examiner",
    "cogs.general",
]
intents = discord.Intents.default()
intents.members = True

class CCExaminerBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await database.create_tables()
        for cog in COGS:
            await self.load_extension(cog)
            print(f"[Cog] Loaded {cog}")
        guild = discord.Object(id=config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"[Bot] Slash commands synced to guild {config.GUILD_ID}.")
        asyncio.create_task(self_ping())
    
    async def on_ready(self) -> None:
        print(f"[Bot] Logged in as {self.user} (ID: {self.user.id})")

async def main() -> None:
    port=int(os.environ.get("PORT", 8080))
    start_http_server_sync(port)
    bot = CCExaminerBot()
    async with bot:
        print("[Bot] Starting bot...")
        try:
            await bot.start(config.DISCORD_TOKEN)
        except Exception as exc:
            print(f"[Bot] Failed to start: {exc}")
            raise
        
if __name__ == "__main__":
    asyncio.run(main())
