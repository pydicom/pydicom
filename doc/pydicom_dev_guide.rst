.. _pydicom_dev_guide:

=======================
Pydicom Developer Guide
=======================

Release guideline
-----------------

Bumpversion
-----------

When you want to release, you can use ``bumpversion`` to update the version
across the library::

  bumpversion release  # Move from 1.0.0.dev0 to 1.0.0

Then, you can commit this change and refer to the section :ref:`git_github` to
create a branch and a release.

Once the release is created, you need to turn to a new development version::

  bumpversion minor # Move from 1.0.0 to 1.1.0.dev0

Once this is done, you can commit and push to master.

.. _git_github:

Git and GitHub
~~~~~~~~~~~~~~

At the moment of a release, a git branch needs to be created with the semantic
``major.minor.X`` (e.g. ``1.0.X). It will be used in the future to backport bug
fixes.

For each patch, a release with an associated tag should be created through the
GitHub front-end. The target branch will not be ``master`` but the maintenance
branch ``major.minor.X``.

Documentation
~~~~~~~~~~~~~

At the moment of a release, there is a need to manually edit the directory of
the `gh-pages`::

  git checkout gh-pages
  cp -r dev major.minor  # major.minor represent a version of the release (1.0)
  unlink stable
  ln -s major.minor stable
  git add major.minor
  git commit -am 'DOC new release major.minor'

By doing so, any bug fix pushed in a maintenance branch will trigger a
documentation build. The ``stable`` version of the doc will also point to the
new release while ``dev`` doc will still point to ``dev`` folder which is the
documentation of the ``master`` branch.

PyPi build
----------

The package can be built for different platforms::
  
  python setup.py bdist_wininst
  python setup.py sdist
  python setup.py bdist_wheel --universal

Then, the different builds can be uploaded to PyPi.  This has to be done by the package owner on PyPi.
Best practice is to use twine, and to upload to the *Test* PyPi server for initial testing::

  twine upload --repository-url https://test.pypi.org/legacy/ dist/*
  
Then anyone can test the install, e.g. in a local virtual environment::

  pip install [--pre] --index-url https://test.pypi.org/simple/ pydicom

If it is a pre-release version, the optional ``--pre`` argument should be used.

When all has been tested satisfactorily, prepare an announcement for the pydicom google group,
then repeat the above twine upload/install test without the test repository urls, and then send the announcement.

There are more details at the `Python packaging guide <https://packaging.python.org/guides/using-testpypi/>`_.


