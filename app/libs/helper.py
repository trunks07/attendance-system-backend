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
