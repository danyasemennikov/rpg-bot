# Jules Task Template

Use this template to generate structured prompts for Jules, the coding agent, for implementation PRs.

---

### Goal
[Describe the specific objective of the PR]

### Before editing
[List any specific documentation or files Jules must read before making changes, e.g., `AGENTS.md`, `GAME_FOUNDATION.md`, or specific feature specs.]

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
- [Explicitly list what Jules should NOT do, e.g., "Do not change gameplay code", "Do not rewrite the Combat Core".]

### Done criteria
- [Criterion 1: e.g., The new function returns the expected value.]
- [Criterion 2: e.g., Tests run successfully without regressions.]

### Tests
- [Describe the testing expectations. E.g., "Run the standard local test command to ensure no regressions." or "Add unit tests for the new function in `test_x.py`."]

### Project state impact
- [Specify if this PR updates confirmed project state. If it does, instruct Jules to update `rpg/docs/PROJECT_STATE_CURRENT.md` and describe the change. If not, explicitly state: "No confirmed project state change. Do not update PROJECT_STATE_CURRENT.md."]
