"""End-to-end integration tests.

Scans a known multi-file project, then verifies the full pipeline:
scan -> index -> search -> callers -> callees -> validate.
"""

import tempfile
from pathlib import Path

import pytest

from codepulse.graph import CodePulse, CodePulseConfig


@pytest.fixture
def fixture_project(tmp_path):
    """Create a small multi-file project."""
    (tmp_path / "main.py").write_text("""
from models import User
from utils import format_name

def create_user(name):
    user = User(name)
    user.save()
    return user

def process(name):
    display = format_name(name)
    return create_user(display)

def run():
    process("Alice")
""")

    (tmp_path / "models.py").write_text("""
class User:
    def __init__(self, name):
        self.name = name

    def save(self):
        return True

    def get_name(self):
        return self.name
""")

    (tmp_path / "utils.py").write_text("""
def format_name(first, last=""):
    if last:
        return first + " " + last
    return first
""")

    return tmp_path


class TestE2E:
    def test_full_pipeline(self, fixture_project):
        # 1. Initialize
        tmp = tempfile.mkdtemp()
        config = CodePulseConfig(data_dir=tmp)
        cp = CodePulse(config)
        cp.db.initialize()

        # 2. Index (includes cross-file resolution)
        result = cp.index_all(str(fixture_project))
        assert result.files_indexed >= 3
        assert result.symbols_found >= 8
        assert len(result.errors) == 0

        # 3. Validate
        report = cp.validate()
        assert report.total_nodes >= 8
        assert report.total_edges >= 4
        assert report.orphan_edges == 0

        # 4. Search
        results = cp.search("greet")
        # No greet in this project, but search should work
        results = cp.search("create_user")
        assert len(results) >= 1

        # 5. Callers — who calls User.save?
        results = cp.search("save")
        assert len(results) >= 1
        save_id = results[0].id
        callers = cp.get_callers(save_id, depth=1)
        caller_names = {c[0].name for c in callers}
        assert "create_user" in caller_names

        # 6. Callees — what does create_user call?
        cu_results = cp.search("create_user")
        cu_id = None
        for r in cu_results:
            if r.name == "create_user" and r.kind == "function":
                cu_id = r.id
                break
        assert cu_id is not None
        callees = cp.get_callees(cu_id, depth=1)
        callee_names = {c[0].name for c in callees}
        assert "save" in callee_names or "User.save" in callee_names  # cross-file call to User.save

        # 7. Impact — changing User affects what?
        user_results = cp.search("User")
        user_id = None
        for r in user_results:
            if r.name == "User" and r.kind == "class":
                user_id = r.id
                break
        assert user_id is not None
        impact = cp.get_impact_radius(user_id, depth=2)
        all_impacted = {n.name for depth in impact.values() for n in depth}
        assert "create_user" in all_impacted  # calls User()

        cp.db.close()
