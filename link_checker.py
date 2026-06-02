import re
from typing import Optional
from config import DISTRICTS

def get_district_from_link(link: str) -> Optional[int]:
    parts = re.split(r"%3A", link, flags=re.IGNORECASE)
    if len(parts) >= 3:
        district_str = parts[2].strip()
        if district_str and district_str[0].isdigit():
            n = int(district_str[0])
            if 0 <= n <= 8:
                return n
    return None

def get_district_name_from_link(link: str) -> Optional[str]:
    index = get_district_from_link(link)
    if index is None:
        return None
    return DISTRICTS[index]

def is_valid_coc_link(link: str) -> bool:
    try:
        return "link.clashofclans.com" in link and "OpenLayout" in link
    except Exception:
        return False