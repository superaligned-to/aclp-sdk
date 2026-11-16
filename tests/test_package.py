import importlib.resources

import aclp
import aclp.events


def test_every_public_name_imports() -> None:
    for module in (aclp, aclp.events):
        missing = [n for n in module.__all__ if not hasattr(module, n)]

        assert missing == [], module.__name__

    assert len(aclp.__all__) == len(set(aclp.__all__))


def test_package_ships_its_type_marker_and_schema() -> None:
    root = importlib.resources.files("aclp")

    assert root.joinpath("py.typed").is_file()
    assert root.joinpath("schema.json").is_file()
