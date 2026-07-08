import json
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
import config
import database
from link_checker import get_district_name_from_link, is_valid_coc_link
from utils.formatting import build_score_embed, sort_districts
from utils.validators import parse_score, calculate_totals

def examiner_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("This command can only be used in a server.")
        if not any(r.id == config.CC_EXAMINER_ROLE_ID for r in interaction.user.roles):
            raise app_commands.CheckFailure("You need the CC Examiner role to use this command.")
        return True
    return app_commands.check(predicate)

async def get_cached_channel(guild: discord.Guild, channel_id: int, bot: discord.Client):
    channel = guild.get_channel(channel_id)
    if channel is None:
        channel = getattr(bot, "cached_channels", {}).get(channel_id)
        if channel is None:
            channel = await guild.fetch_channel(channel_id)
            if hasattr(bot, "cached_channels"):
                bot.cached_channels[channel_id] = channel
    return channel

# Start Modal
class DistrictSelectView(discord.ui.View):

    def __init__(self, month: str, interaction: discord.Interaction) -> None:
        super().__init__(timeout=180)
        self.month = month
        self.original_interaction = interaction
        # use a single multi-select so we don't exceed the 5 action-row limit
        self.selections: list[str] = []

        options = [discord.SelectOption(label=d, value=d) for d in config.DISTRICTS]
        select = discord.ui.Select(
            placeholder="Select 5 districts",
            options=options,
            custom_id="districts_select",
            min_values=5,
            max_values=5,
        )
        select.callback = self._select_callback
        self.add_item(select)

    async def _select_callback(self, interaction: discord.Interaction) -> None:
        self.selections = interaction.data.get("values", [])
        await interaction.response.defer()

    @discord.ui.button(label="Confirm Season", style=discord.ButtonStyle.success, row=1)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        chosen = sort_districts([s for s in self.selections if s is not None])
        if len(chosen) < 5:
            await interaction.response.send_message(
                "Please select all 5 districts before confirming.", ephemeral=True
            )
            return
        if len(set(chosen)) < 5:
            await interaction.response.send_message(
                "All 5 districts must be unique.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            existing = await database.get_active_season()
            if existing:
                await interaction.followup.send(
                    f"Season **{existing['month']}** is already active. End it first with `/end_season`.",
                    ephemeral=True,
                )
                return

            season = await database.create_season(self.month, chosen)

            lb_channel = await get_cached_channel(interaction.guild, config.LEADERBOARD_CHANNEL_ID, interaction.client)
            embed = discord.Embed(
                title=f"🏆 CC Exam Live Leaderboard | {self.month}",
                description="_No scores submitted yet._",
                color=discord.Color.gold(),
            )
            # Check bot permissions in the target channel before sending
            try:
                bot_member = interaction.guild.me
                perms = lb_channel.permissions_for(bot_member) if bot_member is not None else None
                if perms is None or not (perms.view_channel and perms.send_messages and perms.embed_links):
                    await interaction.followup.send(
                        f"Bot missing permissions in channel <#{lb_channel.id}>. Required: View Channels, Send Messages, Embed Links.\n"
                        f"Current: view_channel={getattr(perms, 'view_channel', None)}, send_messages={getattr(perms, 'send_messages', None)}, embed_links={getattr(perms, 'embed_links', None)}",
                        ephemeral=True,
                    )
                    return

                lb_msg = await lb_channel.send(embed=embed)
                await database.save_leaderboard_message(season["id"], lb_msg.id, lb_channel.id)
            except discord.Forbidden:
                await interaction.followup.send(
                    f"Missing access (403) to channel <#{lb_channel.id}>. Check the bot's permissions and channel overwrites.",
                    ephemeral=True,
                )
                return
        except Exception as exc:
            await interaction.followup.send(
                f"Failed to create season or leaderboard: {exc}",
                ephemeral=True,
            )
            return

        self.stop()
        await interaction.followup.send(
            f"Season **{self.month}** started with districts: "
            + ", ".join(f"**{d}**" for d in chosen),
            ephemeral=True,
        )

# Score submission Modal

class ScoreModal(discord.ui.Modal):
    def __init__(
        self,
        title: str,
        districts: list[str],
        prefill: Optional[dict] = None,
        on_submit_callback=None,
    ) -> None:
        super().__init__(title=title)
        self.districts = districts
        self.on_submit_callback = on_submit_callback
        self.inputs: list[discord.ui.TextInput] = []

        for district in districts:
            default = ""
            if prefill and district in prefill:
                info = prefill[district]
                default = f"{info['stars']}.{info['percent']:02d}"
            field = discord.ui.TextInput(
                label=district,
                placeholder="e.g. 3.099 or 2.50",
                default=default,
                required=True,
                max_length=6,
            )
            self.add_item(field)
            self.inputs.append(field)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.on_submit_callback:
            await self.on_submit_callback(interaction, self)

# Delete season confirmation view
class ConfirmDeleteView(discord.ui.View):
    def __init__(self, season_name: str, season_id: int) -> None:
        super().__init__(timeout=60)
        self.season_name = season_name
        self.season_id = season_id

    @discord.ui.button(label="Yes, delete", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await database.delete_season(self.season_id)
        self.stop()
        await interaction.response.send_message(
            f"Season **{self.season_name}** and all its data have been deleted.",
            ephemeral=True,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.send_message("Cancelled.", ephemeral=True)

class ExaminerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _get_leaderboard_cog(self):
        from cogs.leaderboard import LeaderboardCog
        return self.bot.cogs.get("LeaderboardCog")

    async def _trigger_leaderboard_update(self, season=None) -> None:
        cog = self._get_leaderboard_cog()
        if cog:
            await cog.update_leaderboard(season)
    
    # /Start
    @app_commands.command(name="start", description="Start a new CC Exam.")
    @app_commands.describe(month="Month name (e.g. June)", year="Year (e.g. 2025)")
    @examiner_only()
    async def start(
        self, interaction: discord.Interaction, month: str, year: int
    ) -> None:
        season_name = f"{month} {year}"
        view = DistrictSelectView(season_name, interaction)
        await interaction.response.send_message(
            f"**Starting season: {season_name}**\nSelect 5 districts, then click Confirm:",
            view=view,
            ephemeral=True,
        )

    # /End Exam
    @app_commands.command(name="end_exam", description="Close the current CC Exam.")
    @examiner_only()
    async def end_season(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        season = await database.get_active_season()
        if season is None:
            await interaction.followup.send("No active season.", ephemeral=True)
            return

        await database.end_season(season["id"])

        # Update leaderboard title to reflect ended season
        lb_cog = self._get_leaderboard_cog()
        if lb_cog:
            season_dict = dict(season)
            season_dict["is_active"] = False
            await lb_cog.update_leaderboard(season_dict)

        end_channel = await get_cached_channel(interaction.guild, config.END_SEASON_CHANNEL_ID, self.bot)

        bases = await database.get_bases(season["id"])
        base_map = {b["district_name"]: b for b in bases}
        districts: list[str] = sort_districts(list(season["districts"]))

        import aiohttp
        import io

        lines = [f"**Season: {season['month']}**", ""]
        files = []

        # Gather screenshot URLs to refresh
        urls_to_refresh = [base_map[d]["screenshot_url"] for d in districts if d in base_map and base_map[d].get("screenshot_url")]
        refreshed_map = {}

        async with aiohttp.ClientSession() as session:
            # Refresh expired URLs
            if urls_to_refresh:
                try:
                    async with session.post(
                        "https://discord.com/api/v9/attachments/refresh-urls",
                        headers={
                            "Authorization": f"Bot {self.bot.http.token}",
                            "Content-Type": "application/json"
                        },
                        json={"attachment_urls": urls_to_refresh}
                    ) as r_resp:
                        if r_resp.status == 200:
                            r_data = await r_resp.json()
                            for item in r_data.get("refreshed_urls", []):
                                refreshed_map[item["original"]] = item["refreshed"]
                except Exception:
                    pass

            for district in districts:
                lines.append(f"**{district}**")
                if district in base_map:
                    b = base_map[district]
                    lines.append(f"<{b['link']}>")
                    if b.get("builder"):
                        lines.append(f"Builder: {b['builder']}")
                    
                    # Try to fetch and attach the screenshot
                    try:
                        target_url = refreshed_map.get(b["screenshot_url"], b["screenshot_url"])
                        async with session.get(target_url) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                ext = "png"
                                if "jpg" in target_url.lower() or "jpeg" in target_url.lower():
                                    ext = "jpg"
                                file_name = f"{district.replace(' ', '_').lower()}.{ext}"
                                files.append(discord.File(io.BytesIO(data), filename=file_name))
                            else:
                                lines.append(b["screenshot_url"])
                    except Exception:
                        lines.append(b["screenshot_url"])
                else:
                    lines.append("_No base recorded_")
                lines.append("")

        if files:
            await end_channel.send(content="\n".join(lines), files=files)
        else:
            await end_channel.send(content="\n".join(lines))

        await interaction.followup.send(
            f"Season **{season['month']}** has ended.", ephemeral=True
        )

    # /Share Bases
    @app_commands.command(name="share_bases", description="Post all bases for a specific season to the end-season channel.")
    @app_commands.describe(season_name="Season name, e.g. 'June 2025'")
    @examiner_only()
    async def share_bases(self, interaction: discord.Interaction, season_name: str) -> None:
        await interaction.response.defer(ephemeral=True)

        season = await database.get_season_by_name(season_name)
        if season is None:
            await interaction.followup.send(f"No season found with name **{season_name}**.", ephemeral=True)
            return

        end_channel = await get_cached_channel(interaction.guild, config.END_SEASON_CHANNEL_ID, self.bot)

        bases = await database.get_bases(season["id"])
        base_map = {b["district_name"]: b for b in bases}
        districts: list[str] = sort_districts(list(season["districts"]))

        import aiohttp
        import io

        lines = [f"**Season: {season['month']}**", ""]
        files = []

        # Gather screenshot URLs to refresh
        urls_to_refresh = [base_map[d]["screenshot_url"] for d in districts if d in base_map and base_map[d].get("screenshot_url")]
        refreshed_map = {}

        async with aiohttp.ClientSession() as session:
            # Refresh expired URLs
            if urls_to_refresh:
                try:
                    async with session.post(
                        "https://discord.com/api/v9/attachments/refresh-urls",
                        headers={
                            "Authorization": f"Bot {self.bot.http.token}",
                            "Content-Type": "application/json"
                        },
                        json={"attachment_urls": urls_to_refresh}
                    ) as r_resp:
                        if r_resp.status == 200:
                            r_data = await r_resp.json()
                            for item in r_data.get("refreshed_urls", []):
                                refreshed_map[item["original"]] = item["refreshed"]
                except Exception:
                    pass

            for district in districts:
                lines.append(f"**{district}**")
                if district in base_map:
                    b = base_map[district]
                    lines.append(f"<{b['link']}>")
                    if b.get("builder"):
                        lines.append(f"Builder: {b['builder']}")
                    
                    # Try to fetch and attach the screenshot
                    try:
                        target_url = refreshed_map.get(b["screenshot_url"], b["screenshot_url"])
                        async with session.get(target_url) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                ext = "png"
                                if "jpg" in target_url.lower() or "jpeg" in target_url.lower():
                                    ext = "jpg"
                                file_name = f"{district.replace(' ', '_').lower()}.{ext}"
                                files.append(discord.File(io.BytesIO(data), filename=file_name))
                            else:
                                lines.append(b["screenshot_url"])
                    except Exception:
                        lines.append(b["screenshot_url"])
                else:
                    lines.append("_No base recorded_")
                lines.append("")

        if files:
            await end_channel.send(content="\n".join(lines), files=files)
        else:
            await end_channel.send(content="\n".join(lines))

        await interaction.followup.send(
            f"Bases for season **{season['month']}** shared in <#{end_channel.id}>.", ephemeral=True
        )

    # /Delete Season
    @app_commands.command(name="delete_exam", description="Delete a season and all its data.")
    @app_commands.describe(name="Season name, e.g. 'June 2025'")
    @examiner_only()
    async def delete_season(self, interaction: discord.Interaction, name: str) -> None:
        season = await database.get_season_by_name(name)
        if season is None:
            await interaction.response.send_message(
                f"No season found with name **{name}**.", ephemeral=True
            )
            return

        view = ConfirmDeleteView(season["month"], season["id"])
        await interaction.response.send_message(
            f"Are you sure you want to delete season **{season['month']}** and ALL its data? "
            "This cannot be undone.",
            view=view,
            ephemeral=True,
        )

    # /Add Link
    @app_commands.command(name="add_link", description="Add or replace a base link for a district.")
    @app_commands.describe(
        link="The CC base layout share link",
        screenshot="Screenshot of the base",
        builder="Optional name of the base builder",
    )
    @examiner_only()
    async def add_link(
        self,
        interaction: discord.Interaction,
        link: str,
        screenshot: discord.Attachment,
        builder: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        season = await database.get_active_season()
        if season is None:
            await interaction.followup.send("No active season.", ephemeral=True)
            return

        if not is_valid_coc_link(link):
            await interaction.followup.send(
                "That doesn't look like a valid CoC layout share link.", ephemeral=True
            )
            return

        district_name = get_district_name_from_link(link)
        if district_name is None:
            await interaction.followup.send(
                "Could not detect which district this link belongs to.", ephemeral=True
            )
            return

        districts: list[str] = sort_districts(list(season["districts"]))
        if district_name not in districts:
            await interaction.followup.send(
                f"**{district_name}** is not one of the districts in the current season.\n"
                f"Current districts: {', '.join(districts)}",
                ephemeral=True,
            )
            return

        await database.add_base(season["id"], district_name, link, screenshot.url, builder)
        await interaction.followup.send(
            f"Base for **{district_name}** saved.", ephemeral=True
        )

    # show bases
    @app_commands.command(name="show_bases", description="Show all bases for the current season.")
    @examiner_only()
    async def show_bases(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        season = await database.get_active_season()
        if season is None:
            await interaction.followup.send("No active season.", ephemeral=True)
            return

        bases = await database.get_bases(season["id"])
        base_map = {b["district_name"]: b for b in bases}
        districts: list[str] = sort_districts(list(season["districts"]))

        embed = discord.Embed(
            title=f"📋 Bases - {season['month']}",
            color=discord.Color.green(),
        )
        for district in districts:
            if district in base_map:
                b = base_map[district]
                val = f"[Link]({b['link']})\n[Screenshot]({b['screenshot_url']})"
                if b.get("builder"):
                    val += f"\nBuilder: {b['builder']}"
                embed.add_field(
                    name=district,
                    value=val,
                    inline=False,
                )
            else:
                embed.add_field(name=district, value="_Not set_", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    # Submit Score
    @app_commands.command(name="submit_score", description="Submit a score for a player.")
    @app_commands.describe(player="The player to submit a score for")
    @examiner_only()
    async def submit_score(
        self, interaction: discord.Interaction, player: discord.Member
    ) -> None:
        season = await database.get_active_season()
        if season is None:
            await interaction.response.send_message("No active season.", ephemeral=True)
            return

        existing = await database.get_score(season["id"], player.id)
        if existing:
            await interaction.response.send_message(
                f"{player.mention} already has a score this season. Use `/edit_score` instead.",
                ephemeral=True,
            )
            return

        districts: list[str] = sort_districts(list(season["districts"]))

        async def on_submit(inter: discord.Interaction, modal: ScoreModal) -> None:
            district_scores: dict = {}
            errors: list[str] = []
            for i, district in enumerate(districts):
                raw = modal.inputs[i].value
                parsed = parse_score(raw)
                if parsed is None:
                    errors.append(f"**{district}**: invalid score `{raw}` (use x.xxx or x.xx)")
                else:
                    district_scores[district] = parsed

            if errors:
                await inter.response.send_message(
                    "Score parse errors:\n" + "\n".join(errors), ephemeral=True
                )
                return

            totals = calculate_totals(district_scores)
            row = await database.submit_score(
                season_id=season["id"],
                player_id=player.id,
                district_scores=district_scores,
                total_stars=totals["total_stars"],
                total_percent=totals["total_percent"],
                three_star_count=totals["three_star_count"],
                grade=totals["grade"],
            )

            results_channel = await get_cached_channel(inter.guild, config.SCORE_RESULTS_CHANNEL_ID, self.bot)
            try:
                score_embed = build_score_embed(
                    player=player,
                    districts=districts,
                    district_scores=district_scores,
                    total_stars=totals["total_stars"],
                    total_percent=totals["total_percent"],
                    grade=totals["grade"],
                )
                result_msg = await results_channel.send(
                    content=player.mention, embed=score_embed
                    # embed=score_embed
                )
                await database.save_result_message_id(row["id"], result_msg.id)

                await inter.response.send_message("✅ Score submitted.", ephemeral=True)
                await self._trigger_leaderboard_update(season)
            except Exception as exc:
                await inter.response.send_message(
                    f"Failed to post score or update leaderboard: {exc}",
                    ephemeral=True,
                )
                return

        modal = ScoreModal(
            title=f"Submit Score — {player.display_name}",
            districts=districts,
            on_submit_callback=on_submit,
        )
        await interaction.response.send_modal(modal)

    # Edit Score
    @app_commands.command(name="edit_score", description="Edit an existing score for a player.")
    @app_commands.describe(player="The player whose score to edit")
    @examiner_only()
    async def edit_score(
        self, interaction: discord.Interaction, player: discord.Member
    ) -> None:
        season = await database.get_active_season()
        if season is None:
            await interaction.response.send_message("No active season.", ephemeral=True)
            return

        existing = await database.get_score(season["id"], player.id)
        if existing is None:
            await interaction.response.send_message(
                f"No score found for {player.mention} this season.", ephemeral=True
            )
            return

        districts: list[str] = sort_districts(list(season["districts"]))
        current_scores = (
            existing["district_scores"]
            if isinstance(existing["district_scores"], dict)
            else json.loads(existing["district_scores"])
        )

        async def on_submit(inter: discord.Interaction, modal: ScoreModal) -> None:
            district_scores: dict = {}
            errors: list[str] = []
            for i, district in enumerate(districts):
                raw = modal.inputs[i].value
                parsed = parse_score(raw)
                if parsed is None:
                    errors.append(f"**{district}**: invalid score `{raw}`")
                else:
                    district_scores[district] = parsed

            if errors:
                await inter.response.send_message(
                    "Score parse errors:\n" + "\n".join(errors), ephemeral=True
                )
                return

            totals = calculate_totals(district_scores)
            await database.update_score(
                score_id=existing["id"],
                district_scores=district_scores,
                total_stars=totals["total_stars"],
                total_percent=totals["total_percent"],
                three_star_count=totals["three_star_count"],
                grade=totals["grade"],
            )

            results_channel = await get_cached_channel(inter.guild, config.SCORE_RESULTS_CHANNEL_ID, self.bot)

            score_embed = build_score_embed(
                player=player,
                districts=districts,
                district_scores=district_scores,
                total_stars=totals["total_stars"],
                total_percent=totals["total_percent"],
                grade=totals["grade"],
            )
            await results_channel.send(content=player.mention, embed=score_embed)

            await inter.response.send_message("Score updated.", ephemeral=True)
            await self._trigger_leaderboard_update(season)

        modal = ScoreModal(
            title=f"Edit Score — {player.display_name}",
            districts=districts,
            prefill=current_scores,
            on_submit_callback=on_submit,
        )
        await interaction.response.send_modal(modal)

    # delete score
    @app_commands.command(name="delete_score", description="Delete a player's score from the current season.")
    @app_commands.describe(player="The player whose score to delete")
    @examiner_only()
    async def delete_score(
        self, interaction: discord.Interaction, player: discord.Member
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        season = await database.get_active_season()
        if season is None:
            await interaction.followup.send("No active season.", ephemeral=True)
            return

        existing = await database.get_score(season["id"], player.id)
        if existing is None:
            await interaction.followup.send(
                f"No score found for {player.mention} this season.", ephemeral=True
            )
            return

        await database.delete_score(season["id"], player.id)
        await interaction.followup.send(
            f"Score for {player.mention} deleted.", ephemeral=True
        )
        await self._trigger_leaderboard_update(season)


    # Error
    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        msg = str(error)
        if isinstance(error, app_commands.CheckFailure):
            msg = str(error)
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)




async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ExaminerCog(bot))
