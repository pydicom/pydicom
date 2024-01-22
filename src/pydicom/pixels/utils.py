import importlib


def _passes_version_check(package_name: str, minimum_version: tuple[int, ...]) -> bool:
    """Return True if `package_name` is available and its version is greater or
    equal to `minimum_version`
    """
    try:
        module = importlib.import_module(package_name, "__version__")
    except ModuleNotFoundError:
        return False

    return tuple(int(x) for x in module.__version__.split(".")) >= minimum_version
