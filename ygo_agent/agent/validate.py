"""Checks a reply against a decision before it goes back to the engine (see docs/decision-protocol.md)."""


def validate(d, choice):
    """None if `choice` (a list of option indices) is an acceptable answer to decision `d`, else the reason."""
    kind, n = d["kind"], len(d.get("options", []))
    in_range = all(0 <= k < n for k in choice)
    distinct = len(set(choice)) == len(choice)
    if kind in ("effect_yn", "yesno", "go_first"):
        return None if choice in ([0], [1]) else "reply [1] for yes or [0] for no"
    if kind == "place":  # a zone bit mask, not an index
        ok = len(choice) == 1 and isinstance(choice[0], int) and choice[0] & d.get("available", 0)
        return None if ok else "reply [mask] with at least one free zone's bit"
    if not in_range or not distinct:
        return f"indices must be distinct and between 0 and {n - 1}"
    if kind in ("idle", "battle", "option", "position", "announce_card", "announce_number"):
        return None if len(choice) == 1 else "choose exactly one option"
    if kind == "chain":
        if not choice:
            return "you must activate one (this activation is mandatory)" if d.get("forced") else None
        return None if len(choice) == 1 else "choose one option or [] to pass"
    if kind in ("select_card", "tribute"):
        if not choice and (d.get("cancelable") or d["min"] == 0):
            return None
        return None if d["min"] <= len(choice) <= d["max"] else f"choose between {d['min']} and {d['max']} cards"
    if kind == "select_unselect":
        # The engine enforces counts itself; only reject what can't be sent at all.
        if not choice:
            return None if d.get("finishable") or d.get("cancelable") else "you must pick at least one card"
        return None
    if kind == "select_sum":
        if not d["min"] <= len(choice) <= d["max"]:
            return f"choose between {d['min']} and {d['max']} cards"
        opts = d["options"]
        s1 = sum(opts[k]["v1"] for k in choice)
        s2 = sum(opts[k]["v2"] or opts[k]["v1"] for k in choice)
        target = d["sum"]
        ok = (target in (s1, s2)) if d.get("exact") else (s1 >= target or s2 >= target)
        return None if ok else f"those add up to {s1}, but you need {'exactly' if d.get('exact') else 'at least'} {target}"
    if kind in ("announce_attrib", "announce_race"):
        return None if len(choice) == d.get("count", 1) else f"choose exactly {d.get('count', 1)}"
    return None
