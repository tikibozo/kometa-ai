from kometa_ai.utils.run_lock import acquire_run_lock


def test_lock_acquired_when_free(tmp_path):
    """A lock in an uncontended state directory is acquired."""
    with acquire_run_lock(str(tmp_path)) as got_lock:
        assert got_lock is True


def test_second_acquire_is_refused_while_held(tmp_path):
    """A second acquire returns False while the first is still held."""
    with acquire_run_lock(str(tmp_path)) as first:
        assert first is True
        with acquire_run_lock(str(tmp_path)) as second:
            assert second is False


def test_lock_released_after_context_exits(tmp_path):
    """The lock is reusable once the first holder's context has exited."""
    with acquire_run_lock(str(tmp_path)) as first:
        assert first is True

    # First holder released; a fresh acquire succeeds.
    with acquire_run_lock(str(tmp_path)) as again:
        assert again is True


def test_lock_released_even_on_exception(tmp_path):
    """An exception inside the context still releases the lock."""
    try:
        with acquire_run_lock(str(tmp_path)) as got_lock:
            assert got_lock is True
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    with acquire_run_lock(str(tmp_path)) as again:
        assert again is True
