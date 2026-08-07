# 📜 Octo Skill Packaging Guidelines

This guide defines the development and packaging standards for extension Skills within the OctoMatrix ecosystem. Any skill package intended for integration into the system must follow the structure and environment-setup rules below.

---

## 1. Naming & Structure

Skills must be packaged as `.tar.gz` or `.zip` archives, and their internal structure must strictly follow these conventions:

### 1.1 Naming Consistency
The outermost directory name after extraction must exactly match the archive's filename prefix; the system uses this name as the identifier.
* **Correct example**: a file named `draw_card_client_v2.tar.gz` (or `draw_card_client_v2.zip`) must have `draw_card_client_v2/` as its internal root directory.

### 1.2 Standard File Structure
Components inside the skill directory:
* **`SKILL.md` (required)**: The Agent's sole reference for how to use the skill. Must include trigger commands, required parameter definitions, and expected output. Required even for pure prompt-based skills with no code.
* **`setup.sh` (optional)**: Skill initialization script. Required if the skill needs to download extra binaries or extract dynamic libraries.
* **Executables/source (optional)**: e.g. `.py`, `.js`. Not needed if the skill is purely a prompt injection with no code.

### 1.3 The Greedy-Packing Trap (Safeguard)
Running `tar -czf skill.tar.gz *` (or `zip -r skill.zip *`) directly can, if an old archive with the same name already exists in the directory (e.g. from a prior packaging attempt that wasn't cleaned up), get that archive swept up by the shell's `*` expansion and bundled into itself — causing infinite recursion or a "ghost" archive.
* **Mandatory rule**: always exclude the target file itself when packaging:
  ```bash
  # tar.gz
  tar -czf skill.tar.gz --exclude="skill.tar.gz" *

  # zip
  zip -r skill.zip * -x "skill.zip"
  ```

---

## 2. Environment & Setup

Octo's underlying installer (`install_agent_skills`) prepares a safe build sandbox for your skill. If your skill includes a `setup.sh`, follow these battle-tested principles:

### 2.1 Multi-OS Branching
OctoMatrix supports a wide range of operating systems. Before running `setup.sh`, the host installer injects the current OS name into an environment variable (e.g. `OCTO_OS`, whose value matches the branches used by `install_dependency`, such as `ubuntu`, `debian`, `centos`, `macos`, etc.).
Your `setup.sh` must branch on this to provide the corresponding install logic:

```bash
#!/bin/bash
# Example setup.sh structure
case "$OCTO_OS" in
    ubuntu|debian)
        setup_debian
        ;;
    centos|rhel)
        setup_redhat
        ;;
    macos)
        setup_macos
        ;;
    *)
        echo "Unsupported OS: $OCTO_OS"
        exit 1
        ;;
esac
```

### 2.2 Rootless Sandbox Extraction
Using `sudo` to request system-level root privileges inside `setup.sh` is **strictly forbidden**. All dependencies must be downloaded offline and "extracted" into a `local_libs` directory inside the skill's own directory.

#### 2.2.1 Guarding Against Silent Failure Masking
Because `apt-get` is "all-or-nothing," passing a large package list to `apt-get download` in one call will silently fail with nothing downloaded at all if even one package doesn't exist for that OS. Adding `2>/dev/null || true` on top of that produces an empty directory with no way to diagnose why.
* **Mandatory rule**: download dependencies one at a time in a `for` loop, so a single missing package doesn't prevent the rest from being extracted successfully.
  ```bash
  mkdir -p local_libs
  for pkg in dependency_a dependency_b dependency_c; do
      apt-get download $pkg 2>/dev/null || echo "Warning: could not download $pkg, skipping."
  done
  dpkg -x *.deb ./local_libs
  rm *.deb
  ```

#### 2.2.2 Cross-Platform Safe Copying (GNU Portability)
When extracting `.so` dynamic libraries or moving files, avoid the `cp -n` (no-clobber) flag flagged as non-portable in newer GNU Coreutils versions, since it can raise warnings on some environments.
* **Recommended**: use `cp -f` for overwriting local temp directories — it's more stable and portable.

### 2.3 Runtime Mounting & Sandboxing

#### 2.3.1 Dynamic Library Mounting
If your `setup.sh` extracts dynamic libraries into `local_libs/usr/lib/...`, be sure to set the environment variable in your skill's entry point so the Agent can load them dynamically at runtime:
```bash
export LD_LIBRARY_PATH="$(pwd)/local_libs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
```

#### 2.3.2 Eliminating the Global Cache Blind Spot (Global Cache Relocation)
Some packages (e.g. browser engines with large binaries, AI model weights) default to downloading huge files into the user's global cache directory (like `~/.cache`), which seriously breaks a skill package's sandbox isolation and portability.
* **Mandatory rule**: force the cache directory to point to a directory owned by the skill itself (e.g. `./.cache`) via an environment variable or config file, and clear it or add it to `.gitignore` before packaging.
  ```bash
  # Example: forcing a local cache variable
  export HEAVY_DEPENDENCY_CACHE_DIR="$(pwd)/.cache"
  ```

### 2.4 Log Purification
A skill should not print system-level error noise during execution that could pollute the Agent's decision-making.
* **Mandatory rule**: when doing environment checks for "non-critical" dependencies (e.g. checking whether an optional CLI tool exists), redirect the error stream to keep output clean.
  ```bash
  # Wrong: pollutes the log
  my_optional_tool --version

  # Correct: silent verification
  my_optional_tool --version 2>/dev/null || echo "Note: my_optional_tool is not installed, related features will be skipped."
  ```

---
**Summary**: with multi-OS branch control, rootless sandbox extraction, guarded loop-based installs, and global cache localization, your skill will have top-tier security, cross-platform portability, and debugging transparency — a solid building block of the OctoMatrix ecosystem.
