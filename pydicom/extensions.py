from pydicom.dataset import Dataset
from pydicom.tag import Tag
import warnings


def handle_dataset_tags(tags):
    """Define a decorator to use with classes which handle tags"""
    def decorator(handler_class):
        existing_tags = set(Dataset._handler_classes.keys()) & set(tags)
        if existing_tags:
            warnings.warn(
                "Registration of handler {!r} is overriding"
                "existing handling of tags {}".format(handler_class,
                                                      existing_tags)
                )
        Dataset._handler_classes.update({Tag(tag): handler_class
                                        for tag in tags})
        return handler_class

    return decorator
