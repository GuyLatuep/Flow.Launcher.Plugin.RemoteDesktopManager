<div align="center">

<img src="assets/icon.png" width="96" height="96" alt="Remote Desktop Manager plugin icon" />

# Remote Desktop Manager for Flow Launcher

**Search and launch your [Devolutions Remote Desktop Manager](https://devolutions.net/remote-desktop-manager) sessions without leaving your keyboard.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Flow Launcher](https://img.shields.io/badge/Flow%20Launcher-plugin-6b46c1.svg)](https://www.flowlauncher.com/)
[![PowerShell 7+](https://img.shields.io/badge/PowerShell-7%2B-5391FE.svg?logo=powershell&logoColor=white)](https://aka.ms/powershell)
[![Python](https://img.shields.io/badge/python-3-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)

</div>

---

## ✨ Overview

Type `rdm` in [Flow Launcher](https://www.flowlauncher.com/), start typing a session name, and press <kbd>Enter</kbd>. That's it — no switching to the RDM window, no clicking through folders.

```
rdm prod-db01
```

<div align="center">

| You type | You get |
| :-- | :-- |
| `rdm prod` | Every session matching *prod*, grouped by RDM folder/type |
| <kbd>Enter</kbd> | The session opens directly in Remote Desktop Manager |

</div>

Results come from a local cache that refreshes automatically every **5 minutes**, so search stays instant even with large connection lists. Just added a session? Wait a few seconds or search again to trigger a refresh.

---

## 📋 Requirements

| Requirement | Notes |
| :-- | :-- |
| 🖥️ **Remote Desktop Manager** | Installed locally, with the data source you want to search already open/connected in the RDM desktop app |
| 🐚 **[PowerShell 7+](https://aka.ms/powershell)** (`pwsh`) on `PATH` | Windows PowerShell 5.1 is *not* enough — its RDM module can list sessions but fails to open them against recent RDM versions |
| 📦 **[`Devolutions.PowerShell`](https://www.powershellgallery.com/packages/Devolutions.PowerShell)** module | Install with the command below |

```powershell
winget install --id Microsoft.PowerShell
Install-Module Devolutions.PowerShell -Scope CurrentUser
```

> If either requirement is missing, searching will show a result explaining what to install.

---

## 🚀 Install

**From the Flow Launcher Plugin Store** *(once published)*:

```
pm install Remote Desktop Manager
```

**Manually / for development:**

Copy this folder into `%APPDATA%\FlowLauncher\Plugins\` and restart Flow Launcher.

---

## 🛠️ Development

```powershell
python -m pip install -r requirements.txt -t .\lib
```

Then copy or symlink the project folder into `%APPDATA%\FlowLauncher\Plugins\` and restart Flow Launcher to test changes.

---

## 📄 License

Released under the [MIT License](LICENSE).
