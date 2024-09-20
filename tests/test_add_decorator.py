import tempfile

from pytest_xflaky.add_decorator import add_decorator_to_function


def test_file_without_pytest():
    path = None
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as fp:
        fp.write("def test_foo():\n    pass\n")
        path = fp.name

    add_decorator_to_function(path, "test_foo")

    with open(path, "r") as fp:
        assert (
            fp.read()
            == "import pytest\n@pytest.mark.xfail(strict=False)\ndef test_foo():\n    pass\n"
        )


def test_file_with_pytest():
    path = None
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as fp:
        fp.write("import pytest\ndef test_foo():\n    pass\n")
        path = fp.name

    add_decorator_to_function(path, "test_foo")

    with open(path, "r") as fp:
        assert (
            fp.read()
            == "import pytest\n@pytest.mark.xfail(strict=False)\ndef test_foo():\n    pass\n"
        )


def test_multiple_calls():
    path = None
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as fp:
        fp.write(
            "import pytest\ndef test_foo():\n    pass\ndef test_bar():\n    pass\n"
        )
        path = fp.name

    add_decorator_to_function(path, "test_foo")
    add_decorator_to_function(path, "test_bar")

    with open(path, "r") as fp:
        assert (
            fp.read()
            == "import pytest\n@pytest.mark.xfail(strict=False)\ndef test_foo():\n    pass\n@pytest.mark.xfail(strict=False)\ndef test_bar():\n    pass\n"
        )
