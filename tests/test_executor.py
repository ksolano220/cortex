import pytest

from cortex.engine.executor import apply_files, extract_files, is_safe_path


class TestExtractFiles:
    def test_single_file(self):
        output = (
            "Here is the code:\n\n"
            "<<<FILE src/hello.py>>>\n"
            "def hello():\n    print('hi')\n"
            "<<<END>>>\n"
        )
        files = extract_files(output)
        assert files == [("src/hello.py", "def hello():\n    print('hi')")]

    def test_multiple_files(self):
        output = (
            "<<<FILE a.py>>>\nprint('a')\n<<<END>>>\n"
            "some narration\n"
            "<<<FILE b.py>>>\nprint('b')\n<<<END>>>\n"
        )
        files = extract_files(output)
        assert files == [("a.py", "print('a')"), ("b.py", "print('b')")]

    def test_no_blocks_returns_empty(self):
        assert extract_files("just a bunch of text, no sentinels") == []

    def test_path_with_subdirs(self):
        output = "<<<FILE src/pkg/module.py>>>\npass\n<<<END>>>"
        assert extract_files(output) == [("src/pkg/module.py", "pass")]

    def test_ignores_malformed_blocks(self):
        # Missing END marker
        output = "<<<FILE a.py>>>\nprint('a')\nno end marker"
        assert extract_files(output) == []


class TestIsSafePath:
    def test_normal_path_is_safe(self, tmp_path):
        safe, _ = is_safe_path("src/foo.py", tmp_path)
        assert safe

    def test_path_traversal_blocked(self, tmp_path):
        safe, reason = is_safe_path("../../etc/passwd", tmp_path)
        assert not safe
        assert "escapes" in reason

    def test_absolute_path_blocked(self, tmp_path):
        safe, reason = is_safe_path("/etc/passwd", tmp_path)
        assert not safe
        assert "absolute" in reason

    def test_git_dir_blocked(self, tmp_path):
        safe, reason = is_safe_path(".git/config", tmp_path)
        assert not safe
        assert "denylist" in reason

    def test_env_file_blocked(self, tmp_path):
        safe, reason = is_safe_path(".env.production", tmp_path)
        assert not safe
        assert "denylist" in reason

    def test_key_extension_blocked(self, tmp_path):
        safe, reason = is_safe_path("secrets/server.key", tmp_path)
        assert not safe
        assert "denylist" in reason

    def test_empty_path_blocked(self, tmp_path):
        safe, reason = is_safe_path("", tmp_path)
        assert not safe
        assert "empty" in reason


class TestApplyFiles:
    def test_writes_file(self, tmp_path):
        output = "<<<FILE hello.py>>>\nprint('hi')\n<<<END>>>"
        results = apply_files(output, workspace=str(tmp_path))
        assert len(results) == 1
        assert results[0]["written"] is True
        assert (tmp_path / "hello.py").read_text() == "print('hi')"

    def test_creates_parent_dirs(self, tmp_path):
        output = "<<<FILE deep/nested/path/file.txt>>>\ncontent\n<<<END>>>"
        apply_files(output, workspace=str(tmp_path))
        assert (tmp_path / "deep/nested/path/file.txt").read_text() == "content"

    def test_blocks_unsafe_path(self, tmp_path):
        output = "<<<FILE ../../evil.txt>>>\nbad\n<<<END>>>"
        results = apply_files(output, workspace=str(tmp_path))
        assert results[0]["written"] is False
        assert "escapes" in results[0]["reason"]
        assert not (tmp_path.parent.parent / "evil.txt").exists()

    def test_emits_events(self, tmp_path):
        events = []
        output = (
            "<<<FILE good.py>>>\npass\n<<<END>>>\n"
            "<<<FILE .env>>>\nsecret=1\n<<<END>>>"
        )
        apply_files(output, workspace=str(tmp_path), on_event=events.append)
        event_types = [e["type"] for e in events]
        assert "file_write" in event_types
        assert "file_write_blocked" in event_types

    def test_no_blocks_returns_empty(self, tmp_path):
        results = apply_files("no file blocks here", workspace=str(tmp_path))
        assert results == []

    def test_multiple_files_some_blocked(self, tmp_path):
        output = (
            "<<<FILE ok.py>>>\npass\n<<<END>>>\n"
            "<<<FILE /etc/evil>>>\nbad\n<<<END>>>\n"
            "<<<FILE also_ok.txt>>>\nhi\n<<<END>>>"
        )
        results = apply_files(output, workspace=str(tmp_path))
        written = [r for r in results if r["written"]]
        blocked = [r for r in results if not r["written"]]
        assert len(written) == 2
        assert len(blocked) == 1
