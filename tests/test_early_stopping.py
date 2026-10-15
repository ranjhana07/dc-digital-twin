from twin.ml.early_stopping import EarlyStopping


def test_stops_after_patience_without_improvement():
    stopper = EarlyStopping(patience=3, min_delta=0.01)
    improved = [stopper.update(loss, epoch) for epoch, loss in enumerate([1.0, 0.8, 0.79, 0.795, 0.80])]
    assert improved == [True, True, False, False, False]
    assert stopper.best == 0.8
    assert stopper.best_epoch == 1
    assert stopper.should_stop


def test_improvement_resets_counter():
    stopper = EarlyStopping(patience=2, min_delta=0.0)
    for epoch, loss in enumerate([1.0, 1.1, 0.9]):
        stopper.update(loss, epoch)
    assert not stopper.should_stop
    assert stopper.best_epoch == 2
