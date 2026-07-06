import logging
from pathlib import Path

from codepulse.db import GraphDB
from codepulse.parser import SourceParser
from codepulse.routes import index_routes


class TestExpressRoutes:
    def test_detect_express_route_in_js_file(self, tmp_path: Path, db: GraphDB, parser: SourceParser):
        (tmp_path / "package.json").write_text('{"dependencies": {"express": "^4.0.0"}}')
        (tmp_path / "app.js").write_text("app.get('/api/foo', handler);\n")

        count = index_routes(str(tmp_path), db, parser)

        assert count > 0
        route_nodes = db.search_nodes("", kind="route")
        assert any("/api/foo" in n.name for n in route_nodes), f"Expected route /api/foo, got: {[n.name for n in route_nodes]}"

    def test_unreadable_file_logs_warning(self, tmp_path: Path, db: GraphDB, parser: SourceParser, caplog):
        (tmp_path / "package.json").write_text('{"dependencies": {"express": "^4.0.0"}}')
        (tmp_path / "app.js").write_text("app.get('/api/foo', handler);\n")
        (tmp_path / "bad.js").write_bytes(b"\xff\xfe\x00\x01")

        caplog.set_level(logging.WARNING)
        count = index_routes(str(tmp_path), db, parser)

        assert count > 0
        assert "Could not read" in caplog.text
        assert "bad.js" in caplog.text
        assert "express" in caplog.text
