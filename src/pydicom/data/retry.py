from functools import wraps
import logging
import time
from typing import Any
from collections.abc import Callable


def retry(
    exc: type[Exception] | tuple[type[Exception], ...],
    exc_msg: str | None = None,
    tries: int = 4,
    delay: int = 3,
    backoff: int = 2,
    logger: logging.Logger | None = None,
) -> Callable[[Callable], Any]:
    """Retry calling the decorated function using an exponential backoff.

    https://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: https://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    Parameters
    ----------
    exc : Exception or Tuple[Exception, ...]
        The exception to check. may be a tuple of exceptions to check.
    exc_msg : str, optional
        The message to be shown if an exception occurs.
    tries : int, optional
        The number of times to try (not retry) before giving up, default ``4``.
    delay : int, optional
        The initial delay between retries in seconds, default ``3``.
    backoff : int, optional
        The backoff multiplier e.g. value of 2 will double the delay each
        retry, default ``2``.
    logger : logging.Logger, optional
        The logger to use. If ``None`` (default), print to stdout.
    """

    def deco_retry(f: Callable) -> Any:
        @wraps(f)
        def f_retry(*args: Any, **kwargs: Any) -> Any:
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except exc as e:
                    msg = f"{e}: retrying in {mdelay} seconds..."
                    if exc_msg:
                        msg += f"  {exc_msg}"

                    if logger:
                        logger.warning(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff

            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry
