# Flow Launcher Plugin: Remote Desktop Manager

Search and open your [Devolutions Remote Desktop Manager](https://devolutions.net/remote-desktop-manager) (RDM) sessions from [Flow Launcher](https://www.flowlauncher.com/).

## Requirements

- Remote Desktop Manager installed locally.
- [PowerShell 7+](https://aka.ms/powershell) (`pwsh`) on `PATH`. Windows PowerShell 5.1 (the version built into Windows) is *not* enough — RDM's current automation module requires PS7, and its older, PS5.1-compatible module can list sessions but fails to actually open them against recent RDM versions.
  ```powershell
  winget install --id Microsoft.PowerShell
  ```
- The [`Devolutions.PowerShell`](https://www.powershellgallery.com/packages/Devolutions.PowerShell) module:
  ```powershell
  Install-Module Devolutions.PowerShell -Scope CurrentUser
  ```
- The data source you want to search must already be open/connected in your RDM desktop app; the plugin reads whatever RDM currently has loaded.

If either requirement is missing, searching will show a result explaining what to install.

## Usage

Type `rdm` followed by a search term:

```
rdm prod-db01
```

Matching sessions are listed by name (with their RDM group/type as the subtitle). Press Enter to open the selected session in Remote Desktop Manager.

Results are served from a local cache that refreshes automatically in the background every 5 minutes, so search stays fast even with a large connection list. If you don't see a session you just added, wait a few seconds or search again to trigger a refresh.

## Install

Once published to the Flow Launcher Plugin Store:

```
pm install Remote Desktop Manager
```

For manual/dev installation, copy this folder into `%APPDATA%\FlowLauncher\Plugins\` and restart Flow Launcher.

## Development

```powershell
python -m pip install -r requirements.txt -t .\lib
```

Then copy/symlink the project folder into `%APPDATA%\FlowLauncher\Plugins\` and restart Flow Launcher to test changes.

## License

MIT — see [LICENSE](LICENSE).
