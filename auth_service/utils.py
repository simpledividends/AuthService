import datetime

TZ_UTC = datetime.timezone.utc


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(TZ_UTC).replace(tzinfo=None)
