# CodePulse Benchmark

Measures how much faster OpenCode runs WITH CodePulse's MCP server vs WITHOUT.

## How it works

1. Saves current OpenCode config
2. Creates a temp config WITHOUT the codepulse MCP server
3. Runs `opencode run --format json "<question>"` for N iterations
4. Restores original config (WITH codepulse MCP)
5. Runs again for N iterations
6. Computes median metrics and savings percentage

## Run

```bash
./scripts/benchmark/run.sh --repo raftaar-ai --runs 4
```

## Questions

- `raftaar-ai`: Architecture question about auth system
- `codepulse`: How code parsing works

## Timing notes

Each `opencode run` takes 1-15 minutes depending on question complexity and model speed. A full benchmark with 4 runs per arm (8 total) can take 30-120 minutes. Use `--runs 1` for a quick smoke test.

## Metrics

| Metric | Source |
|---|---|
| Cost | Sum of `step_finish.part.cost` |
| Total tokens | Sum of `step_finish.part.tokens.total` |
| Tool calls | Count of `tool_use` events |
| Wall time | Last timestamp minus first |
| Cache reads | Sum of `step_finish.part.tokens.cache.read` |
