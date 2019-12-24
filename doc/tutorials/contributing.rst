
Contributing a patch to pydicom
===============================

Download the current source code
--------------------------------

1. Install Git if required
2. Sign up to `GitHub <https://github.com>`_
3. `Fork the project <https://github.com/pydicom/pydicom/fork>`_
4. Using the command line, ``cd`` to the directory where you want your
local copy of *pydicom* to live

Clone the source code (you may wish to use ``--depth=1`` to save on
bandwidth)::

     $ git clone https://github.com/YourUsername/pydicom.git

Its recommended that you install *pydicom* in a
:doc:`virtual environment<virtualenvs>` as this allows you to test different
combinations of Python and installed packages. Where ``X.Y`` is the Python
version to use::

  $ mkvirtualenv -p /path/to/pythonX.Y pydX.Y

You can now install the cloned copy of *pydicom* (``-e`` for editable mode)::

  (pydX.Y) $ pip install -e /path/to/local/pydicom/


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
