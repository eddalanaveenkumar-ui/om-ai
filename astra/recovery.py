"""Recovery is only automatic when the failed action provably sent no input."""
class TargetNotReady(ValueError, RuntimeError):
    pass


class RecoveryBudget:
    def __init__(self, limit=3):
        self.remaining = limit

    def claim(self):
        if not self.remaining:
            return False
        self.remaining -= 1
        return True


def repair_queue(proposal, tail, allowed):
    steps = proposal.get('actions')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
        return None
    if any(not isinstance(s, dict) or s.get('action') not in allowed for s in steps):
        return None
    return steps + tail
