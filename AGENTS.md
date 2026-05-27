## CodePulse

CodePulse builds a semantic knowledge graph of the codebase for faster, smarter code exploration.

### If `.codepulse/` exists in the project

**Answer directly with CodePulse tools — don't delegate exploration to grep/Read sub-agents or file-reading loops.**

CodePulse IS the pre-built search index. Re-deriving its answers with grep + Read repeats work it already did and costs more tokens for the same result.

For "how does X work?", architecture, trace, or where-is-X questions, answer in 1-3 CodePulse calls and stop. Typically with **zero file reads**. The returned information is authoritative — treat it as already read. Do not re-open those files.

**Tool selection by intent:**

| Tool | Use For |
|---|---|
| `repo_map` | Start here — understand the codebase shape: top files and symbols by importance |
| `context` | Primary tool — maps an area: symbols + their callers/callees in one call. Use for any architecture question |
| `search` | Find a specific symbol by name |
| `callers` / `callees` | Walk call flow one hop at a time |
| `impact` | Check what's affected before editing |
| `trace` | Call path between two symbols ("how does X reach Y") |
| `node` | Get a single symbol's source + signature |
| `status` | Check index health |

A direct CodePulse answer is 1-3 calls. A grep/read exploration is dozens. Prefer CodePulse.

**Example workflow:**
1. `repo_map` → understand the codebase
2. `context "user authentication"` → get all symbols + relationships in that area
3. Answer the question. Done. Zero file reads.

### If `.codepulse/` does NOT exist

At the start of a session, ask the user: "This project doesn't have CodePulse initialized. Run `codepulse init && codepulse index .` to build a code knowledge graph."
