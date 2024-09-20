=============
pytest-xflaky
=============

.. image:: https://img.shields.io/pypi/v/pytest-xflaky.svg
    :target: https://pypi.org/project/pytest-xflaky
    :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/pytest-xflaky.svg
    :target: https://pypi.org/project/pytest-xflaky
    :alt: Python versions

.. image:: https://github.com/Tesorio/pytest-xflaky/actions/workflows/main.yml/badge.svg
    :target: https://github.com/Tesorio/pytest-xflaky/actions/workflows/main.yml
    :alt: See Build Status on GitHub Actions

What are flaky tests?
---------------------

Flaky tests, also called intermittent tests, are automated software tests that exhibit inconsistent behavior, sometimes passing and sometimes failing without any changes to the underlying code or test environment. These tests can impact negatively in many ways:

- **Frustrate engineers,** since they can waste time investigating and fixing seemingly random failures. This can lead to decreased productivity and increased stress levels.
- **Undermine confidence in the testing process,** as frequent false failures can lead developers to ignore or distrust test results. This can result in real issues being overlooked and potentially making their way into production.
- **Slow down development and deployment processes,** as teams may need to rerun tests multiple times or spend time investigating false failures before merging code or releasing new versions. Furthermore, flaky tests are often a signal of tests being dependent on each other, which may be a blocker for running a test suite in parallel.

How to keep your codebase free of them?
---------------------------------------

To maintain a codebase free of flaky tests, strive to produce code that is as deterministic as possible. For tests that inevitably have side effects—such as those involving dates, times, or external services—consider implementing boundaries that allow them to behave deterministically when the test suite is running.

As an example, at **Tesorio**, we use libraries such as `freezegun <https://github.com/spulec/freezegun>`_ and `vcrpy <https://github.com/kevin1024/vcrpy>`_ to make tests with side effects to be deterministic.

Nevertheless, some situations may slip through the cracks, as it's not always obvious when code is truly free of side effects. You might occasionally notice a test failing intermittently, dismissing it as a one-off occurrence. However, if left unchecked, these sporadic failures can multiply, leading to a higher frequency of flaky tests over time. Flaky tests require ongoing vigilance to prevent them from escalating into a more significant issue. We realized it, and we want to fight them back now, but also keep them under vigilance.

What is xflaky?
---------------

`pytest-xflaky <https://github.com/Tesorio/pytest-xflaky>`_ is a flaky-test hunter pytest plugin that collect reports and automatically submit PRs to put flaky tests under quarantine.

Features
--------

* Adds ``@pytest.xfail(strict=False)`` to flaky tests
* Maps flaky tests to GitHub users, based on the git blame and GitHub API
* Generates simple text report for flaky tests
* Generates a GitHub Report that can be used to automatically create Pull Requests


    💡 The ``@pytest.xfail(strict=False)`` decorator is a powerful tool for managing flaky tests.
    It allows a test to fail without causing the entire test suite to fail.


    When applied to a test, it marks the test as “expected to fail.”
    If the test passes unexpectedly, it will be reported as “XPASS” (unexpectedly passing).


    This approach helps maintain visibility of flaky tests while preventing them from blocking CI/CD pipelines.

Installation
------------

You can install "pytest-xflaky" via `pip`_ from `PyPI`_::

    $ pip install pytest-xflaky

Usage
-----

Xflaky runs in separate steps:

1. First, it needs to collect data from tests using the ``--xflaky-collect`` option
2. Then, you can create the reports using the ``--xflaky-report`` and ``--xflaky-github-report`` options (optional)
3. Finally, it can add the ``@pytest.xfail`` decorator, using the ``--xflaky-fix`` option

Note that the ``--json-report`` `plugin <https://pypi.org/project/pytest-json-report/>`_ is installed along with xflaky and is required.

We also recommend you to use another plugin: `pytest-randomly <https://github.com/pytest-dev/pytest-randomly>`_.

