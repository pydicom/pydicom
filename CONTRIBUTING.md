
Contributing to pydicom
=======================

This is the summary for contributing code, documentation, testing, and filing
issues. Please read it carefully to help making the code review process go as
smoothly as possible and maximize the likelihood of your contribution being
merged.

How to contribute
-----------------

The preferred workflow for contributing to pydicom is to fork the
[main repository](https://github.com/pydicom/pydicom) on
GitHub, clone, and develop on a branch. Steps:

1. Fork the [project repository](https://github.com/pydicom/pydicom)
   by clicking on the 'Fork' button near the top right of the page. This creates
   a copy of the code under your GitHub user account. For more details on
   how to fork a repository see [this guide](https://help.github.com/articles/fork-a-repo/).

2. Clone your fork of the pydicom repo from your GitHub account to your local disk:

   ```bash
   $ git clone git@github.com:YourLogin/pydicom.git
   $ cd pydicom
   ```

3. Create a ``feature`` branch to hold your development changes:

   ```bash
   $ git checkout -b my-feature
   ```

   Always use a ``feature`` branch. It's good practice to never work on the ``master`` branch!

4. Develop the feature on your feature branch. Add changed files using ``git add`` and then ``git commit`` files:

   ```bash
   $ git add modified_files
   $ git commit
   ```

   to record your changes in Git, then push the changes to your GitHub account with:

   ```bash
   $ git push -u origin my-feature
   ```

5. Follow [these instructions](https://help.github.com/articles/creating-a-pull-request-from-a-fork)
to create a pull request from your fork. This will send an email to the committers.

(If any of the above seems like magic to you, please look up the
[Git documentation](https://git-scm.com/documentation) on the web, or ask a friend or another contributor for help.)

Pull Request Checklist
----------------------

We recommend that your contribution complies with the following rules before you
submit a pull request:

-  Follow the
   [coding-guidelines](http://pydicom.org/dev/developers/contributing.html#coding-guidelines).

-  Use, when applicable, the validation tools and scripts in the
   `pydicom.utils` submodule.  A list of utility routines available
   for developers can be found in the
   [Utilities for Developers](http://pydicom.org/dev/developers/utilities.html#developers-utils)
   page.

-  If your pull request addresses an issue, please use the pull request title to
   describe the issue and mention the issue number in the pull request
   description. This will make sure a link back to the original issue is
   created. Use "closes #PR-NUM" or "fixes #PR-NUM" to indicate github to
   automatically close the related issue. Use any other keyword (i.e: works on,
   related) to avoid github to close the referenced issue.

-  All public methods should have informative docstrings with sample
   usage presented as doctests when appropriate.

-  Please prefix the title of your pull request with `[MRG]` (Ready for Merge),
   if the contribution is complete and ready for a detailed review. Two core
   developers will review your code and change the prefix of the pull request to
   `[MRG + 1]` on approval, making it eligible for merging. An incomplete
   contribution -- where you expect to do more work before receiving a full
   review -- should be prefixed `[WIP]` (to indicate a work in progress) and
   changed to `[MRG]` when it matures. WIPs may be useful to: indicate you are
   working on something to avoid duplicated work, request broad review of
   functionality or API, or seek collaborators. WIPs often benefit from the
   inclusion of a
   [task list](https://github.com/blog/1375-task-lists-in-gfm-issues-pulls-comments)
   in the PR description.

-  When adding additional functionality, provide at least one
   example script in the ``examples/`` folder. Have a look at other
   examples for reference. Examples should demonstrate why the new
   functionality is useful in practice and, if possible, compare it
   to other methods available in pydicom.

-  Documentation and high-coverage tests are necessary for enhancements to be
   accepted. Bug-fixes or new features should be provided with 
   [non-regression tests](https://en.wikipedia.org/wiki/Non-regression_testing).
   These tests verify the correct behavior of the fix or feature. In this
   manner, further modifications on the code base are granted to be consistent
   with the desired behavior.
   For the Bug-fixes case, at the time of the PR, this tests should fail for
   the code base in master and pass for the PR code.

-  The documentation should also include expected time and space
   complexity of the algorithm and scalability, e.g. "this algorithm
   can scale to a large number of samples > 100000, but does not
   scale in dimensionality: n_features is expected to be lower than
   100".

You can also check for common programming errors with the following
tools:

-  Code with good unittest **coverage** (at least 80%), check with:

  ```bash
  $ pip install pytest pytest-cov
  $ py.test --cov=pydicom path/to/test_for_package
  ```

-  No pyflakes warnings, check with:

  ```bash
  $ pip install pyflakes
  $ pyflakes path/to/module.py
  ```

-  No PEP8 warnings, check with:

  ```bash
  $ pip install pep8
  $ pep8 path/to/module.py
  ```

-  AutoPEP8 can help you fix some of the easy redundant errors:

  ```bash
  $ pip install autopep8
  $ autopep8 path/to/pep8.py
  ```

Bonus points for contributions that include a performance analysis with
a benchmark script and profiling output (please report on the mailing
list or on the GitHub issue).

Filing bugs
-----------
We use Github issues to track all bugs and feature requests; feel free to
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
   as your Python, pydicom and numpy versions. This information
   can be found by running the following code snippet:

  ```python
  import platform; print(platform.platform())
  import sys; print("Python", sys.version)
  import numpy; print("numpy", numpy.__version__)
  import pydicom; print("pydicom", pydicom.__version__)
  ```

-  please include a [reproducible](http://stackoverflow.com/help/mcve) code
   snippet or link to a [gist](https://gist.github.com). If an exception is
   raised, please provide the traceback. (use `%xmode` in ipython to use the
   non beautified version of the trackeback)


New contributor tips
--------------------

A great way to start contributing to pydicom is to pick an item
from the list of [Easy issues](https://github.com/pydicom/pydicom/issues?labels=Easy)
in the issue tracker. Resolving these issues allow you to start
contributing to the project without much prior knowledge. Your
assistance in this area will be greatly appreciated by the more
experienced developers as it helps free up their time to concentrate on
other issues.

Documentation
-------------

We are glad to accept any sort of documentation: function docstrings,
reStructuredText documents (like this one), tutorials, etc.
reStructuredText documents live in the source code repository under the
``doc/`` directory.

You can edit the documentation using any text editor and then generate
the HTML output by typing ``make html`` from the ``doc/`` directory.
Alternatively, ``make`` can be used to quickly generate the
documentation without the example gallery. The resulting HTML files will
be placed in ``_build/html/`` and are viewable in a web browser. See the
``README`` file in the ``doc/`` directory for more information.

For building the documentation, you will need
[sphinx](http://sphinx.pocoo.org/),
[numpy](http://numpy.org/),
[matplotlib](http://matplotlib.org/), and
[pillow](http://pillow.readthedocs.io/en/latest/).

When you are writing documentation, it is important to reference the related
part of the DICOM standard, and give give intuition to the reader on what the
method does. It is best to always start with a small paragraph with a
hand-waving explanation of what the method does to the data and a figure (coming
from an example) illustrating it.
