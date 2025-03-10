"""
Thread Utility Functions for TomCat Application

This module provides utilities for managing background threads and tasks,
including a thread pool implementation for efficient concurrent processing.
"""
import logging
import atexit
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class ThreadManager:
    """
    Manages a thread pool for background task execution.
    Provides methods to submit tasks and clean up completed ones.
    """

    def __init__(self, max_workers=4):
        """
        Initialize the thread manager with a thread pool.

        Args:
            max_workers (int): Maximum number of worker threads to use
        """
        self.max_workers = max_workers
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.active_futures = {}

        # Register shutdown function
        atexit.register(self._shutdown)

        logger.info(f"Thread manager initialized with {max_workers} workers")

    def submit_task(self, task_key, func, *args, **kwargs):
        """
        Submit a task to the thread pool for execution.

        Args:
            task_key (str): Unique key to identify the task
            func (callable): Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            bool: True if task was submitted, False if already running
        """
        # Check if task is already running
        if task_key in self.active_futures and not self.active_futures[task_key].done():
            logger.debug(f"Task {task_key} is already running")
            return False

        # Submit the task to the thread pool
        future = self.thread_pool.submit(func, *args, **kwargs)
        self.active_futures[task_key] = future

        logger.debug(f"Submitted task: {task_key}")
        return True

    def cleanup_completed_tasks(self):
        """
        Clean up completed tasks to free memory.

        Returns:
            int: Number of tasks cleaned up
        """
        # Create a copy of keys to avoid modification during iteration
        keys = list(self.active_futures.keys())
        cleaned_count = 0

        for key in keys:
            future = self.active_futures[key]
            if future.done():
                # Handle any exceptions to prevent them from being silently dropped
                try:
                    # Get the result to ensure any exceptions are raised and logged
                    result = future.result()
                    logger.debug(f"Task {key} completed successfully")
                except Exception as e:
                    logger.error(f"Error in background task {key}: {str(e)}")

                # Remove the future from tracking
                del self.active_futures[key]
                cleaned_count += 1

        if cleaned_count > 0:
            logger.debug(f"Cleaned up {cleaned_count} completed tasks")

        return cleaned_count

    def get_active_task_count(self):
        """
        Get the count of currently active (not completed) tasks.

        Returns:
            int: Number of active tasks
        """
        self.cleanup_completed_tasks()
        return len(self.active_futures)

    def _shutdown(self):
        """
        Shutdown the thread pool when the application exits.
        This method is registered with atexit.
        """
        # Don't accept new tasks, but wait for submitted tasks to complete
        self.thread_pool.shutdown(wait=True)
        logger.info("Thread pool has been shut down")

    def __del__(self):
        """
        Ensure thread pool is properly shut down when this object is deleted.
        """
        try:
            # Don't wait for tasks to complete if being garbage collected
            self.thread_pool.shutdown(wait=False)
            logger.debug("Thread pool shut down during garbage collection")
        except:
            # Ignore errors during garbage collection
            pass