.. code:: shell

    # Run test suite without any randomness, and then, in random order
    pytest --xflaky-collect --json-report -p no:randomly
    pytest --xflaky-collect --json-report
    pytest --xflaky-collect --json-report --randomly-seed=last
    pytest --xflaky-collect --json-report --randomly-seed=last
    pytest --xflaky-collect --json-report --randomly-seed=last

    # Generate reports
    # If a test fails at least 2 times, and succeeds at least 2 times, it's considered flaky
    pytest --xflaky-report --xflaky-github-report --xflaky-min-failures 2 --xflaky-min-successes 2

The report should look like the following:

.. code:: text

    FAILED TESTS:
    tests/cache/test_something.py::MyTestCase::test_get_error:26 (failed: 2/6) FLAKY
    -
    Flaky tests result (tests: 65, runs: 390, successes: 388, failures: 2, flaky: 1)

Options
-------

+------------------------------+------------------------------------+--------------------------------------------------+
| Option                       | Default                            | Help                                             |
+==============================+====================================+==================================================+
| ``--xflaky-collect``         | ``False``                          | Collect flaky tests                              |
+------------------------------+------------------------------------+--------------------------------------------------+
| ``--xflaky-text-report-file``| ``.xflaky_report.txt``             | File to store text report                        |
+------------------------------+------------------------------------+--------------------------------------------------+
| ``--xflaky-github-report``   | ``False``                          | Generate GitHub report                           |
+------------------------------+------------------------------------+--------------------------------------------------+
| ``--xflaky-github-token``    | ``""``                             | GitHub token to use for API requests             |
|                              |                                    | (defaults to GITHUB_TOKEN)                       |
+------------------------------+------------------------------------+--------------------------------------------------+
| ``--xflaky-github-report-    | ``.xflaky_report_github.json``     | File to store GitHub report                      |
| file``                       |                                    |                                                  |
+------------------------------+------------------------------------+--------------------------------------------------+
| ``--xflaky-reports-          | ``.reports``                       | Directory to store json reports                  |
| directory``                  |                                    |                                                  |
+------------------------------+------------------------------------+--------------------------------------------------+
| ``--xflaky-report``          | ``False``                          | Generate xflaky report                           |
+------------------------------+------------------------------------+--------------------------------------------------+
| ``--xflaky-fix``             | ``False``                          | Fix flaky tests                                  |
+------------------------------+------------------------------------+--------------------------------------------------+
| ``--xflaky-min-failures``    | ``1``                              | Minimum number of failures to consider a test    |
|                              |                                    | flaky                                            |
+------------------------------+------------------------------------+--------------------------------------------------+
| ``--xflaky-min-successes``   | ``1``                              | Minimum number of successes to consider a test   |
|                              |                                    | flaky                                            |
+------------------------------+------------------------------------+--------------------------------------------------+

Contributing
------------
Contributions are very welcome. Tests can be run with `tox`_, please ensure
the coverage at least stays the same before you submit a pull request.

License
-------

Distributed under the terms of the `MIT`_ license, "pytest-xflaky" is free and open source software


Issues
------

If you encounter any problems, please `file an issue`_ along with a detailed description.

.. _`Cookiecutter`: https://github.com/audreyr/cookiecutter
.. _`@hackebrot`: https://github.com/hackebrot
.. _`MIT`: https://opensource.org/licenses/MIT
.. _`BSD-3`: https://opensource.org/licenses/BSD-3-Clause
.. _`GNU GPL v3.0`: https://www.gnu.org/licenses/gpl-3.0.txt
.. _`Apache Software License 2.0`: https://www.apache.org/licenses/LICENSE-2.0
.. _`cookiecutter-pytest-plugin`: https://github.com/pytest-dev/cookiecutter-pytest-plugin
.. _`file an issue`: https://github.com/Tesorio/pytest-xflaky/issues
.. _`pytest`: https://github.com/pytest-dev/pytest
.. _`tox`: https://tox.readthedocs.io/en/latest/
.. _`pip`: https://pypi.org/project/pip/
.. _`PyPI`: https://pypi.org/project
