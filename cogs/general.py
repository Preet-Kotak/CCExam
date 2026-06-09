import discord
from discord import app_commands
from discord.ext import commands
import database
import config
from utils.formatting import build_leaderboard_embed, build_show_score_embed, sort_districts

class ScorePaginator(discord.ui.View):
    def __init__(self, records: list, player: discord.Member | discord.User) -> None:
        super().__init__(timeout=300)
        
        self.records = records
        self.player = player
        self.page = 0
        page_btn = next((c for c in self.children if getattr(c, "custom_id", None) == "page_button"), None)
        if page_btn:
            page_btn.label = f"{len(self.records) - self.page}/{len(self.records)}"

    def _build_embed(self) -> discord.Embed:
        row = self.records[self.page]
        import json

        district_scores = (
            row["district_scores"]
            if isinstance(row["district_scores"], dict)
            else json.loads(row["district_scores"])
        )
        districts: list[str] = sort_districts(list(row["districts"]))
        return build_show_score_embed(
            season_name=row["month"],
            districts=districts,
            district_scores=district_scores,
            total_stars=row["total_stars"],
            total_percent=row["total_percent"],
            grade=row["grade"],
            page=self.page + 1,
            total_pages=len(self.records),
            player_name=self.player.display_name if self.player is not None else None,
            player_icon_url=(self.player.display_avatar.url if getattr(self.player, "display_avatar", None) is not None else None),
        )
    @discord.ui.button(label="⬅️Prev", style=discord.ButtonStyle.secondary)
    async def prev_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        
        if self.page < len(self.records) - 1:
            self.page += 1
        
        page_btn = next((c for c in self.children if getattr(c, "custom_id", None) == "page_button"), None)
        if page_btn:
            page_btn.label = f"{len(self.records) - self.page}/{len(self.records)}"
        await interaction.response.edit_message(embed=self._build_embed(), view=self)


    @discord.ui.button(label="Page", style=discord.ButtonStyle.secondary, disabled=True, custom_id="page_button")
    async def page_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        return

    @discord.ui.button(label="Next➡️", style=discord.ButtonStyle.secondary)
    async def next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.page > 0:
            self.page -= 1
        page_btn = next((c for c in self.children if getattr(c, "custom_id", None) == "page_button"), None)
        if page_btn:
            page_btn.label = f"{len(self.records) - self.page}/{len(self.records)}"
        await interaction.response.edit_message(embed=self._build_embed(), view=self)


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_examiner(self, member: discord.Member) -> bool:
        return any(r.id == config.CC_EXAMINER_ROLE_ID for r in member.roles)
    
    async def season_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        seasons = await database.get_all_seasons()
        choices = [
            app_commands.Choice(name=season["month"], value=season["month"])
            for season in seasons
            if current.lower() in season["month"].lower()
        ]
        return choices[:25] 
    
    async def district_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        districts = config.DISTRICTS
        choices = [
            app_commands.Choice(name=district, value=district)
            for district in districts
            if current.lower() in district.lower()
        ]
        return choices
    


    @app_commands.command(name="show_score", description="Show all recorded scores for a player.")
    @app_commands.describe(player="The player to look up")
    async def show_score(
        self, interaction: discord.Interaction, player: discord.Member
    ) -> None:
        await interaction.response.defer()
        records = await database.get_player_all_scores(player.id)
        if not records:
            await interaction.followup.send(
                f"No scores found for {player.mention}.", ephemeral=True
            )
            return

        view = ScorePaginator(records, player)
        embed = view._build_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=False)

    @app_commands.command(name="help", description="List available commands.")
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        is_examiner = (
            isinstance(interaction.user, discord.Member)
            and self._is_examiner(interaction.user)
        )

        embed = discord.Embed(title="CC Examiner Bot — Commands", color=discord.Color.blurple())

        if is_examiner:
            embed.add_field(
                name="CC Examiner Commands",
                value=(
                    "`/start` — Start a new season and choose 5 districts\n"
                    "`/add_link` — Add or replace a base link + screenshot for a district\n"
                    "`/submit_score` — Submit a score for a player\n"
                    "`/edit_score` — Edit an existing score for a player\n"
                    "`/delete_score` — Delete a player's score from the current season\n"
                    "`/show_bases` — Show all current base links and screenshots\n"
                    "`/end_exam` — Close the current season\n"
                    "`/delete_exam` — Delete an entire season and all its data\n"
                ),
                inline=False,
            )

        embed.add_field(
            name="Everyone",
            value=(
                "`/show_score` — View all recorded scores for a player\n"
                "`/leaderboard` — View the leaderboard for a season\n"
                "`/district_leaderboard` — View the leaderboard for a specific district and season\n"
                "`/help` — Show this help message\n"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="leaderboard", description="Show the leaderboard for a season.")
    @app_commands.describe(
        season="The season to view the leaderboard for"
    )
    @app_commands.autocomplete(season=season_autocomplete)
    async def leaderboard(
        self, interaction: discord.Interaction, season: str
    ) -> None:
        season_record = await database.get_season_by_name(season)
        if not season_record:
            await interaction.response.send_message(
                f"Season '{season}' was not found.", ephemeral=True
            )
            return

        scores = await database.get_all_scores(season_record["id"])
        embed = build_leaderboard_embed(
            season_name=season_record["month"],
            scores=scores,
            guild=interaction.guild,
            is_active=season_record["is_active"],
            show_stats=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="district_leaderboard", description="Show the leaderboard for a specific district and season.")
    @app_commands.describe(
        season="The season to view the leaderboard for",
        district="The district to view the leaderboard for"
    )
    @app_commands.autocomplete(season=season_autocomplete)
    @app_commands.autocomplete(district=district_autocomplete)  
    async def district_leaderboard(
        self, interaction: discord.Interaction, season: str, district: str
    ) -> None:
        season_record = await database.get_season_by_name(season)
        if not season_record:
            await interaction.response.send_message(
                f"Season '{season}' was not found.", ephemeral=True
            )
            return

        leaderboard = await database.get_district_leaderboard(season_record["id"], district)
        if not leaderboard:
            await interaction.response.send_message(
                f"No scores found for {district} in {season_record['month']}.", ephemeral=True
            )
            return

        lines = []
        for idx, entry in enumerate(leaderboard):
            player_name = None
            player_id = entry["player_id"]
            if interaction.guild is not None:
                member = interaction.guild.get_member(player_id)
                if member is not None:
                    player_name = member.display_name
            if player_name is None:
                user = await self.bot.fetch_user(player_id)
                player_name = user.name

            stars = int(entry["stars"])
            percent = int(entry["percent"])
            lines.append(
                f"#{idx+1} <@{player_name}> - {stars}⭐ {percent}%"
            )

        embed = discord.Embed(
            title=f"{district} Leaderboard | {season_record['month']}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
        


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GeneralCog(bot))