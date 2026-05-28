import json
import subprocess
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
import yaml

from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse

REQUIRED_FIELDS = [
    "name", "url", "commit", "language", "path",
    "use_scip", "max_seconds", "min_symbols", "max_internal_orphans",
]


@dataclass
class BatchResult:
    name: str = ""
    passed: bool = False
    duration_seconds: float = 0.0
    files_indexed: int = 0
    symbols_found: int = 0
    edges_found: int = 0
    total_nodes: int = 0
    total_edges: int = 0
    orphan_parent_refs: int = 0
    orphan_edges: int = 0
    issues: int = 0
    error: str | None = None
    precision: float | None = None


@dataclass
class BatchReport:
    repos: list[BatchResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        total = len(self.repos)
        passed = sum(1 for r in self.repos if r.passed)
        failed = total - passed
        return {
            "summary": {
                "total_repos": total,
                "total_passed": passed,
                "total_failed": failed,
            },
            "repos": [asdict(r) for r in self.repos],
        }


class BatchValidator:
    def run(self, manifest_path: str, output_path: str) -> dict:
        mpath = Path(manifest_path)
        if not mpath.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(mpath) as f:
            manifest = yaml.safe_load(f) or {}

        repos = manifest.get("repos", [])
        report = BatchReport()

        for entry in repos:
            self._validate_entry(entry)
            result = self._process_entry(entry, mpath.parent)
            report.repos.append(result)

        report_dict = report.to_dict()
        Path(output_path).write_text(json.dumps(report_dict, indent=2))
        return report_dict

    def _validate_entry(self, entry: dict) -> None:
        missing = [f for f in REQUIRED_FIELDS if f not in entry]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

    def _process_entry(self, entry: dict, manifest_dir: Path) -> BatchResult:
        result = BatchResult(name=entry["name"])
        start = time.time()

        try:
            repo_path = self._resolve_repo(entry, manifest_dir)
            index_path = str(Path(repo_path) / entry["path"])

            batch_data_dir = Path(
                tempfile.mkdtemp(prefix=f"codepulse-batch-{entry['name']}-")
            )
            config = CodePulseConfig(
                data_dir=str(batch_data_dir),
                use_scip=entry["use_scip"],
            )
            cp = CodePulse(config)
            cp.db.initialize()

            index_result = cp.index_all(index_path)

            result.files_indexed = index_result.files_indexed
            result.symbols_found = index_result.symbols_found
            result.edges_found = index_result.edges_found

            validate_report = cp.validate()
            result.total_nodes = validate_report.total_nodes
            result.total_edges = validate_report.total_edges
            result.orphan_parent_refs = validate_report.orphan_parent_refs
            result.orphan_edges = validate_report.orphan_edges
            result.issues = len(validate_report.issues)

            min_symbols = entry["min_symbols"]
            max_orphans = entry["max_internal_orphans"]
            total_orphans = (
                validate_report.orphan_parent_refs + validate_report.orphan_edges
            )

            if index_result.errors:
                result.error = "; ".join(index_result.errors[:5])

            elapsed = time.time() - start
            within_time = elapsed <= entry["max_seconds"]
            if not within_time:
                message = f"Exceeded max_seconds={entry['max_seconds']}"
                result.error = f"{result.error}; {message}" if result.error else message

            result.passed = (
                not index_result.errors
                and result.symbols_found >= min_symbols
                and total_orphans <= max_orphans
                and validate_report.ok
                and within_time
            )

            manifest_path = entry.get("manifest_path")
            if manifest_path:
                mpath = Path(manifest_path)
                if not mpath.is_absolute():
                    mpath = manifest_dir / mpath
                if mpath.exists():
                    with open(mpath) as f:
                        golden = yaml.safe_load(f)
                    from codepulse.validation import compare_to_golden
                    comparison = compare_to_golden(cp.db, golden)
                    result.precision = round(comparison.symbols.precision, 4)

            cp.close()

        except Exception as e:
            result.error = str(e)
            result.passed = False

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _resolve_repo(self, entry: dict, manifest_dir: Path) -> str:
        url = entry["url"]
        commit = entry["commit"]

        if url.startswith("file://"):
            url = url[len("file://"):]

        repo_path = Path(url)

        if not repo_path.is_absolute():
            repo_path = manifest_dir / repo_path

        repo_path = repo_path.resolve()

        if repo_path.exists() and not (repo_path / ".git").is_dir():
            return str(repo_path)

        if repo_path.exists() and (repo_path / ".git").is_dir():
            if commit and commit != "local":
                subprocess.run(
                    ["git", "checkout", commit],
                    cwd=str(repo_path), capture_output=True, check=False,
                )
            return str(repo_path)

        clone_dir = Path(tempfile.mkdtemp(prefix="codepulse-batch-clone-"))
        dest = clone_dir / entry["name"]
        subprocess.run(
            ["git", "clone", url, str(dest)],
            capture_output=True, check=True,
        )
        if commit and commit != "local":
            subprocess.run(
                ["git", "checkout", commit],
                cwd=str(dest), capture_output=True, check=True,
            )
        return str(dest)
