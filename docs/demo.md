# CodePulse Demo Script

## Demo target

Use a small public repo first so the demo is fast and reproducible:

```bash
bash scripts/demo-codepulse-on-repo.sh https://github.com/pallets/flask
```

## What to capture

1. Terminal: clone/index output with file/symbol/edge counts.
2. Terminal: `codepulse validate` output.
3. Terminal: `codepulse search Flask --limit 5` output.
4. Terminal: symbol note roundtrip:
   ```bash
   codepulse note add "src/flask/app.py:Flask" "Central application object; inspect before changing routing or config." --source demo
   codepulse note list "src/flask/app.py:Flask"
   codepulse note search routing
   ```
5. Dashboard screenshot after `cd web && npm run dev`.

## X thread skeleton

AI coding agents still inspect repos like blind grep machines.

I’m building CodePulse: a local-first semantic code graph + MCP server for agents.

It parses repos into:
- symbols
- edges
- callers/callees
- impact radius
- searchable symbol notes

The new bit: agents can now write memory back onto code symbols.

So the next edit starts with repo-local context, not rediscovery.
