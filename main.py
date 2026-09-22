import os
import sys

# Flow Launcher's embeddable Python doesn't put the script's own directory on
# sys.path by default, so local imports (rdm_bridge) and vendored deps (lib/)
# both need to be added explicitly.
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PLUGIN_DIR)
sys.path.insert(0, os.path.join(PLUGIN_DIR, "lib"))

from flowlauncher import FlowLauncher  # noqa: E402

import rdm_bridge  # noqa: E402

CACHE_FILE = os.path.join(PLUGIN_DIR, "cache", "sessions.json")
ICON_PATH = "assets/icon.png"
MAX_RESULTS = 20

# Folders/credential records, not connections you can actually "open".
_NON_OPENABLE_TYPES = {"Group", "Credential"}


def _score(query_lower, name_lower, group_lower):
    if not query_lower:
        return 0
    if name_lower == query_lower:
        return 100
    if name_lower.startswith(query_lower):
        return 80
    if query_lower in name_lower:
        return 60
    if query_lower in group_lower:
        return 30
    return None


class RemoteDesktopManagerPlugin(FlowLauncher):
    def __init__(self):
        self._bridge = rdm_bridge.RDMBridge(CACHE_FILE)
        super().__init__()

    def query(self, query):
        query_lower = query.strip().lower()
        sessions = self._bridge.get_sessions()

        if not sessions:
            error = self._bridge.last_error()
            if error:
                return [{
                    "Title": "Couldn't load Remote Desktop Manager sessions",
                    "SubTitle": error,
                    "IcoPath": ICON_PATH,
                }]
            return [{
                "Title": "Loading Remote Desktop Manager sessions…",
                "SubTitle": "This can take a few seconds on first use.",
                "IcoPath": ICON_PATH,
            }]

        scored = []
        for session in sessions:
            if (session.get("ConnectionType") or "") in _NON_OPENABLE_TYPES:
                continue
            name = session.get("Name") or ""
            group = session.get("Group") or ""
            score = _score(query_lower, name.lower(), group.lower())
            if score is not None:
                scored.append((score, session))

        scored.sort(key=lambda item: (-item[0], item[1].get("Name") or ""))

        results = []
        for score, session in scored[:MAX_RESULTS]:
            name = session.get("Name") or "(unnamed session)"
            group = session.get("Group") or ""
            conn_type = session.get("ConnectionType") or ""
            subtitle = " / ".join(part for part in (group, conn_type) if part)
            results.append({
                "Title": name,
                "SubTitle": subtitle or "Remote Desktop Manager session",
                "IcoPath": ICON_PATH,
                "JsonRPCAction": {
                    "method": "open_session",
                    "parameters": [session.get("ID")],
                },
            })

        if not results:
            results.append({
                "Title": f"No Remote Desktop Manager sessions match \"{query}\"",
                "SubTitle": "Press Enter to refresh from Remote Desktop Manager",
                "IcoPath": ICON_PATH,
                "JsonRPCAction": {
                    "method": "refresh_sessions",
                    "parameters": [],
                },
            })

        return results

    def open_session(self, session_id):
        if not session_id:
            return
        rdm_bridge.open_session(session_id)

    def refresh_sessions(self):
        self._bridge.get_sessions(force_refresh=True)


if __name__ == "__main__":
    RemoteDesktopManagerPlugin()
