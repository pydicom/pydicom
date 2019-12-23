
Contribution to pydicom
=======================


Get the development version
---------------------------

  1. Sign up to `github <https://github.com>`_
  2. `Fork the project <https://github.com/pydicom/pydicom/fork>`_
  3. Using the command line, ``cd`` to the directory where you want your
    local copy of *pydicom* to live.
  4. Download the source code::

    $ git clone https://github.com/YourGithubUsername/pydicom.git

Its recommended that you install *pydicom* in a virtual environment. This
allows you to work on *pydicom* without having to worry about breaking other
applications that may depend on the package. The most convenient way to manage
virtual environments is with
`virtualenv <https://pypi.org/project/virtualenv/>`_ and
`virtualenvwrapper <https://pypi.org/project/virtualenvwrapper/>`_

  $ pip install virtualenv virtualenvwrapper

A new virtual environment can then be created with::

  $ mkvirtualenv -p /path/to/python name-of-env

Virtual environments can be activated with::

  $ workon name-of-env
  (name-of-env) $

And deactivated using::

  (name-of-env) $ deactivate

You can now install the cloned copy of *pydicom* (``-e`` for editable mode)::

  $ pip install -e /path/to/local/pydicom/


Running the unit tests
----------------------

  pip install pytest

``cd`` into the ``pydicom/tests`` directory and run::

  $ pytest


Create a new branch for your patch
----------------------------------

  $ git checkout -b name-of-patch


Writing documentation
---------------------

  # pip install sphinx numpy matplotlib sphinx_rtd_theme sphinx_gallery
