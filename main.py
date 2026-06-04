import asyncio
import os
import sys
import traceback
import discord
from discord.ext import commands

try:
    import config
    import database
except Exception as e:
    print(f"[ERROR] Failed to import config or database: {e}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)

try:
    from keep_alive import start_http_server_sync, self_ping
except Exception as e:
    print(f"[ERROR] Failed to import keep_alive: {e}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)

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
        print("[Setup] Starting setup_hook...", flush=True)
        try:
            await database.create_tables()
            print("[Setup] Database tables created", flush=True)
        except Exception as e:
            print(f"[Setup] Failed to create tables: {e}", flush=True)
            traceback.print_exc()
        
        for cog in COGS:
            try:
                await self.load_extension(cog)
                print(f"[Cog] Loaded {cog}", flush=True)
            except Exception as e:
                print(f"[Cog] Failed to load {cog}: {e}", flush=True)
                traceback.print_exc()
        
        try:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"[Bot] Slash commands synced to guild {config.GUILD_ID}.", flush=True)
        except Exception as e:
            print(f"[Bot] Failed to sync commands: {e}", flush=True)
            traceback.print_exc()
        
        asyncio.create_task(self_ping())
    
    async def on_ready(self) -> None:
        print(f"[Bot] Logged in as {self.user} (ID: {self.user.id})")

async def main() -> None:
    port=int(os.environ.get("PORT", 8080))
    start_http_server_sync(port)
    print(f"[Main] HTTP server requested on port {port}")
    # Diagnostic info (do not print secrets)
    print(f"[Main] DISCORD_TOKEN set: {bool(os.environ.get('DISCORD_TOKEN'))}")
    print(f"[Main] DATABASE_URL set: {bool(os.environ.get('DATABASE_URL'))}")
    print(f"[Main] RENDER_URL set: {bool(os.environ.get('RENDER_URL'))}")
    print(f"[Main] Python version: {os.sys.version.splitlines()[0]}")
    bot = CCExaminerBot()
    async with bot:
        print("[Bot] Starting bot...")
        try:
            await bot.start(config.DISCORD_TOKEN)
        except Exception as exc:
            print(f"[Bot] Failed to start: {exc}")
            raise
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[FATAL ERROR] {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
