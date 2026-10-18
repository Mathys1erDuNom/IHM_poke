"""Messages de combat séparés des calculs et règles."""


def add_log(state, text, kind="normal"):
    state.setdefault("log", []).append({"text": str(text), "kind": kind})
    state["log"] = state["log"][-60:]


def effectiveness_text(multiplier):
    if multiplier == 0:
        return "Aucun effet !"
    if multiplier >= 4:
        return "C'est extrêmement efficace !"
    if multiplier > 1:
        return "C'est super efficace !"
    if multiplier <= 0.25:
        return "C'est très peu efficace…"
    if multiplier < 1:
        return "Ce n'est pas très efficace…"
    return None


def status_label(status, config):
    if not status:
        return ""
    return config["statuses"].get(status, {}).get("label", str(status))