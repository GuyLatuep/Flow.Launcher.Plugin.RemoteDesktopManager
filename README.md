# Flow Launcher Plugin: Remote Desktop Manager

Search and open your [Devolutions Remote Desktop Manager](https://devolutions.net/remote-desktop-manager) (RDM) sessions from [Flow Launcher](https://www.flowlauncher.com/).

## Requirements

- Remote Desktop Manager installed locally (the plugin drives it via its bundled PowerShell module — no separate install needed).
- Windows PowerShell available on `PATH` (default on Windows).
- The data source you want to search must already be open/connected in your RDM desktop app; the plugin reads whatever RDM currently has loaded.

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
