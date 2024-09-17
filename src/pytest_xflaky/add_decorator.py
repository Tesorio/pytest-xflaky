import sys

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())


def add_decorator_to_function(path, function_name):
    with open(path, "r") as fp:
        source_code = fp.read()

    # Initialize the parser and set the Python language
    parser = Parser(PY_LANGUAGE)

    # Parse the source code
    tree = parser.parse(bytes(source_code, "utf-8"))
    root_node = tree.root_node

    if "::" in function_name:
        class_name = function_name.split("::")[0]
        function_name = function_name.split("::")[1]
    else:
        class_name = None

    # Helper function to traverse nodes
    last_class_name = None
    decorators = set()
    is_pytest_imported = False

    def traverse(node):
        nonlocal last_class_name, decorators, is_pytest_imported

        if node.type in {"import_from_statement", "import_statement"}:
            if b"import pytest" in node.text:
                is_pytest_imported = True

        if node.type == "decorator":
            decorators.add(node.text)

        elif node.type == "class_definition":
            last_class_name = node.child_by_field_name("name").text.decode()
            decorators = set()

        elif node.type == "function_definition":
            if node.child_by_field_name("name").text.decode() == function_name:
                if last_class_name == class_name:
                    return node, decorators
            decorators = set()

        for child in node.children:
            if node := traverse(child):
                return node

    if found := traverse(root_node):
        function_node, decorators = found
    else:
        return None

    # skip if decorator already added
    if not any(d.startswith(b"@pytest.mark.xfail") for d in decorators):
        # Add the decorator before the function definition
        indent = " " * function_node.range.start_point.column
        function_start_byte = function_node.start_byte
        source_code = (
            source_code[:function_start_byte]
            + f"@pytest.mark.xfail(strict=False)\n{indent}"
            + source_code[function_start_byte:]
        )

    # add import pytest
    if not is_pytest_imported:
        import_statement = "import pytest\n"
        source_code = import_statement + source_code

    with open(path, "w") as fp:
        fp.write(source_code)


def parse_report_file(path):
    with open(path, "r") as fp:
        for line in fp:
            line = line.strip()
            if line.endswith(" FLAKY") and "::" in line:
                path, rest = line.split("::", 1)
                rest = rest.split(" ")[0]
                function_name, _line = rest.rsplit(":", 1)
                yield path, function_name


def add_decorators(report_file):
    for line in parse_report_file(report_file):
        path, function_name = line
        add_decorator_to_function(path, function_name)


if __name__ == "__main__":
    report_file = sys.argv[1]
    add_decorators(report_file)
