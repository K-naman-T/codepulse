# CodePulse — tryable in 60 seconds

## Install

```bash
git clone https://github.com/K-naman-T/codepulse.git
cd codepulse
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Demo (this repo)

```bash
mkdir -p /tmp/cp-demo && cd /tmp/cp-demo
codepulse init
codepulse index /path/to/codepulse/src
codepulse repo-map
codepulse search "parse"
codepulse callers "/path/to/codepulse/src/codepulse/parser.py:SourceParser.parse_file"
codepulse validate
```

Expected: non-zero **Symbols** and **Edges** after index; search returns function IDs.

## MCP

```bash
codepulse mcp   # stdio MCP server for coding agents
```

## Proof (factory hot path)

Factory job `codepulse-tryable-001` recorded a controller transcript with index → search → callers → validate green after bundling the real `sdd/complete-e2e-codepulse` branch (GitHub `main` was previously a stub initial commit).
