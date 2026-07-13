# No Leading Dot Filter

## Rule

Never use a leading `.` (dot) in file paths or shell commands unless it is a genuine relative path (e.g., `./file` or `../file`).

## Applies to

- `read`, `edit`, `write`, `find_file_by_name` and any other file-tool arguments: always pass absolute Windows paths directly, e.g. `F:/importre/orchestrator/index.js`.
- `exec` commands: do not prefix with `.`. Use commands directly, e.g. `cd "F:\importre" && npm start` or `git status`.

## Pre-send filter

Before sending any tool call, verify:
1. Does the file path start with `.`? If yes, remove it.
2. Does the exec command start with `. `? If yes, remove the leading dot and space.

If the command is intended to run in the project directory, use `cd "F:\importre" && ...` instead of `. cd ...`.
