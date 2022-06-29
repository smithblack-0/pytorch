from torch.utils.data.datapipes._hook_iterator import _SnapshotState
from torch.utils.data.datapipes.datapipe import IterDataPipe
from torch.utils.data.graph_settings import apply_shuffle_seed


# TODO: Caveats
#   1. Caller (either the ReadingService or DataLoader) must pass in the initial RNG
#   2. `in_batch_shuffle` and `bucketbatch` are not compatible with this because they currently
#      lack the option to `set_seed`.
def _simple_graph_snapshot_restoration(datapipe: IterDataPipe, n_iterations: int, rng=None) -> None:
    r"""
    This function will restore a snapshot by fast-forwarding the given DataPipe by ``n_iterations``,
    and in the process, fast-forward its parent DataPipes as well at the cost of re-doing every computation.
    For instance, applying this function to the final DataPipe of a graph will restore the snapshot
    (via fast-forward) every DataPipe within the graph.

    Note:
        This is the simplest but least efficient way to fast-forward a DataPipe. Usage of other fast-forwarding
        methods (custom ones if necessary) are recommended.

    Args:
        datapipe: IterDataPipe to be fast-forwarded
        n_iterations: number of iterations to fast-forward
        rng: ``Optional[torch.Generator]``. If not ``None``, this RNG will be used for shuffling. The generator
            should be in its `initial` state as it was first passed into ``DataLoader`` or ``ReadingService``.
    """
    if datapipe._snapshot_state != _SnapshotState.NotStarted:
        raise RuntimeError(
            "Snapshot restoration cannot be applied. You can only restore simple snapshot to the graph "
            "if your graph has not started,\nand have not restored another snapshot or "
            "create any iterator. It is possible to override this by setting "
            "`datapipe._snapshot_state = _SnapshotState.NotStarted`.")

    apply_shuffle_seed(datapipe, rng)

    remainder = n_iterations
    it = iter(datapipe)
    while remainder > 0:
        try:
            next(it)
            remainder -= 1
        except StopIteration:
            raise RuntimeError(f"Fast-forward {datapipe} by {n_iterations} iterations "
                               "exceeds the number of samples available.")
    datapipe._fast_forward_iterator = it
    # While the DataPipe has `_fast_forward_iterator`, `next()` will get result from there instead of elsewhere.

    # This will prevent the DataPipe from resetting in the `iter()` call
    # If another DataPipe is consuming it, it won't have to start over again
    datapipe._snapshot_state = _SnapshotState.Restored
