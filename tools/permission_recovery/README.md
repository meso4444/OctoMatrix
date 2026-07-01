# OctoMatrix Local Agent Permission Precision Recovery Tool

This tool is designed to resolve file ownership conflicts and permission overrides between Docker containers and the host system (such as log write failures, or `.cyberbrain_env` access denied errors) by performing a fully automated security and permission reconfiguration of the Agent instances.

## 📂 Directory Structure

```
tools/permission_recovery/
├── restore_local_permissions.sh  # Core recovery script (Must be run with sudo)
└── README.md                     # This documentation
```

---

## 🛠️ How It Works

`restore_local_permissions.sh` detects the host system administrator account (e.g., `kenzan`) running the script, and aligns all agent directories under `agent_home` to meet the system's security specifications:

### 🔒 Permission and Ownership Specifications

| Directory / File Path | Recommended Owner (Owner:Group) | Recommended Perms | Security & Defense Design |
| :--- | :--- | :--- | :--- |
| `agent_home/` Instance Root | `kenzan:kenzan` (Sys Admin) | `1777` | Sticky Bit enabled. Anyone can create files, but can only delete their own files. Prevents cross-instance deletions. |
| `octo_cyberbrain/` | `kenzan:kenzan` (Sys Admin) | `1777` | Control layer. Ensures the system can manage variables and piping processes. |
| `.cyberbrain_env` | `kenzan:kenzan` (Sys Admin) | `644` | Read-only environment configuration. Prevents runtime tampering of critical variables. |
| `octo_shell.log` | `kenzan:kenzan` (Sys Admin) | `644` | Active activity log. Writable only by the system user (via tmux piping). Agent accounts are read-only to prevent log purging. |
| `octo_ghost.json` | `kenzan:kenzan` (Sys Admin) | `646` | Active Ghost state file. Others writable. Allows agents running in de-escalated environments to call `ghost_updater` to log state. |
| `toolbox/` / `knowledge/` | `kenzan:kenzan` (Sys Admin) | `644` (Files)<br>`755` (Dirs) | Internal tools and knowledge base. Read-only for agents. |
| `skillbox/` | `kenzan:kenzan` (Sys Admin) | `a-w,a+rX` | Skill sandbox. Enforced read-only. |
| Symlinks `*_shared_space` | - | `777` (Symbolic Link) | Ensures cross-agent mesh communication. |

---

## 🚀 Execution Guide

### 1. One-Click Auto Detect & Repair
Execute directly from the script directory:
```bash
sudo ./restore_local_permissions.sh
```
*The script will automatically detect the `agent_home` location and reconfigure permissions.*

### 2. Specify a Custom `agent_home` Directory
If your instance is deployed in a custom directory, pass the path as an argument:
```bash
sudo ./restore_local_permissions.sh /path/to/custom/agent_home
```

---

## ⚠️ Notes
1. This script modifies ownership and sensitive permissions, so **it must be run with `sudo`**.
2. After completion, you can verify it by checking if `octo_shell.log` belongs to the host user (e.g., `kenzan`) and has `644` permissions via `ls -la`.
