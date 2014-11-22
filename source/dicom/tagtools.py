""" Tools to wrap dataset tag operations

Usage:

    for tag in ds.keys():
        with valid_tag(tag):
            # Anything that goes wrong here is annotated
 """

from contextlib import contextmanager


@contextmanager
def tag_in_exception(tag):
    """ Perform a protected read on the tag """
    try:
        yield
    except Exception as e:
        err = 'Invalid tag {0}: {1}'
        err = err.format(tag, str(e))
        raise type(e)(err)
