# Jules Task Template (Archived / Inactive)

Archived workflow experiment template. Do not use as the current implementation source of truth; current implementation prompts should be prepared for Codex.

---

### Goal
[Describe the specific objective of the PR]

### Before editing
[List any specific documentation or files the coding agent must read before making changes, e.g., `rpg/AGENTS.md`, `rpg/docs/GAME_FOUNDATION.md`, or specific feature specs.]

### Context
[Provide necessary background information, explaining *why* this change is being made and any relevant decisions from the Design & Balance Gem.]

### Files to inspect/edit
- `path/to/file1.py`
- `path/to/file2.py`
- `path/to/new_file.py` (Create)

### Implementation scope
1. [Action 1: e.g., Update function X to do Y]
2. [Action 2: e.g., Add new route metadata to Z]
3. [Action 3: e.g., Ensure backward compatibility with legacy aliases]

### Non-goals
- [Explicitly list what the coding agent should NOT do, e.g., "Do not change gameplay code", "Do not rewrite the Combat Core".]

### Done criteria
- [Criterion 1: e.g., The new function returns the expected value.]
- [Criterion 2: e.g., Tests run successfully without regressions.]

### Tests
- [Describe the testing expectations. E.g., "Run the standard local test command to ensure no regressions." or "Add unit tests for the new function in `test_x.py`."]

### Project state impact
- [Specify if this PR updates confirmed project state. If it does, instruct the coding agent to update `rpg/docs/PROJECT_STATE_CURRENT.md` and describe the change. If not, explicitly state: "No confirmed project state change. Do not update PROJECT_STATE_CURRENT.md."]
