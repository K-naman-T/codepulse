import sqlite3
import tempfile
from pathlib import Path

from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse
from codepulse.db import GraphDB, Node


def test_gexf_export_well_formed():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "graph.db"
        config = CodePulseConfig()
        config.data_dir = tmp
        db = GraphDB(str(db_path))
        db.initialize()
        db.upsert_node(Node(id="file_a.py:foo", name="file_a.py:foo", kind="function", file_path="file_a.py", line_start=1, language="python"))
        db.upsert_node(Node(id="file_a.py:bar", name="file_a.py:bar", kind="function", file_path="file_a.py", line_start=5, language="python"))
        db.conn.execute("INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
                        ["file_a.py:foo", "file_a.py:bar", "calls"])
        db.conn.commit()
        db.close()

        cp = CodePulse(config)

        result = Path(tmp) / "out.gexf"
        from codepulse.cli import _export_gexf
        _export_gexf(cp, str(result))

        text = result.read_text()
        assert '<?xml version="1.0" encoding="UTF-8"?>' in text
        assert '<gexf xmlns="http://gexf.net/1.3"' in text
        assert text.count("<node ") == 2
        assert text.count("<edge ") == 1
        assert "label=\"foo\"" in text
        assert "label=\"bar\"" in text


def test_gexf_export_empty():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "graph.db"
        config = CodePulseConfig()
        config.data_dir = tmp
        db = GraphDB(str(db_path))
        db.initialize()
        db.close()

        cp = CodePulse(config)
        result = Path(tmp) / "out.gexf"
        from codepulse.cli import _export_gexf
        _export_gexf(cp, str(result))
        text = result.read_text()
        assert "<nodes>" in text
        assert "</nodes>" in text
        assert "<edges>" in text


def test_gexf_export_label_extraction():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "graph.db"
        config = CodePulseConfig()
        config.data_dir = tmp
        db = GraphDB(str(db_path))
        db.initialize()
        db.upsert_node(Node(id="path:barename", name="path:barename", kind="function", file_path="path.py", line_start=1, language="python"))
        db.upsert_node(Node(id="justname", name="justname", kind="function", file_path="other.py", line_start=1, language="python"))
        db.close()

        cp = CodePulse(config)
        result = Path(tmp) / "out.gexf"
        from codepulse.cli import _export_gexf
        _export_gexf(cp, str(result))
        text = result.read_text()
        assert "label=\"barename\"" in text
        assert "label=\"justname\"" in text


def test_gexf_export_edge_matching():
    """Edge source/target IDs may differ from node IDs; verify fallback matching."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "graph.db"
        config = CodePulseConfig()
        config.data_dir = tmp
        db = GraphDB(str(db_path))
        db.initialize()
        db.upsert_node(Node(id="/src/a.py:func_a", name="/src/a.py:func_a", kind="function", file_path="/src/a.py", line_start=1, language="python"))
        db.upsert_node(Node(id="/src/b.py:func_b", name="/src/b.py:func_b", kind="function", file_path="/src/b.py", line_start=5, language="python"))
        db.conn.execute("INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
                        ["/src/a.py:func_a", "/src/b.py:func_b", "calls"])
        db.conn.commit()
        db.close()

        cp = CodePulse(config)
        result = Path(tmp) / "out.gexf"
        from codepulse.cli import _export_gexf
        _export_gexf(cp, str(result))
        text = result.read_text()
        assert text.count("<edge ") == 1
