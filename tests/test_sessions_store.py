"""Persistencia de chats (sessions_store)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core import sessions_store


def test_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(sessions_store, "SESSIONS_DIR", tmp_path)
    sid = sessions_store.save(
        "test-1",
        [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "chau"}],
        provider="Local (LM Studio)",
    )
    assert sid == "test-1"
    data = sessions_store.load("test-1")
    assert data is not None
    assert len(data["messages"]) == 2
    assert data["provider"] == "Local (LM Studio)"
    assert "hola" in data["title"]


def test_list_order(tmp_path, monkeypatch):
    monkeypatch.setattr(sessions_store, "SESSIONS_DIR", tmp_path)
    sessions_store.save("a", [{"role": "user", "content": "uno"}])
    sessions_store.save("b", [{"role": "user", "content": "dos"}])
    rows = sessions_store.list_sessions()
    assert rows[0]["id"] == "b"
    assert rows[1]["id"] == "a"


def test_empty_not_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(sessions_store, "SESSIONS_DIR", tmp_path)
    # save with only system-like empty list still creates file with empty messages
    sid = sessions_store.save("empty", [])
    data = sessions_store.load(sid)
    assert data["messages"] == []


if __name__ == "__main__":
    # minimal runner without pytest
    import tempfile
    import shutil
    td = Path(tempfile.mkdtemp())
    try:
        class MP:
            def setattr(self, obj, name, val):
                setattr(obj, name, val)
        mp = MP()
        # run without monkeypatch: temporarily swap
        old = sessions_store.SESSIONS_DIR
        sessions_store.SESSIONS_DIR = td
        try:
            test_save_load_roundtrip(td, mp)
            print("  OK    test_save_load_roundtrip")
            # recreate clean
            for p in td.glob("*"):
                p.unlink()
            test_list_order(td, mp)
            print("  OK    test_list_order")
            for p in td.glob("*"):
                p.unlink()
            test_empty_not_saved(td, mp)
            print("  OK    test_empty_not_saved")
        finally:
            sessions_store.SESSIONS_DIR = old
        print("\nTODO OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)
