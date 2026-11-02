"""In-memory subscription operations and read-only name search."""

subscribers = set()
MAX_QUERY_LENGTH = 100
DEMO_NAMES = ("Alice", "Bob", "Анна", "Борис")


class QueryError(ValueError):
    """An input error with a stable public API code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def subscribe(name: str):
    name = name.strip()
    if not name:
        raise ValueError("empty name")
    subscribers.add(name)
    return {"subscribed": True}


def unsubscribe(name: str) -> bool:
    name = name.strip()
    if not name:
        raise ValueError("empty name")
    if name in subscribers:
        subscribers.remove(name)
        return True
    return False


def list_subscribers():
    """Return a new sorted list, preserving the original service behavior."""
    return sorted(subscribers)


def normalize_query(query: str) -> str:
    if not isinstance(query, str):
        raise QueryError("invalid_query", "Поисковый запрос должен быть строкой.")
    query = query.strip()
    # Python len(str) counts Unicode code points; check before casefold expansion.
    if len(query) > MAX_QUERY_LENGTH:
        raise QueryError(
            "query_too_long",
            "Поисковый запрос должен быть не длиннее 100 символов.",
        )
    return query


def search_subscribers(query: str = "") -> list[str]:
    """Search by case-insensitive substring without modifying stored names."""
    needle = normalize_query(query).casefold()
    return [name for name in list_subscribers() if needle in name.casefold()]
