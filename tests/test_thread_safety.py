"""
Stress tests for thread safety in MediaManager and ThreadManager (Phase 4).
These tests are designed to fail if proper locking is not implemented.
"""
import threading
import pytest
import time
from unittest.mock import MagicMock
from tomcat.services.media_service import MediaManager
from tomcat.utils.thread_utils import ThreadManager

def _make_manager(tmpdir):
    config = MagicMock()
    config.lowmag_folder = str(tmpdir / "lowmag")
    config.tiltseries_folder = str(tmpdir / "tiltseries")
    config.tomogram_folder = str(tmpdir / "tomogram")
    config.thumbnails_folder = str(tmpdir / "thumbnails")
    config.paths = {
        "lowmag_path": "/some/path",
        "tiltseries_path": "/some/path",
        "tomogram_path": "/some/path",
    }

    thread_manager = ThreadManager(max_workers=4)
    return MediaManager(config, thread_manager)

class TestProcessingQueueLock:
    """THREAD-01, THREAD-02: MediaManager dict mutations must be thread-safe."""

    def test_concurrent_processing_queue_mutations(self, tmp_path):
        """
        Simultaneous queueing and processing (which involves deletion) 
        should not raise RuntimeError.
        """
        manager = _make_manager(tmp_path)
        # Mock _all_media_exists to always return False so items are queued
        manager._all_media_exists = MagicMock(return_value=False)
        # Mock _generate_media_for_tomogram_internal to do nothing but maybe a tiny sleep
        def slow_gen(name):
            time.sleep(0.001)
        manager._generate_media_for_tomogram_internal = MagicMock(side_effect=slow_gen)

        num_threads = 5
        num_items = 50
        barrier = threading.Barrier(num_threads)
        errors = []

        def worker(thread_id):
            barrier.wait()
            try:
                for i in range(num_items):
                    tomo_name = f"tomo_{thread_id}_{i}"
                    manager.queue_tomogram_for_processing(tomo_name)
                    # Also try to trigger process_queue manually to increase contention
                    manager.process_queue()
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # If it's not thread-safe, we expect RuntimeError: OrderedDict mutated during iteration
        assert len(errors) == 0, f"Encountered {len(errors)} errors: {errors}"

    def test_concurrent_media_status_mutations(self, tmp_path):
        """THREAD-03: MediaManager.media_status mutations must be thread-safe."""
        manager = _make_manager(tmp_path)
        num_threads = 10
        num_items = 200
        barrier = threading.Barrier(num_threads)
        errors = []

        def worker(thread_id):
            barrier.wait()
            try:
                for i in range(num_items):
                    tomo_name = f"tomo_{i}" # High contention on same keys
                    manager.media_status[f"lowmag_{tomo_name}"] = f"status_{thread_id}_{i}"
                    # Simulate a read
                    _ = manager.media_status.get(f"lowmag_{tomo_name}")
                    # Simulate a deletion (even if not used much in app, good for stress test)
                    if i % 10 == 0:
                        manager.media_status.pop(f"lowmag_{tomo_name}", None)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Encountered {len(errors)} errors: {errors}"

    def test_concurrent_thumbnail_progress_updates(self, tmp_path):
        """THREAD-03: thumbnail_progress updates must be atomic."""
        manager = _make_manager(tmp_path)
        num_threads = 10
        num_items = 500
        barrier = threading.Barrier(num_threads)

        def worker():
            barrier.wait()
            for i in range(num_items):
                # The += operation is not atomic in Python
                manager.thumbnail_progress['downloaded'] += 1

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
        
        expected = num_threads * num_items
        actual = manager.thumbnail_progress['downloaded']
        # This is expected to fail without locks because of lost updates
        assert actual == expected, f"Lost updates in thumbnail_progress: {actual} != {expected}"

class TestSubmitTaskAtomicity:
    """THREAD-04: ThreadManager.submit_task must be atomic for the same key."""

    def test_simultaneous_submit_task(self):
        tm = ThreadManager(max_workers=4)
        task_key = "shared_task_key"
        num_threads = 20
        barrier = threading.Barrier(num_threads)
        results = []

        def worker():
            barrier.wait()
            # Simultaneous calls to submit_task with same key
            res = tm.submit_task(task_key, lambda: time.sleep(0.1))
            results.append(res)

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Exactly one should have returned True (successfully submitted)
        # Without a lock, multiple threads might see 'task_key not in active_futures' 
        # at the same time and all return True.
        assert results.count(True) == 1, f"Multiple threads successfully submitted task with same key: {results.count(True)}"
