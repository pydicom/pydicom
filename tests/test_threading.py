import threading
from pydicom import config

def test_settings_thread_safety():
    """Different threads can adjust config settings without conflict"""
    barrier = threading.Barrier(3)
    errors = []
    mode_name = {
        config.IGNORE: "IGNORE",
        config.WARN:  "WARN",
        config.RAISE: "RAISE",
    }

    def worker(id, val):
        config.settings.reading_validation_mode = val
        barrier.wait(timeout=2)
        # Record if this thead's setting was not preserved
        if config.settings.reading_validation_mode != val:
            errors.append(
                f"Thread {id} expected {mode_name[val]}, "
                f"got {mode_name[config.settings.reading_validation_mode]}"
            )

    t1 = threading.Thread(target=worker, args=(1, config.IGNORE))
    t2 = threading.Thread(target=worker, args=(2, config.RAISE))
    t3 = threading.Thread(target=worker, args=(2, config.WARN))
    
    t1.start()
    t2.start()
    t3.start()
    t1.join()
    t2.join()
    t3.join()

    assert not errors, f"Thread safety violations detected: {errors}"