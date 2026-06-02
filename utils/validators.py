from typing import Optional

def parse_score(raw: str) -> Optional[dict]:
    raw = raw.strip()
    if "." not in raw:
        return None

    parts = raw.split(".", 1)
    if len(parts) != 2:
        return None

    star_str, percent_str = parts

    if not star_str.isdigit():
        return None
    stars = int(star_str)
    if stars < 0 or stars > 3:
        return None

    if len(percent_str) not in (2, 3):
        return None
    if not percent_str.isdigit():
        return None

    stripped = percent_str.lstrip("0")
    percent = int(stripped) if stripped else 0

    if percent < 0 or percent > 100:
        return None

    return {"stars": stars, "percent": percent}

def calculate_totals(district_scores: dict) -> dict:
    from config import GRADE_MAP

    total_stars = 0
    total_percent = 0
    three_star_count = 0

    for score in district_scores.values():
        total_stars += score["stars"]
        total_percent += score["percent"]
        if score["stars"] == 3:
            three_star_count += 1

    grade = GRADE_MAP.get(three_star_count, "D")

    return {
        "total_stars": total_stars,
        "total_percent": total_percent,
        "three_star_count": three_star_count,
        "grade": grade,
    }