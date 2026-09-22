import json
import os
import time

import rdm_bridge


def _write_cache(path, sessions=None, timestamp=None, error=None):
    payload = {
        "sessions": sessions if sessions is not None else [],
        "timestamp": time.time() if timestamp is None else timestamp,
        "error": error,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


class TestLoadCacheFromDisk:
    def test_loads_sessions_timestamp_and_error(self, tmp_path):
        cache_file = tmp_path / "sessions.json"
        _write_cache(cache_file, sessions=[{"Name": "prod-db01"}], timestamp=time.time(), error=None)
        bridge = rdm_bridge.RDMBridge(str(cache_file))
        assert bridge.get_sessions() == [{"Name": "prod-db01"}]
        assert bridge.last_error() is None

    def test_loads_error_from_cache(self, tmp_path):
        cache_file = tmp_path / "sessions.json"
        _write_cache(cache_file, sessions=[], timestamp=time.time(), error="Devolutions.PowerShell module not found")
        bridge = rdm_bridge.RDMBridge(str(cache_file))
        assert bridge.last_error() == "Devolutions.PowerShell module not found"

    def test_missing_cache_file_yields_empty_sessions(self, tmp_path):
        cache_file = tmp_path / "does-not-exist.json"
        bridge = rdm_bridge.RDMBridge(str(cache_file))
        assert bridge._sessions == []
        assert bridge.last_error() is None

    def test_handles_bom_encoded_cache(self, tmp_path):
        cache_file = tmp_path / "sessions.json"
        payload = json.dumps({"sessions": [{"Name": "x"}], "timestamp": time.time(), "error": None})
        cache_file.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))
        bridge = rdm_bridge.RDMBridge(str(cache_file))
        assert bridge.get_sessions() == [{"Name": "x"}]

    def test_malformed_cache_is_ignored(self, tmp_path):
        cache_file = tmp_path / "sessions.json"
        cache_file.write_text("{not valid json", encoding="utf-8")
        bridge = rdm_bridge.RDMBridge(str(cache_file))
        assert bridge._sessions == []


class TestStaleness:
    def test_fresh_cache_is_not_stale(self, tmp_path):
        cache_file = tmp_path / "sessions.json"
        _write_cache(cache_file, timestamp=time.time())
        bridge = rdm_bridge.RDMBridge(str(cache_file))
        assert bridge._is_stale() is False

    def test_old_cache_is_stale(self, tmp_path):
        cache_file = tmp_path / "sessions.json"
        stale_timestamp = time.time() - rdm_bridge.CACHE_TTL_SECONDS - 1
        _write_cache(cache_file, timestamp=stale_timestamp)
        bridge = rdm_bridge.RDMBridge(str(cache_file))
        assert bridge._is_stale() is True


class TestGetSessions:
    def test_triggers_refresh_when_stale(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "sessions.json"
        stale_timestamp = time.time() - rdm_bridge.CACHE_TTL_SECONDS - 1
        _write_cache(cache_file, sessions=[{"Name": "old"}], timestamp=stale_timestamp)
        bridge = rdm_bridge.RDMBridge(str(cache_file))

        calls = []
        monkeypatch.setattr(bridge, "_trigger_refresh", lambda: calls.append(True))
        sessions = bridge.get_sessions()

        assert calls == [True]
        assert sessions == [{"Name": "old"}]

    def test_does_not_trigger_refresh_when_fresh(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "sessions.json"
        _write_cache(cache_file, sessions=[{"Name": "fresh"}], timestamp=time.time())
        bridge = rdm_bridge.RDMBridge(str(cache_file))

        calls = []
        monkeypatch.setattr(bridge, "_trigger_refresh", lambda: calls.append(True))
        bridge.get_sessions()

        assert calls == []

    def test_force_refresh_always_triggers(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "sessions.json"
        _write_cache(cache_file, sessions=[{"Name": "fresh"}], timestamp=time.time())
        bridge = rdm_bridge.RDMBridge(str(cache_file))

        calls = []
        monkeypatch.setattr(bridge, "_trigger_refresh", lambda: calls.append(True))
        bridge.get_sessions(force_refresh=True)

        assert calls == [True]


class TestTriggerRefresh:
    def test_spawns_detached_process_and_writes_lock(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "sessions.json"
        bridge = rdm_bridge.RDMBridge(str(cache_file))

        spawned = []
        monkeypatch.setattr(rdm_bridge, "_spawn_detached", lambda script: spawned.append(script))
        bridge._trigger_refresh()

        assert len(spawned) == 1
        assert "Get-RDMSession" in spawned[0]
        assert os.path.exists(bridge._lock_file)

    def test_skips_when_refresh_already_in_flight(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "sessions.json"
        bridge = rdm_bridge.RDMBridge(str(cache_file))
        os.makedirs(tmp_path, exist_ok=True)
        with open(bridge._lock_file, "w", encoding="utf-8"):
            pass

        spawned = []
        monkeypatch.setattr(rdm_bridge, "_spawn_detached", lambda script: spawned.append(script))
        bridge._trigger_refresh()

        assert spawned == []

    def test_records_error_when_spawn_fails(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "sessions.json"
        bridge = rdm_bridge.RDMBridge(str(cache_file))

        def _boom(script):
            raise OSError("pwsh.exe not found")

        monkeypatch.setattr(rdm_bridge, "_spawn_detached", _boom)
        bridge._trigger_refresh()

        assert bridge.last_error() == "pwsh.exe not found"


class TestRefreshInFlight:
    def test_true_for_recent_lock(self, tmp_path):
        cache_file = tmp_path / "sessions.json"
        bridge = rdm_bridge.RDMBridge(str(cache_file))
        with open(bridge._lock_file, "w", encoding="utf-8"):
            pass
        assert bridge._refresh_in_flight() is True

    def test_false_for_stale_lock(self, tmp_path):
        cache_file = tmp_path / "sessions.json"
        bridge = rdm_bridge.RDMBridge(str(cache_file))
        with open(bridge._lock_file, "w", encoding="utf-8"):
            pass
        old_time = time.time() - rdm_bridge._REFRESH_LOCK_TTL_SECONDS - 1
        os.utime(bridge._lock_file, (old_time, old_time))
        assert bridge._refresh_in_flight() is False

    def test_false_when_no_lock_file(self, tmp_path):
        cache_file = tmp_path / "sessions.json"
        bridge = rdm_bridge.RDMBridge(str(cache_file))
        assert bridge._refresh_in_flight() is False


class TestOpenSession:
    def test_open_session_spawns_detached_with_session_id(self, monkeypatch):
        spawned = []
        monkeypatch.setattr(rdm_bridge, "_spawn_detached", lambda script: spawned.append(script))
        rdm_bridge.open_session("abc-123")
        assert len(spawned) == 1
        assert "abc-123" in spawned[0]
        assert "Open-RDMSession" in spawned[0]

    def test_open_session_swallows_os_error(self, monkeypatch):
        def _boom(script):
            raise OSError("pwsh.exe not found")

        monkeypatch.setattr(rdm_bridge, "_spawn_detached", _boom)
        rdm_bridge.open_session("abc-123")  # must not raise
