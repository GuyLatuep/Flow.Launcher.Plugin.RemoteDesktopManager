"""Bridge between the plugin and Remote Desktop Manager's PowerShell module.

Flow Launcher spawns a brand new python.exe per query for this SDK -- there is
no long-lived plugin process to hold state or run background threads across
queries. So instead of in-process caching/threads, this module:

  * reads whatever session list is currently on disk (fast, synchronous)
  * if that cache is stale, launches a *detached* powershell.exe that outlives
    this short-lived python process, has it write the fresh results straight
    to the cache file, and returns immediately without waiting for it

The next query (next keystroke) then picks up the refreshed cache.

Remote Desktop Manager's automation is the `Devolutions.PowerShell` module
(PowerShell Gallery), which requires PowerShell 7+ (`pwsh.exe`). The older
`RemoteDesktopManager` module / Windows PowerShell 5.1 can still list
sessions, but its Open-RDMSession call times out against current RDM
versions (verified against RDM 2026.2.18.0) -- likely an IPC protocol
mismatch, since that module hasn't been updated since 2023. So this plugin
requires pwsh + Devolutions.PowerShell rather than trying to support both.
"""
import json
import os
import subprocess
import tempfile
import time

CACHE_TTL_SECONDS = 5 * 60
_REFRESH_LOCK_TTL_SECONDS = 20

# CREATE_NO_WINDOW hides the console; child processes outlive their parent on
# Windows by default so no extra flag is needed for that. DETACHED_PROCESS
# additionally strips the window station, which the RDM PowerShell module
# needs (it's backed by RDM's WPF engine) -- combining the two makes RDM
# cmdlets fail silently, so CREATE_NO_WINDOW alone is used here.
_DETACHED_FLAGS = subprocess.CREATE_NO_WINDOW

# Plain PowerShell (no Python .format placeholders) -- kept separate so its
# literal `{`/`}` never has to be escaped for str.format/f-strings.
_IMPORT_SNIPPET = r"""
if (-not (Get-Module -ListAvailable -Name Devolutions.PowerShell)) {
    throw "Devolutions.PowerShell module not found. Install it with: Install-Module Devolutions.PowerShell -Scope CurrentUser"
}
Import-Module Devolutions.PowerShell -ErrorAction Stop
"""


def _build_refresh_script(cache_file, lock_file):
    return (
        "$ErrorActionPreference = 'Stop'\n"
        "try {\n"
        + _IMPORT_SNIPPET +
        "    $sessions = Get-RDMSession | Select-Object Name, ID, Group, @{Name='ConnectionType'; Expression={ $_.ConnectionType.ToString() }}\n"
        "    $payload = @{ sessions = @($sessions); timestamp = [double][DateTimeOffset]::UtcNow.ToUnixTimeSeconds(); error = $null }\n"
        "} catch {\n"
        "    $payload = @{ sessions = @(); timestamp = [double][DateTimeOffset]::UtcNow.ToUnixTimeSeconds(); error = $_.Exception.Message }\n"
        "}\n"
        f"$payload | ConvertTo-Json -Depth 4 | Set-Content -Path '{cache_file}' -Encoding UTF8\n"
        f"Remove-Item -Path '{lock_file}' -ErrorAction SilentlyContinue\n"
    )


def _build_open_session_script(session_id):
    return (
        "$ErrorActionPreference = 'Stop'\n"
        + _IMPORT_SNIPPET +
        f"Open-RDMSession -ID '{session_id}' -Silent\n"
    )


def _spawn_detached(script):
    """Runs `script` in a detached pwsh.exe that outlives this process.

    Passed via -File (a temp .ps1), not -Command: a multi-line script handed
    to -Command through subprocess's argv list gets mangled by Windows
    command-line quoting. The script deletes its own temp file when done.
    Raises FileNotFoundError (a subclass of OSError) if pwsh.exe (PowerShell
    7+) isn't on PATH -- Devolutions.PowerShell requires it.
    """
    fd, path = tempfile.mkstemp(prefix="rdm-flowlauncher-", suffix=".ps1")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(script)
        f.write(f"\nRemove-Item -LiteralPath '{path}' -Force -ErrorAction SilentlyContinue\n")
    subprocess.Popen(
        [
            "pwsh.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-File", path,
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
            # Windows PowerShell 5.1's `Set-Content -Encoding UTF8` writes a
            # BOM (.NET Core/pwsh 7 doesn't); utf-8-sig strips it if present
            # and behaves like plain utf-8 if not.
            with open(self._cache_file, "r", encoding="utf-8-sig") as f:
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
        try:
            os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
            with open(self._lock_file, "w", encoding="utf-8"):
                pass
            script = _build_refresh_script(self._cache_file, self._lock_file)
            _spawn_detached(script)
        except OSError as exc:
            self._last_error = str(exc)


def open_session(session_id):
    """Fire-and-forget: launches the given session ID in RDM in a detached
    process so it keeps running after this short-lived query process exits."""
    script = _build_open_session_script(session_id)
    try:
        _spawn_detached(script)
    except OSError:
        pass
