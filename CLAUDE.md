## CodePulse

CodePulse builds a semantic knowledge graph of codebases for faster, smarter code exploration.

### If `.codepulse/` exists in the project

**Answer directly with CodePulse — don't delegate exploration to file-reading tools.** CodePulse is the pre-built search index; re-deriving its answers with grep + Read repeats work it already did and costs more for the same result. For "how does X work?", architecture, trace, or where-is-X questions, answer in a handful of CodePulse calls and stop — typically with **zero file reads**.

**Tool selection by intent:**

| Tool | Use For |
|------|---------|
| `codepulse search` | Find a symbol by name |
| `codepulse callers` | Find what calls a function |
| `codepulse callees` | Find what a function calls |
| `codepulse trace` | Show impact radius of a symbol |
| `codepulse serve` | Start MCP server for AI agent integration |

### If `.codepulse/` does NOT exist

Ask the user if they'd like to initialize:

"I notice this project doesn't have CodePulse initialized. Would you like me to run `codepulse init && codepulse index .` to build a code knowledge graph?"
