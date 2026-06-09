import discord
import config
from typing import Optional

GREEN_GRADES = {"B", "B+", "A", "A+"}

def fmt_percent(p: int) -> str:
    return f"{p:03d}%"

def grade_color(grade: str) -> discord.Color:
    return discord.Color.green() if grade in GREEN_GRADES else discord.Color.red()

def sort_districts(districts: list[str]) -> list[str]:
    order = {district: index for index, district in enumerate(config.DISTRICTS)}
    return sorted(districts, key=lambda district: order.get(district, len(order)))

def build_score_embed(
    player: discord.Member,
    districts: list[str],
    district_scores: dict,
    total_stars: int,
    total_percent: int,
    grade: str,
) -> discord.Embed:
    embed = discord.Embed(color=grade_color(grade))
    embed.set_author(
        name=player.display_name,
        icon_url=player.display_avatar.url,
    )

    districts = sort_districts(districts)
    lines = []
    for district in districts:
        score = district_scores.get(district, {"stars": 0, "percent": 0})
        lines.append(
            f"**{district}**: {score['stars']}⭐ {fmt_percent(score['percent'])}"
        )
    lines.append("")
    lines.append(f"**Total**: {total_stars}⭐ {fmt_percent(total_percent)}")
    lines.append(f"**Grade**: {grade}")
    embed.description = "\n".join(lines)
    return embed

def build_leaderboard_embed(
    season_name: str,
    scores: list[dict],
    guild: discord.Guild,
    is_active: bool = True,
    show_stats: bool = False,
) -> discord.Embed:
    title_prefix = "🏆 CC Exam Live Leaderboard" if is_active else "🏆 CC Exam Leaderboard"
    embed = discord.Embed(
        title=f"{title_prefix} | {season_name}",
        color=discord.Color.gold(),
    )

    if not scores:
        embed.description = "_No scores submitted yet._"
        return embed

    rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
    mentions = []
    for row in scores:
        member = guild.get_member(row["player_id"])
        mentions.append(member.mention if member else f"<@{row['player_id']}>")

    max_mention_len = max((len(mention) for mention in mentions), default=0)
    lines = [""]

    for i, (row, mention) in enumerate(zip(scores, mentions), start=1):
        rank_display = rank_emojis.get(i, f"#{i}")
        if show_stats:
            lines.append(
                f"{rank_display} {mention:<{max_mention_len}}  {row['total_stars']}⭐ {fmt_percent(row['total_percent'])}  {row['grade']}"
            )
        else:
            lines.append(
                f"{rank_display} {mention:<{max_mention_len}}  {row['grade']}"
            )

    lines.append("")
    embed.description = "\n".join(lines)
    return embed

def build_show_score_embed(
    season_name: str,
    districts: list[str],
    district_scores: dict,
    total_stars: int,
    total_percent: int,
    grade: str,
    page: int,
    total_pages: int,
    player_name: Optional[str] = None,
    player_icon_url: Optional[str] = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=f" {season_name}",
        color=grade_color(grade),
    )
    if player_name:
        
        if player_icon_url:
            embed.set_author(name=player_name, icon_url=player_icon_url)
        else:
            embed.set_author(name=player_name)
    districts = sort_districts(districts)
    lines = []
    for district in districts:
        score = district_scores.get(district, {"stars": 0, "percent": 0})
        lines.append(
            f"**{district}**: {score['stars']}⭐ {fmt_percent(score['percent'])}"
        )
    lines.append("")
    lines.append(f"**Total**: {total_stars}⭐ {fmt_percent(total_percent)}")
    lines.append(f"**Grade**: {grade}")
    embed.description = "\n".join(lines)
    return embed