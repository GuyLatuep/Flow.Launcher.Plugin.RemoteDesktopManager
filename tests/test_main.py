import main


def _make_plugin(sessions=None, last_error=None):
    """Builds a RemoteDesktopManagerPlugin without running FlowLauncher's
    __init__ (which reads sys.argv and dispatches/prints a JSON-RPC response
    as a side effect)."""
    plugin = object.__new__(main.RemoteDesktopManagerPlugin)
    plugin._bridge = _FakeBridge(sessions or [], last_error)
    return plugin


class _FakeBridge:
    def __init__(self, sessions, last_error=None):
        self._sessions = sessions
        self._last_error = last_error
        self.force_refresh_calls = 0

    def get_sessions(self, force_refresh=False):
        if force_refresh:
            self.force_refresh_calls += 1
        return self._sessions

    def last_error(self):
        return self._last_error


class TestScore:
    def test_empty_query_has_no_score(self):
        assert main._score("", "prod-db01", "servers") == 0

    def test_exact_match_scores_highest(self):
        assert main._score("prod-db01", "prod-db01", "servers") == 100

    def test_prefix_match(self):
        assert main._score("prod", "prod-db01", "servers") == 80

    def test_substring_of_name(self):
        assert main._score("db01", "prod-db01", "servers") == 60

    def test_substring_of_group_only(self):
        assert main._score("serv", "prod-db01", "servers") == 30

    def test_no_match_returns_none(self):
        assert main._score("nope", "prod-db01", "servers") is None


class TestQuery:
    def test_no_sessions_and_no_error_shows_loading_message(self):
        plugin = _make_plugin(sessions=[], last_error=None)
        results = plugin.query("prod")
        assert len(results) == 1
        assert "Loading" in results[0]["Title"]

    def test_no_sessions_with_error_shows_error_message(self):
        plugin = _make_plugin(sessions=[], last_error="pwsh.exe not found")
        results = plugin.query("prod")
        assert len(results) == 1
        assert "Couldn't load" in results[0]["Title"]
        assert results[0]["SubTitle"] == "pwsh.exe not found"

    def test_non_openable_types_are_filtered_out(self):
        sessions = [
            {"Name": "prod-db01", "ID": "1", "Group": "Servers", "ConnectionType": "RDPConfiguration"},
            {"Name": "prod-group", "ID": "2", "Group": "Servers", "ConnectionType": "Group"},
            {"Name": "prod-cred", "ID": "3", "Group": "Servers", "ConnectionType": "Credential"},
        ]
        plugin = _make_plugin(sessions=sessions)
        results = plugin.query("prod")
        titles = [r["Title"] for r in results]
        assert titles == ["prod-db01"]

    def test_results_are_ranked_best_match_first(self):
        sessions = [
            {"Name": "web-prod-2", "ID": "1", "Group": "Servers", "ConnectionType": "RDPConfiguration"},
            {"Name": "prod-db01", "ID": "2", "Group": "Servers", "ConnectionType": "RDPConfiguration"},
            {"Name": "prod", "ID": "3", "Group": "Servers", "ConnectionType": "RDPConfiguration"},
        ]
        plugin = _make_plugin(sessions=sessions)
        results = plugin.query("prod")
        titles = [r["Title"] for r in results]
        assert titles == ["prod", "prod-db01", "web-prod-2"]

    def test_result_includes_open_session_action(self):
        sessions = [{"Name": "prod-db01", "ID": "abc-123", "Group": "Servers", "ConnectionType": "RDPConfiguration"}]
        plugin = _make_plugin(sessions=sessions)
        results = plugin.query("prod")
        assert results[0]["JsonRPCAction"] == {
            "method": "open_session",
            "parameters": ["abc-123"],
        }

    def test_no_match_offers_refresh(self):
        sessions = [{"Name": "prod-db01", "ID": "1", "Group": "Servers", "ConnectionType": "RDPConfiguration"}]
        plugin = _make_plugin(sessions=sessions)
        results = plugin.query("nothing-like-this")
        assert len(results) == 1
        assert results[0]["JsonRPCAction"] == {"method": "refresh_sessions", "parameters": []}


class TestOpenSession:
    def test_open_session_forwards_to_bridge(self, monkeypatch):
        called_with = []
        monkeypatch.setattr(main.rdm_bridge, "open_session", lambda session_id: called_with.append(session_id))
        plugin = _make_plugin()
        plugin.open_session("abc-123")
        assert called_with == ["abc-123"]

    def test_open_session_ignores_empty_id(self, monkeypatch):
        called = []
        monkeypatch.setattr(main.rdm_bridge, "open_session", lambda session_id: called.append(session_id))
        plugin = _make_plugin()
        plugin.open_session(None)
        assert called == []


class TestRefreshSessions:
    def test_refresh_sessions_forces_a_refresh(self):
        plugin = _make_plugin(sessions=[])
        plugin.refresh_sessions()
        assert plugin._bridge.force_refresh_calls == 1
