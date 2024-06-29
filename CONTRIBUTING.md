
Contributing to pydicom
=======================

This is the guide for contributing code, documentation and tests to *pydicom*, as
well as information on filing issues. Please read it carefully to help make the
code review process go as smoothly as possible and maximize the likelihood of your
contribution being merged.


How to contribute
-----------------

The preferred workflow for contributing to *pydicom* is to fork the
[main repository](https://github.com/pydicom/pydicom) on
GitHub, clone, and develop on a branch. Steps:

1. Fork the [project repository](https://github.com/pydicom/pydicom)
   by clicking on the 'Fork' button near the top right of the page. This creates
   a copy of the code under your GitHub user account. For more details on
   how to fork a repository see [this guide](https://help.github.com/articles/fork-a-repo/).

2. Clone your fork of the *pydicom* repo from your GitHub account to your local disk:

   ```bash
   $ git clone https://github.com/YourUsername/pydicom
   $ cd pydicom/
   ```

3. Install [pre-commit](https://pre-commit.com):

    ```bash
    $ pip install pre-commit
    $ pre-commit install
    ```

4. Create a ``feature`` branch to hold your development changes:

   ```bash
   $ git checkout -b my-feature
   ```

   Always use a ``feature`` branch. It's good practice to never work on the ``main`` branch!

5. Develop the feature on your feature branch. Add changed files using ``git add`` and then ``git commit`` files:

   ```bash
   $ git add modified_files
   $ git commit
   ```

6. Add a meaningful commit message. Pull requests are "squash-merged", e.g.
   squashed into one commit with all commit messages combined. The commit
   messages can be edited during the merge, but it helps if they are clearly
   and briefly showing what has been done in the commit. Check out the
   [seven commonly accepted rules](https://www.theserverside.com/video/Follow-these-git-commit-message-guidelines)
   for commit messages. Here are some examples, taken from actual commits:

   ```
   Add support for new VRs OV, SV, UV

   -  closes #1016
   ```
   ```
   Add warning when saving compressed without encapsulation  
   ```
   ```
   Add optional handler argument to Dataset.decompress()

   - also add it to Dataset.convert_pixel_data()
   - add separate error handling for given handle
   - see #537
   ```

   When you run ``git commit`` the pre-commit checks will automatically run, if
   it finds any errors then they should be fixed before calling ``git commit``
   again.

7. To record your changes in Git, push the changes to your GitHub
   account with:

   ```bash
   $ git push -u origin my-feature
   ```

8. Follow [these instructions](https://help.github.com/articles/creating-a-pull-request-from-a-fork) to create a pull request from your fork. This will send an email to the committers.

(If any of the above seems like magic to you, please look up the
[Git documentation](https://git-scm.com/documentation) on the web, or ask a friend or another contributor for help.)

Pull Request Checklist
----------------------

We recommend that your contribution complies with the following rules before you
submit a pull request:

-  Follow the style used in the rest of the code. That mostly means to
   follow [PEP-8 guidelines](https://www.python.org/dev/peps/pep-0008/) for
   the code, and the [NumPy style](https://numpydoc.readthedocs.io/en/latest/format.html)
   for documentation.

-  If your pull request addresses an issue, please use the pull request title to
   describe the issue and mention the issue number in the pull request
   description. This will make sure a link back to the original issue is
   created. Use "closes #issue-number" or "fixes #issue-number" to let GitHub
   automatically close the related issue on commit. Use any other keyword
   (i.e. works on, related) to avoid GitHub to close the referenced issue.

-  All public methods should have informative docstrings with sample
   usage presented as doctests when appropriate.

-  Please prefix the title of your pull request with `[MRG]` (Ready for Merge),
   if the contribution is complete and ready for a detailed review. Some of the
   core developers will review your code, make suggestions for changes, and
   approve it as soon as it is ready for merge. Pull requests are usually merged
   after two approvals by core developers, or other developers asked to review the code.
   An incomplete contribution -- where you expect to do more work before receiving a full
   review -- should be prefixed with `[WIP]` (to indicate a work in progress) and
   changed to `[MRG]` when it matures. WIPs may be useful to: indicate you are
   working on something to avoid duplicated work, request broad review of
   functionality or API, or seek collaborators. WIPs often benefit from the
   inclusion of a
   [task list](https://github.com/blog/1375-task-lists-in-gfm-issues-pulls-comments)
   in the PR description.

-  When adding additional functionality, check if it makes sense to add one or
   more example scripts in the ``examples/`` folder. Have a look at other
   examples for reference. Examples should demonstrate why the new
   functionality is useful in practice and, if possible, compare it
   to other methods available in pydicom.

-  Documentation and high-coverage tests are necessary for enhancements to be
   accepted. Bug-fixes shall be provided with
   [regression tests](https://en.wikipedia.org/wiki/regression_testing) that
   fail before the fix. For new features, the correct behavior shall be
   verified by feature tests. A good practice to write sufficient tests is
   [test-driven development](https://en.wikipedia.org/wiki/Test-driven_development).

You can also check for common programming errors and style issues with the
following tools:

-  The test coverage should be at least as good as the current coverage and any
new lines of code must be covered:

  ```bash
  $ pip install pytest pytest-cov
  $ cd pydicom/
  $ pytest --cov=pydicom tests/
  ```

- The type hints, code syntax, spelling and formatting should be checked:

  ```bash
  $ pre-commit run
  ```

Alternatively you can run these checks manually without pre-commit:

-  Check the type hints

  ```bash
  $ pip install mypy
  $ cd pydicom/
  $ mypy
  ```

-  Check the code style and syntax

  ```bash
  $ pip install ruff
  $ cd pydicom/
  $ ruff check .
  ```

- Consistent code formatting

  ```bash
  $ pip install black
  $ cd pydicom/
  $ black src/pydicom/
  $ black tests/
  ```

Filing issues
-------------
We use GitHub issues to track all bugs and feature requests; feel free to
open an issue if you have found a bug or wish to see a feature implemented.

It is recommended to check that your issue complies with the
following rules before submitting:

-  Verify that your issue is not being currently addressed by other
   [issues](https://github.com/pydicom/pydicom/issues?q=)
   or [pull requests](https://github.com/pydicom/pydicom/pulls?q=).

-  Please ensure all code snippets and error messages are formatted in
   appropriate code blocks.
   See [Creating and highlighting code blocks](https://help.github.com/articles/creating-and-highlighting-code-blocks).

-  Please include your operating system type and version number, as well
   as your Python and pydicom versions.

   Please use the `pydicom_env_info` module to gather this information :

   ```bash
   $ python -m pydicom.env_info
   ```

-  Please include a
   [reproducible](https://stackoverflow.com/help/minimal-reproducible-example)
   code snippet or link to a [gist](https://gist.github.com). If an
   exception is raised, please provide the complete traceback. (use `%xmode`
   in ipython to use the non beautified version of the trackeback)


Documentation
-------------

We are glad to accept any sort of documentation: function docstrings,
reStructuredText documents, tutorials, etc.
reStructuredText documents live in the source code repository under the
``doc/`` directory.

You can edit the documentation using any text editor and then generate
the HTML output by typing ``make html`` from the ``doc/`` directory.
Alternatively, ``make`` can be used to quickly generate the
documentation without the example gallery. The resulting HTML files will
be placed in ``_build/html/`` and are viewable in a web browser. See the
``README`` file in the ``doc/`` directory for more information.

Install the dependencies needed for building the documentation::

    ```bash
    $ cd pydicom/
    $ pip install -e .[docs]
    ```

To build the documentation itself::

    ```bash
    $ cd pydicom/doc/
    $ make clean && make html
    ```

When you are writing documentation that references DICOM, it is often
helpful to reference the related part of the
[DICOM standard](https://www.dicomstandard.org/current/). Try to make the
explanations intuitive and understandable also for users not fluent in DICOM.
