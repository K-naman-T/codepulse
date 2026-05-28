import json
import shutil
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

FIELD_TYPES = {
    "name": str,
    "url": str,
    "commit": str,
    "language": str,
    "path": str,
    "use_scip": bool,
    "max_seconds": (int, float),
    "min_symbols": int,
    "max_internal_orphans": int,
    "manifest_path": str,
}


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
        if not isinstance(repos, list):
            raise ValueError("Field repos must be a list")
        report = BatchReport()

        for entry in repos:
            self._validate_entry(entry)
            result = self._process_entry(entry, mpath.parent)
            report.repos.append(result)

        report_dict = report.to_dict()
        Path(output_path).write_text(json.dumps(report_dict, indent=2))
        return report_dict

    def _validate_entry(self, entry: dict) -> None:
        if not isinstance(entry, dict):
            raise ValueError("Each repo entry must be a mapping")
        missing = [f for f in REQUIRED_FIELDS if f not in entry]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        for field, expected_type in FIELD_TYPES.items():
            if field in entry and not self._matches_type(entry[field], expected_type):
                expected_name = self._type_name(expected_type)
                raise ValueError(f"Field {field} must be {expected_name}")

    def _matches_type(self, value: object, expected_type: type | tuple[type, ...]) -> bool:
        if expected_type is bool:
            return type(value) is bool
        if expected_type is int:
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == (int, float):
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        return isinstance(value, expected_type)

    def _type_name(self, expected_type: type | tuple[type, ...]) -> str:
        if isinstance(expected_type, tuple):
            return " or ".join(t.__name__ for t in expected_type)
        return expected_type.__name__

    def _process_entry(self, entry: dict, manifest_dir: Path) -> BatchResult:
        result = BatchResult(name=entry["name"])
        start = time.time()
        temp_paths: list[Path] = []
        cp: CodePulse | None = None

        try:
            repo_path = self._resolve_repo(entry, manifest_dir, temp_paths)
            index_path = str(Path(repo_path) / entry["path"])

            batch_data_dir = self._make_temp_dir(
                prefix=f"codepulse-batch-{entry['name']}-",
                temp_paths=temp_paths,
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
                if not mpath.exists():
                    raise FileNotFoundError(f"Golden manifest not found: {mpath}")
                with open(mpath) as f:
                    golden = yaml.safe_load(f)
                from codepulse.validation import compare_to_golden
                comparison = compare_to_golden(cp.db, golden)
                result.precision = round(comparison.symbols.precision, 4)

        except Exception as e:
            result.error = str(e)
            result.passed = False
        finally:
            if cp is not None:
                cp.close()
            for path in temp_paths:
                shutil.rmtree(path, ignore_errors=True)

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _make_temp_dir(self, prefix: str, temp_paths: list[Path]) -> Path:
        path = Path(tempfile.mkdtemp(prefix=prefix))
        temp_paths.append(path)
        return path

    def _resolve_repo(self, entry: dict, manifest_dir: Path, temp_paths: list[Path]) -> str:
        url = entry["url"]
        commit = entry["commit"]

        if url.startswith("file://"):
            url = url[len("file://"):]

        repo_path = Path(url)

        if not repo_path.is_absolute():
            repo_path = manifest_dir / repo_path

        repo_path = repo_path.resolve()

        is_git_checkout = (repo_path / ".git").exists()

        if repo_path.exists() and not is_git_checkout:
            return str(repo_path)

        if repo_path.exists() and is_git_checkout:
            if not commit or commit == "local":
                return str(repo_path)
            clone_dir = self._make_temp_dir("codepulse-batch-clone-", temp_paths)
            dest = clone_dir / entry["name"]
            self._run_git(
                ["clone", str(repo_path), str(dest)],
                f"clone local repository {repo_path}",
            )
            self._checkout_commit(dest, commit)
            return str(dest)

        clone_dir = self._make_temp_dir("codepulse-batch-clone-", temp_paths)
        dest = clone_dir / entry["name"]
        self._run_git(["clone", url, str(dest)], f"clone repository {url}")
        if commit and commit != "local":
            self._checkout_commit(dest, commit)
        return str(dest)

    def _checkout_commit(self, repo_path: Path, commit: str) -> None:
        self._run_git(["checkout", commit], f"checkout commit {commit}", cwd=repo_path)

    def _run_git(self, args: list[str], context: str, cwd: Path | None = None) -> None:
        try:
            subprocess.run(
                ["git", *args],
                cwd=str(cwd) if cwd is not None else None,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or e.stdout or "").strip()
            message = f"Failed to {context}"
            if detail:
                message = f"{message}: {detail}"
            raise RuntimeError(message) from e
