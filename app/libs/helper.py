from datetime import datetime
import re
from typing import Optional


class Helper:
    @staticmethod
    def paginate(
        data: list,
        total_count: int,
        skip: int,
        page: int,
        page_size: int,
        search: Optional[str] = None,
    ) -> dict:
        return {
            "data": data,
            "pagination": {
                "total_items": total_count,
                "total_pages": (total_count + page_size - 1) // page_size,
                "current_page": page,
                "page_size": page_size,
                "next_page": page + 1 if skip + page_size < total_count else None,
                "prev_page": page - 1 if page > 1 else None,
                "search_term": search,
            },
        }

    @staticmethod
    def parse_flexible_datetime(dt_str: str) -> datetime:
        if not dt_str or not isinstance(dt_str, str):
            raise ValueError("Invalid datetime")

        s = dt_str.strip()

        if s.endswith("Z"):
            s = s[:-1] + "+00:00"

        s = s.replace(" ", "T")
        m = re.search(r"([+-])(\d{2})(\d{2})$", s)
        if m:
            sign, hh, mm = m.groups()
            s = re.sub(r"([+-]\d{4})$", f"{sign}{hh}:{mm}", s)

        # Try fromisoformat first (handles fractional seconds and +HH:MM offsets)
        try:
            return datetime.fromisoformat(s)
        except Exception:
            pass

        # Fallback strptime patterns (no timezone awareness here)
        strptime_patterns = [
            "%Y-%m-%dT%H:%M:%S.%f",  # 2025-10-06T08:00:00.123
            "%Y-%m-%dT%H:%M:%S",     # 2025-10-06T08:00:00
            "%Y-%m-%dT%H:%M",        # 2025-10-06T08:00
            "%Y-%m-%d %H:%M:%S.%f",  # 2025-10-06 08:00:00.123
            "%Y-%m-%d %H:%M:%S",     # 2025-10-06 08:00:00
            "%Y-%m-%d %H:%M",        # 2025-10-06 08:00
            "%Y-%m-%d",              # 2025-10-06  (interpreted as midnight)
        ]

        for fmt in strptime_patterns:
            try:
                return datetime.strptime(dt_str, fmt)
            except Exception:
                continue

        # Nothing matched
        raise ValueError(f"Unrecognized datetime format: {dt_str}")
