subscribers = set()


def subscribe(name: str):
    name = name.strip()
    if not name:
        raise ValueError("empty name")
    subscribers.add(name)
    return {"subscribed": True}


def unsubscribe(name: str) -> bool:
    """Remove subscriber. Trim spaces; empty -> ValueError. Return True if removed, False if not present."""
    name = name.strip()
    if not name:
        raise ValueError("empty name")
    if name in subscribers:
        subscribers.remove(name)
        return True
    return False


def list_subscribers():
    """Return new sorted list of subscribers."""
    return sorted(subscribers)  # stable sorted copy
# touch to trigger runner
# noop change to trigger edit tool behavior
