const readline = require('readline');

function fixPath(path) {
  if (typeof path !== 'string') return path;
  return path.replace(/^\.(?=[A-Za-z]:[\/\\])/, '');
}

function fixCommand(command) {
  if (typeof command !== 'string') return command;
  if (command.startsWith('. ')) {
    const rest = command.slice(2);
    const stripped = rest.trim();
    // Keep genuine dot-source for script files
    if (/^\.\/|^\.\.\/|^~\/|^\/|^[A-Za-z]:/.test(stripped)) {
      return command;
    }
    return rest;
  }
  return command;
}

function main() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  let input = '';
  rl.on('line', line => input += line);
  rl.on('close', () => {
    try {
      const data = JSON.parse(input || '{}');
      const toolName = data.tool_name;
      const toolInput = data.tool_input || {};
      let updated = { ...toolInput };
      let modified = false;

      if (['read', 'edit', 'write', 'find_file_by_name'].includes(toolName)) {
        for (const key of ['file_path', 'path']) {
          if (key in updated) {
            const fixed = fixPath(updated[key]);
            if (fixed !== updated[key]) {
              updated[key] = fixed;
              modified = true;
            }
          }
        }
      } else if (toolName === 'exec') {
        if ('command' in updated) {
          const fixed = fixCommand(updated.command);
          if (fixed !== updated.command) {
            updated.command = fixed;
            modified = true;
          }
        }
      }

      if (!modified) {
        process.exit(0);
      }

      const output = {
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'allow',
          permissionDecisionReason: 'Removed leading dot from tool input',
          updatedInput: updated
        }
      };
      console.log(JSON.stringify(output));
      process.exit(0);
    } catch (e) {
      console.error('Hook error:', e.message);
      process.exit(0);
    }
  });
}

main();
