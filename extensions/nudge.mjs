const NUDGE = `Before executing generated code, run the smallest relevant validation step first (for Python: python -m py_compile <file>; for JavaScript: node --check <file>). Read the last line of any traceback and fix the cause before rerunning.`;
const FAILURE = /Traceback \(most recent call last\)|SyntaxError|Unexpected token|JSONDecodeError/i;

export default function (pi) {
  pi.on("before_agent_start", async (event) => ({
    systemPrompt: event.systemPrompt + "\n\n" + NUDGE,
  }));
  pi.on("tool_execution_end", async (event) => {
    if (!event.isError || !FAILURE.test(JSON.stringify(event.result || {}))) return;
    return { message: { customType: "learning-nudge", content: NUDGE, display: true } };
  });
}
