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
    *   `--level snapshot [--range START-END]`: Read aggregated GHOST at
        snapshot level, sorted by recency, 1 = most recent. **Defaults to
        `--range 1-30`** (the sole automated use case is right after a GHOST
        reset/wake, using time as a proxy for a topic context that doesn't
        exist yet). If nothing in the default range relates to the current
        discussion topic, page further back yourself, e.g. `--range 31-100`,
        then `--range 101-200` if still nothing — the pacing and judgment of
        when to stop is entirely up to the Agent. Range output is **not
        alphabetized** (recency order is preserved); keep each page chunk
        around 30~100 rather than requesting a huge range and dumping it all
        into `dive_into_the_shell.py` at once.
    *   `--level monthly --month YYYY-MM`: Read the consolidated index for a
        specific month (required; no fuzzy "past N months" mode).
    *   `--level yearly --year YYYY`: Read the consolidated index for a
        specific year (required).
    *   monthly/yearly have no topic-filtering capability, deliberately —
        they're cold memory, and judging relevance is the Agent's job after
        reading the full list; output stays alphabetized for easy manual
        browsing.
*   **Execution examples**:
    *   *Wake / general context reconstruction*: `python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot`
    *   *Page further back when nothing relevant is found*: `python3 octo_cyberbrain/octo_ghost_reader.py --level snapshot --range 31-100`
    *   *Look up a specific month*: `python3 octo_cyberbrain/octo_ghost_reader.py --level monthly --month 2026-03`

---

## 3. Shell Deep-dive: `dive_into_the_shell.py`

*   **Purpose**: Full-text search on historical terminal logs (Raw Logs).
*   **Core logic**: Default uses "Latest-First", keeping records closest to present.
*   **Parameter explanation**:
    *   `--keyword`: Specify one or more search targets (required).
    *   `--level`: Specify search depth (`current`/`snapshot`/`monthly`/`yearly`).
    *   `--level monthly --month YYYY-MM` / `--level yearly --year YYYY`:
        monthly/yearly must specify an exact target month/year (required);
        this searches only that single archive, not every archive that exists.
    *   `--offset N`: **Key to deep digging**. Skip latest N lines, browse far older history (pagination mechanism).
    *   `-C`: Specify context line count (default 20).
*   **Execution examples**:
    *   *Normal context reconstruction*: `python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot --keyword "important event"`
    *   *Dig deeper history*: `python3 octo_cyberbrain/dive_into_the_shell.py --level snapshot --keyword "important event" --offset 1000`
    *   *Look up a specific month*: `python3 octo_cyberbrain/dive_into_the_shell.py --level monthly --month 2026-03 --keyword "important event"`
*   **Protection mechanism**: Single output limited to 1000 lines to prevent token explosion.

---

## 4. Legacy migration: `octo_ghost_legacy_converter.py`

*   **Purpose**: One-time conversion of old `.md` format Ghost to new `.json` format.
*   **Execution method**: `python3 octo_cyberbrain/octo_ghost_legacy_converter.py`
