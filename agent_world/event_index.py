"""Rebuildable indexes over the authoritative append-only event history."""
from collections import Counter, defaultdict


class EventIndex:
    def __init__(self):
        self.offset = 0
        self.last = None
        self.by_type = defaultdict(list)
        self.by_actor = defaultdict(list)
        self.counts = Counter()
        self.counts_by_actor = defaultdict(Counter)
        self.ledger = []
        self.feedback = defaultdict(list)

    def __deepcopy__(self, memo):
        # Derived caches never make transactional snapshots grow with history.
        return EventIndex()

    def __getstate__(self):
        return {}

    def __setstate__(self, state):
        self.__init__()

    def update(self, events):
        if self.offset > len(events) or (self.offset and events[self.offset - 1] is not self.last):
            self.__init__()
        for event in events[self.offset:]:
            self.by_type[event.type].append(event)
            self.by_actor[event.actor_id].append(event)
            self.counts[event.type] += 1
            self.counts_by_actor[event.actor_id][event.type] += 1
            if event.type in {"invalid_action", "contention_failure"}:
                self.feedback[event.actor_id].append(event)
            if event.type in {"ledger_note", "ledger_seed_note"}:
                self.ledger.append(event)
        self.offset = len(events)
        self.last = events[-1] if events else None
        return self


def event_index(state):
    index = getattr(state, "_event_index", None)
    if index is None:
        index = state._event_index = EventIndex()
    return index.update(state.events)
