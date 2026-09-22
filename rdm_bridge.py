"""Bridge between the plugin and Remote Desktop Manager's PowerShell module.

Flow Launcher spawns a brand new python.exe per query for this SDK -- there is
no long-lived plugin process to hold state or run background threads across
queries. So instead of in-process caching/threads, this module:

  * reads whatever session list is currently on disk (fast, synchronous)
  * if that cache is stale, launches a *detached* powershell.exe that outlives
    this short-lived python process, has it write the fresh results straight
    to the cache file, and returns immediately without waiting for it

The next query (next keystroke) then picks up the refreshed cache.
"""
import json
import os
import subprocess
import time

CACHE_TTL_SECONDS = 5 * 60
_REFRESH_LOCK_TTL_SECONDS = 20

# Detach the child so it keeps running after this short-lived process exits.
_DETACHED_FLAGS = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

_MODULE_CANDIDATES = [
    r"%ProgramFiles(x86)%\Devolutions\Remote Desktop Manager\RemoteDesktopManager.PowerShellModule.dll",
    r"%ProgramFiles%\Devolutions\Remote Desktop Manager\RemoteDesktopManager.PowerShellModule.dll",
]

_REFRESH_SCRIPT = """
$ErrorActionPreference = 'Stop'
try {{
    Import-Module '{module_path}' | Out-Null
    $sessions = Get-RDMSession | Select-Object Name, ID, Group, ConnectionType
    $payload = @{{ sessions = @($sessions); timestamp = [double][DateTimeOffset]::UtcNow.ToUnixTimeSeconds(); error = $null }}
}} catch {{
    $payload = @{{ sessions = @(); timestamp = [double][DateTimeOffset]::UtcNow.ToUnixTimeSeconds(); error = $_.Exception.Message }}
}}
$payload | ConvertTo-Json -Depth 4 | Set-Content -Path '{cache_file}' -Encoding UTF8
Remove-Item -Path '{lock_file}' -ErrorAction SilentlyContinue
"""

_OPEN_SESSION_SCRIPT = """
$ErrorActionPreference = 'Stop'
Import-Module '{module_path}' | Out-Null
Open-RDMSession -ID '{session_id}' -Silent
"""


def find_module_path():
    for candidate in _MODULE_CANDIDATES:
        expanded = os.path.expandvars(candidate)
        if os.path.isfile(expanded):
            return expanded
    return None


class RDMUnavailableError(RuntimeError):
    pass


def _spawn_detached(script):
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-Command", script,
        ],
        creationflags=_DETACHED_FLAGS,
        close_fds=True,
    )


class RDMBridge:
    """Reads the on-disk session cache and triggers detached refreshes."""

    def __init__(self, cache_file):
        self._cache_file = cache_file
        self._lock_file = cache_file + ".lock"
        self._sessions = []
        self._last_refresh = 0.0
        self._last_error = None
        self._load_cache_from_disk()

    def _load_cache_from_disk(self):
        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._sessions = data.get("sessions") or []
            self._last_refresh = data.get("timestamp") or 0.0
            self._last_error = data.get("error")
        except (OSError, ValueError):
            pass

    def _is_stale(self):
        return (time.time() - self._last_refresh) > CACHE_TTL_SECONDS

    def _refresh_in_flight(self):
        try:
            age = time.time() - os.path.getmtime(self._lock_file)
            return age < _REFRESH_LOCK_TTL_SECONDS
        except OSError:
            return False

    def get_sessions(self, force_refresh=False):
        """Returns the cached session list, kicking off a detached background
        refresh if the cache is stale or empty. Never blocks on PowerShell."""
        if force_refresh or self._is_stale() or not self._sessions:
            self._trigger_refresh()
        return self._sessions

    def last_error(self):
        return self._last_error

    def _trigger_refresh(self):
        if self._refresh_in_flight():
            return
        module_path = find_module_path()
        if module_path is None:
            self._last_error = (
                "Remote Desktop Manager PowerShell module not found. "
                "Is RDM installed?"
            )
            return
        try:
            os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
            with open(self._lock_file, "w", encoding="utf-8"):
                pass
            script = _REFRESH_SCRIPT.format(
                module_path=module_path,
                cache_file=self._cache_file,
                lock_file=self._lock_file,
            )
            _spawn_detached(script)
        except OSError as exc:
            self._last_error = str(exc)


def open_session(session_id):
    """Fire-and-forget: launches the given session ID in RDM in a detached
    process so it keeps running after this short-lived query process exits."""
    module_path = find_module_path()
    if module_path is None:
        raise RDMUnavailableError(
            "Remote Desktop Manager PowerShell module not found. Is RDM installed?"
        )
    script = _OPEN_SESSION_SCRIPT.format(module_path=module_path, session_id=session_id)
    _spawn_detached(script)
