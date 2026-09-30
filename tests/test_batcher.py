from twin.ingest.batcher import Batcher


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_flushes_when_full():
    written = []
    batcher = Batcher(written.append, max_size=3, max_age_s=10.0, clock=FakeClock())
    for index in range(7):
        batcher.add(index)
    assert written == [[0, 1, 2], [3, 4, 5]]
    assert batcher.pending() == 1


def test_flushes_when_aged():
    clock = FakeClock()
    written = []
    batcher = Batcher(written.append, max_size=100, max_age_s=1.0, clock=clock)
    batcher.add("a")
    clock.now = 0.5
    assert batcher.flush_if_due() == 0
    clock.now = 1.2
    assert batcher.flush_if_due() == 1
    assert written == [["a"]]
    assert batcher.pending() == 0


def test_age_restarts_with_new_batch():
    clock = FakeClock()
    written = []
    batcher = Batcher(written.append, max_size=100, max_age_s=1.0, clock=clock)
    batcher.add(1)
    clock.now = 2.0
    batcher.flush_if_due()
    batcher.add(2)
    clock.now = 2.5
    assert batcher.flush_if_due() == 0
    clock.now = 3.1
    assert batcher.flush_if_due() == 1


def test_manual_flush_and_counters():
    written = []
    batcher = Batcher(written.append, max_size=10)
    batcher.add(1)
    batcher.add(2)
    assert batcher.flush() == 2
    assert batcher.flush() == 0
    assert batcher.flushed_batches == 1
    assert batcher.flushed_items == 2
