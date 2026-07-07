import fcntl
import logging
import os
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

LOCK_FILENAME = ".kometa-ai.lock"


@contextmanager
def acquire_run_lock(state_dir: str) -> Iterator[bool]:
    """Acquire an exclusive, non-blocking run lock for the processing pipeline.

    Yields ``True`` if the lock was acquired (the caller should proceed) or
    ``False`` if another kometa-ai run already holds it (the caller should skip
    processing this cycle).

    The lock is an ``flock`` on a file in the state directory. Because flock is
    tied to the open file descriptor, the kernel releases it automatically if
    the holding process dies — so a crashed run never leaves a stale lock behind.

    This is the guard against the concurrent-run tag-clobber bug: two overlapping
    runs (e.g. the scheduler firing while a manual ``--run-now`` exec is active)
    each reconcile Radarr against their own start-of-run snapshot and undo each
    other's tag changes. Serializing the fetch→process→reconcile window prevents
    that entirely.

    Args:
        state_dir: Directory in which to place the lock file.
    """
    lock_path = os.path.join(state_dir, LOCK_FILENAME)
    fd = open(lock_path, "w")
    acquired = False
    try:
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            logger.warning(
                f"Another kometa-ai run holds the lock ({lock_path}); skipping "
                "this run to avoid clobbering Radarr tags. It will run on the "
                "next scheduled cycle."
            )
            yield False
            return

        try:
            fd.write(str(os.getpid()))
            fd.flush()
        except OSError:
            # Recording the PID is best-effort diagnostics; the lock itself is
            # what matters.
            pass

        yield True
    finally:
        if acquired:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        fd.close()
