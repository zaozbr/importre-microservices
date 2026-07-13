# No Leading Dot Filter

## Rule

Never use a leading `.` (dot) in file paths or shell commands unless it is a genuine relative path (e.g., `./file` or `../file`).

## Applies to

- `read`, `edit`, `write`, `find_file_by_name` and any other file-tool arguments: always pass absolute Windows paths directly, e.g. `F:/importre/orchestrator/index.js` or `/f:/importre/orchestrator/index.js`.
- `exec` commands: do not prefix with `.`. Use commands directly, e.g. `cd "F:\importre" && npm start` or `git status`.

## Pre-send filter (MANDATORY)

Before sending any tool call, verify:
1. Does the file path start with `.`? If yes, remove it. Use `/f:/...` as a safe alternative if the habit persists.
2. Does the exec command start with `. `? If yes, remove the leading dot and space.

If the command is intended to run in the project directory, use `cd "F:\importre" && ...` instead of `. cd ...`.

## Verified workaround

Using the `/f:/importre/...` path format has been verified to work and is harder to accidentally prefix with a dot. Prefer this format when the dot habit persists.

## Deep-search fix protocol

If the assistant repeatedly adds leading dots despite this rule:
- Prefer path format `/f:/importre/...` over `F:/importre/...` because it is harder to accidentally prepend a dot.
- Read every file path out loud as "slash f slash ..." before sending.
- If a dot is detected after sending, immediately retry with the path corrected and do not proceed until the call succeeds.
