"""Escritura de .env desde la UI (set_env_var)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.model_catalog import set_env_var


def _run():
    import tempfile
    td = Path(tempfile.mkdtemp())
    env = td / ".env"
    env.write_text("FOO=1\nBAR=2\n", encoding="utf-8")

    ok, det = set_env_var("FOO", "99", env_path=env)
    assert ok, det
    assert "FOO=99" in env.read_text(encoding="utf-8")
    print("  OK    test_replace_existing")

    ok, det = set_env_var("NEWVAR", "xyz", env_path=env, create_if_missing=True)
    assert ok, det
    assert "NEWVAR=xyz" in env.read_text(encoding="utf-8")
    print("  OK    test_create_missing")

    ok, det = set_env_var("NOPE", "x", env_path=env, create_if_missing=False)
    assert not ok
    print("  OK    test_refuse_create")

    # create .env from scratch
    env2 = td / "nuevo.env"
    ok, det = set_env_var("A", "1", env_path=env2, create_if_missing=True)
    assert ok and env2.exists(), det
    print("  OK    test_create_file")

    print("\nTODO OK")


if __name__ == "__main__":
    _run()
