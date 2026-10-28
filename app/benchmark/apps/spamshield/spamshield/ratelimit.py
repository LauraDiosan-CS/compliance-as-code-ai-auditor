"""Per-client token bucket protecting the classifier from floods (e.g. a misconfigured relay)."""

import time
from collections import defaultdict


class TokenBucket:
    def __init__(self, per_minute: int) -> None:
        self.rate = per_minute / 60.0
        self.capacity = per_minute
        self.tokens = defaultdict(lambda: float(per_minute))
        self.stamp = defaultdict(time.monotonic)

    def take(self, key: str) -> bool:
        now = time.monotonic()
        self.tokens[key] = min(self.capacity, self.tokens[key] + (now - self.stamp[key]) * self.rate)
        self.stamp[key] = now
        if self.tokens[key] >= 1:
            self.tokens[key] -= 1
            return True
        return False
