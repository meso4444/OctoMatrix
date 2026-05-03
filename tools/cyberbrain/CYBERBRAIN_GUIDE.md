# 🧠 Cyberbrain GHOST System Operation Manual

This directory contains all core tools related to Agent GHOST system. Agents should follow this manual to perform GHOST writing, reading, and deep-dive retrieval.

---

## 1. GHOST Writing: `octo_ghost_updater.py`

*   **Purpose**: This is the **only legal method** for Agents to write semantic outlines, keywords, and file paths.
*   **Execution modes**:
    *   **CLI mode (recommended for Agents)**: Inject via parameters in one shot, completely avoiding EOF errors.
        `python3 octo_cyberbrain/octo_ghost_updater.py --outline "Semantic outline" --keywords "keyword1,keyword2" --paths "/file/path1,/file/path2"`
    *   **Interactive mode (human debugging)**: Run without parameters, input as prompted.
*   **Key responsibility**: Agents must actively and regularly execute this tool to ensure task context is not lost due to system reorganization.

---

## 2. Soul Reading: `octo_ghost_reader.py`

*   **Purpose**: Read structured JSON GHOST indices.
*   **Parameter explanation**:
    *   `--level current`: Read currently accumulating GHOST status.
    *   `--level snapshot`: Read aggregated GHOST at snapshot level.
    *   `--level monthly --months N`: Read monthly consolidated index for past N months.
*   **Execution example**: `python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot`

---

## 3. Shell Deep-dive: `dive_into_the_shell.py`

*   **Purpose**: Full-text search on historical terminal logs (Raw Logs).
*   **Core logic**: Default uses "Latest-First", keeping records closest to present.
*   **Parameter explanation**:
    *   `--keyword`: Specify one or more search targets (required).
    *   `--level`: Specify search depth (`current`/`snapshot`/`monthly`/`yearly`).
    *   `--offset N`: **Key to deep digging**. Skip latest N lines, browse far older history (pagination mechanism).
    *   `-C`: Specify context line count (default 50).
*   **Execution examples**:
    *   *Normal context reconstruction*: `python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot --keyword "important event"`
    *   *Dig deeper history*: `python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot --keyword "important event" --offset 1000`
*   **Protection mechanism**: Single output limited to 1000 lines to prevent token explosion.

---

## 4. Legacy migration: `octo_ghost_legacy_converter.py`

*   **Purpose**: One-time conversion of old `.md` format Ghost to new `.json` format.
*   **Execution method**: `python3 octo_cyberbrain/octo_ghost_legacy_converter.py`
