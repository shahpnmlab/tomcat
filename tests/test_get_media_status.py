"""
Tests for MediaManager.get_media_status() (plan 01-01).

Behaviour under test:
  - File already on disk with size > 0  → returns "ready" immediately,
    sets media_status[key] = "ready", does NOT call queue_tomogram_for_processing
  - Status already "generating"         → returns "generating" without disk I/O or queuing
  - Status already "error"              → returns "error" without queuing
  - Status "unknown", no file on disk   → queues, sets "generating", returns "generating"
  - Invalid media_type                  → returns {"status": "error", ...}
"""
import os
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(tmpdir):
    """Return a MediaManager wired up with a mock Config and ThreadManager."""
    from tomcat.services.media_service import MediaManager

    config = MagicMock()
    # Folder paths that the method under test will resolve files into
    config.lowmag_folder = str(tmpdir / "lowmag")
    config.tiltseries_folder = str(tmpdir / "tiltseries")
    config.tomogram_folder = str(tmpdir / "tomogram")
    config.thumbnails_folder = str(tmpdir / "thumbnails")
    config.paths = {
        "lowmag_path": "/some/path",
        "tiltseries_path": "/some/path",
        "tomogram_path": "/some/path",
    }

    thread_manager = MagicMock()
    thread_manager.max_workers = 4
    thread_manager.get_active_task_count.return_value = 0
    return MediaManager(config, thread_manager)


def _create_file(path, size=100):
    """Create a file at *path* with *size* bytes of content."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * size)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetMediaStatusDiskFirstGate:
    """D-06 / D-03: disk-first gate must return 'ready' and cache it."""

    @pytest.mark.parametrize("media_type,subfolder,ext", [
        ("lowmag", "lowmag", ".jpg"),
        ("tiltseries", "tiltseries", ".gif"),
        ("tomogram", "tomogram", ".gif"),
    ])
    def test_returns_ready_when_file_exists(self, tmp_path, media_type, subfolder, ext):
        """When file exists on disk with content, status must be 'ready'."""
        manager = _make_manager(tmp_path)
        tomo_name = "tomo_001"
        folder = getattr(manager.config, f"{subfolder}_folder")
        media_file = os.path.join(folder, f"{tomo_name}{ext}")
        _create_file(media_file)

        result = manager.get_media_status(media_type, tomo_name)

        assert result["status"] == "ready", (
            f"Expected 'ready' for {media_type}, got '{result['status']}'"
        )

    def test_dict_set_to_ready_on_disk_hit(self, tmp_path):
        """D-06: media_status dict must be populated when disk file confirmed."""
        manager = _make_manager(tmp_path)
        tomo_name = "tomo_001"
        media_file = os.path.join(manager.config.lowmag_folder, f"{tomo_name}.jpg")
        _create_file(media_file)

        manager.get_media_status("lowmag", tomo_name)

        assert manager.media_status.get(f"lowmag_{tomo_name}") == "ready", (
            "media_status dict must be set to 'ready' when disk file is confirmed"
        )

    def test_no_queue_call_when_file_exists(self, tmp_path):
        """D-05: queue_tomogram_for_processing must NOT be called when file on disk."""
        manager = _make_manager(tmp_path)
        tomo_name = "tomo_001"
        media_file = os.path.join(manager.config.lowmag_folder, f"{tomo_name}.jpg")
        _create_file(media_file)

        with patch.object(manager, "queue_tomogram_for_processing") as mock_queue:
            manager.get_media_status("lowmag", tomo_name)
            mock_queue.assert_not_called()

    def test_zero_byte_file_does_not_return_ready(self, tmp_path):
        """A zero-byte file on disk must NOT be reported as 'ready'."""
        manager = _make_manager(tmp_path)
        tomo_name = "tomo_001"
        media_file = os.path.join(manager.config.lowmag_folder, f"{tomo_name}.jpg")
        _create_file(media_file, size=0)

        result = manager.get_media_status("lowmag", tomo_name)

        assert result["status"] != "ready"


class TestGetMediaStatusDictFastPath:
    """D-05: already-tracked statuses must short-circuit without re-queuing."""

    def test_generating_status_returned_without_queuing(self, tmp_path):
        manager = _make_manager(tmp_path)
        tomo_name = "tomo_002"
        manager.media_status["lowmag_tomo_002"] = "generating"

        with patch.object(manager, "queue_tomogram_for_processing") as mock_queue:
            result = manager.get_media_status("lowmag", tomo_name)

        assert result["status"] == "generating"
        mock_queue.assert_not_called()

    def test_error_status_returned_without_queuing(self, tmp_path):
        manager = _make_manager(tmp_path)
        tomo_name = "tomo_003"
        manager.media_status["tiltseries_tomo_003"] = "error"

        with patch.object(manager, "queue_tomogram_for_processing") as mock_queue:
            result = manager.get_media_status("tiltseries", tomo_name)

        assert result["status"] == "error"
        mock_queue.assert_not_called()


class TestGetMediaStatusUnknownQueuing:
    """D-05: unknown status with no file on disk must queue and return 'generating'."""

    def test_unknown_queues_and_returns_generating(self, tmp_path):
        manager = _make_manager(tmp_path)
        tomo_name = "tomo_004"

        with patch.object(manager, "queue_tomogram_for_processing") as mock_queue:
            result = manager.get_media_status("tomogram", tomo_name)

        assert result["status"] == "generating"
        mock_queue.assert_called_once_with(tomo_name, priority=True)

    def test_unknown_sets_generating_in_dict(self, tmp_path):
        manager = _make_manager(tmp_path)
        tomo_name = "tomo_005"

        with patch.object(manager, "queue_tomogram_for_processing"):
            manager.get_media_status("lowmag", tomo_name)

        assert manager.media_status.get("lowmag_tomo_005") == "generating"


class TestGetMediaStatusInvalidType:
    """Invalid media type must return error dict."""

    def test_invalid_type_returns_error(self, tmp_path):
        manager = _make_manager(tmp_path)
        result = manager.get_media_status("thumbnail", "tomo_001")
        assert result["status"] == "error"
        assert "message" in result
