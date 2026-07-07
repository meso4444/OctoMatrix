
## Cyberbrain GHOST System Guidelines

Agents must strictly comply with the following GHOST operation specifications to ensure long-term GHOST continuity and system stability.

### 1. Core Operation Tools (Toolbox)
- **`octo_ghost_updater.py`**: **The sole GHOST writing entry point**. Agents must proactively and regularly execute this script to record "keywords," "file paths," and "semantic outlines" to ensure important task contexts are permanently saved.
- **`octo_ghost_reader.py`**: **Soul Reader**. Used to read structured JSON GHOST indices (supporting current/snapshot/monthly levels).
- **`dive_into_the_shell.py`**: **Shell Deep Diver**. Used to perform deep retrieval of keywords in historical terminal logs (Raw Logs).

### 2. Daily GHOST Update Guidelines (Ghost Writing Workflow)
Agents should follow the "outline first, then keywords & paths" process below to record GHOST after completing phased tasks:

1. **Step 1: Write Semantic Outline (Outline First)**
   - Prioritize writing detailed decision logic, task records, and execution results.
   - Semantic outlines must authentically represent conversation content and technical details.

2. **Step 2: Extract Real Keywords (Literal Keywords Extraction)**
   - **Core Principle**: Extract keywords from the outline you just wrote.
   - **No Translation**: Strictly prohibit converting keywords to English (unless the original is English) or re-interpreting semantically.
   - **Authentic Representation**: Must preserve the original form of keywords as they appear in terminal logs to ensure subsequent `dive` retrieval can match precisely.

3. **Step 3: Absolute Paths of Related Important Files (Paths)**

4. **Execute Write Command**
   - Example command execution:
    ```bash
    python3 octo_cyberbrain/octo_ghost_updater.py --outline "semantic outline" --keywords "keyword1,keyword2" --paths "/file/path1,/file/path2"
    ```

### 3. Advanced Operation Guidelines (Knowledge)
- **Manual Location**: For more detailed parameter explanations and Deep Dive retrieval techniques, refer to `octo_cyberbrain/CYBERBRAIN_GUIDE.md`.

---

## Notification System Operation Guidelines

### Message Sending Specifications

1. **Unique Delivery Channel**: **`matrix_notifier.py` is the user's only pipeline for receiving message content, the response content must not be simplified or omitted.**
2. **Quote Usage Principles**:
   - Consistently wrap the outermost layer with **single quotes** `'`.
   - Within messages, you can freely use double quotes `"`, dollar signs `$`, etc., without needing extra escaping.
   - If the message itself contains single quotes, it's recommended to use double quotes for the outer layer instead, or escape the inner single quotes (`\'`).
   - Don't use \*\* for text emphasis in messages

2. **Sending Examples**:

```bash
## General response
python3 toolbox/matrix_notifier.py '💬 Hello! I am {agent_name}\nI have received your message and am responding'

## Send document (with description)
python3 toolbox/matrix_notifier.py --file document /path/to/report.pdf '📄 Task Completion Report'

## Send photo
python3 toolbox/matrix_notifier.py --file photo /tmp/screenshot.png 'Screenshot verification'

## Send video
python3 toolbox/matrix_notifier.py --file video /tmp/demo.mp4 'Demo video\nDuration: 5 minutes'

## Send audio
python3 toolbox/matrix_notifier.py --file audio /tmp/notification.wav 'Voice confirmation'
```

3. **Visual Expression Standards**:

	Agents should send corresponding Avatar emotion stickers based on message content and current emotional state.

	#### Usage Examples

```bash
## Send independent emotion sticker
python3 toolbox/matrix_notifier.py --file sticker avatar/emojis/happy.webm

```
---

4. **Security Notes**:

   - Avoid including sensitive information in notifications, such as personal data, passwords, etc.

5. **URL Link Processing Standards**:

   - **Reject Guessing**: Never "calculate" or "compose" URLs on your own (e.g., guessing based on date format). Only use links explicitly returned by search tools.
   - **Resolve Redirects**: If search results are redirect links (such as `google.com/url?...` or `vertexaisearch...`), **must** use Python `requests.head()` or `curl -I` to resolve the original true URL (Canonical URL).
   - **Verify Validity**: Before sending to users, verify that URLs can be accessed normally (returning HTTP 200/301/302).
   - **Source Verification**: Confirm that the domain of the final URL matches the claimed news source (e.g., if the source says PR Newswire, the URL domain should be `prnewswire.com`).

---

## Awake System Operation Guidelines

The matrix issues commands to Agents on schedule through the "Awake System". For detailed implementation, see `knowledge/AWAKE_FUNCTIONALITY.md`.

Agents **must use the dedicated script** to manage automated behavior. Direct editing of `awake.yaml` or using bare curl is strictly prohibited.

- **Add Awake Tasks (Supports trigger: daily, weekly, monthly, interval, date, cron)**:
    ```bash
    python3 toolbox/awake_task_manager.py register \
      --id "task_id" --target "{agent_name}" --trigger "cron" \
      --hour 9 --minute 30 --prompt "Execute task content"
    ```
- **View and Manage**:
    - `python3 toolbox/awake_task_manager.py list`
    - `python3 toolbox/awake_task_manager.py delete --id "task_id"`
    - `python3 toolbox/awake_task_manager.py update --id "task_id" --hour 10 --prompt "New content"`

---
