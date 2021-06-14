import typing as tp
from datetime import datetime, timedelta


class ApproxDatetime:

    def __init__(
        self,
        expected: datetime,
        abs_delta: timedelta = timedelta(seconds=10),
    ) -> None:
        self.min_ = expected - abs_delta
        self.max_ = expected + abs_delta

    def __eq__(self, actual: tp.Any) -> bool:
        if not isinstance(actual, datetime):
            return False
        return self.min_ <= actual <= self.max_
