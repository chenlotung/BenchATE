from app.worker import CommandQueue
from app.models import Command


def test_new_off_cancels_older_queued_on_and_apply_for_same_channel():
    queue = CommandQueue()
    queue.put(Command("apply", "CH1"))
    queue.put(Command("output_on", "CH1"))
    queue.put(Command("output_on", "CH3"))
    assert queue.put(Command("output_off", "CH1")) == 2
    assert queue.get().kind == "output_off"
    remaining = queue.get()
    assert remaining.kind == "output_on" and remaining.channel == "CH3"
