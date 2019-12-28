
Creating and managing virtual environments
==========================================

Using pip
---------

.. note::

   For more information on using ``virtualenvwrapper`` see the
   `command reference
   <https://virtualenvwrapper.readthedocs.io/en/latest/command_ref.html>`_.

Install packages
................

Install the `virtualenv <https://pypi.org/project/virtualenv/>`_ and
`virtualenvwrapper <https://pypi.org/project/virtualenvwrapper/>`_ packages::

  $ pip install virtualenv virtualenvwrapper

Create a new virtual environment
................................

To create a new environment run::

  $ mkvirtualenv test-env

This will produce output similar to:

.. code-block:: text

  Using base prefix '/usr/local'
  New python executable in /home/user/env/test-env/bin/python3.5
  Also creating executable in /home/user/env/test-env/bin/python
  Installing setuptools, pip, wheel...done.
  virtualenvwrapper.user_scripts creating /home/user/env/test-env/bin/predeactivate
  virtualenvwrapper.user_scripts creating /home/user/env/test-env/bin/postdeactivate
  virtualenvwrapper.user_scripts creating /home/user/env/test-env/bin/preactivate
  virtualenvwrapper.user_scripts creating /home/user/env/test-env/bin/postactivate
  virtualenvwrapper.user_scripts creating /home/user/env/test-env/bin/get_env_details

The output includes the location where the new virtualenv will
be created, in this case at ``/home/user/env/test-env``. By default, new
environments will be created in the location specified by the ``WORKON_HOME``
environmental variable.

After creation the new environment will be activated, as shown by the
``(test-env)`` before the prompt::

  (test-env) $

The version of Python used in the virtual environment can be controlled using
the ``-p path`` option, where ``path`` is the path to a Python executable::

  $ mkvirtualenv -p /usr/bin/python3.7 py37-env
  (py37-env) $ python --version
  Python 3.7.5

Activating and deactivating environments
........................................

You can exit the environment by using ``deactivate``::

  (test-env) $ deactivate
  $

And activate it with the ``workon`` command::

  $ workon test-env
  (test-env) $

You can switch between environments without needing to deactivate them first::

  (test-env) $ workon py37-env
  (py37-env) $


Deleting environments
.....................

To delete an environment in ``WORKON_HOME`` (must be deactivated first)::

  $ rmvirtualenv pyd37-env


Managing installed packages
...........................

Packages can be installed and uninstalled using pip::

  (test-env) $ pip install pydicom
  (test-env) $ pip uninstall pydicom

Different virtual environments can have different versions of the same package
installed::

  $ mkvirtualenv pydicom-current
  (pydicom-current) $ pip install pydicom
  (pydicom-current) $ python -c "import pydicom; print(pydicom.__version__)"
  1.4.0
  (pydicom-current) $ mkvirtualenv pydicom-old
  (pydicom-old) $ pip install pydicom==1.2
  (pydicom-old) $ python -c "import pydicom; print(pydicom.__version__)"
  1.2.0

Using conda
-----------

.. note::

   For more information on using virtual environments in conda see
   `managing conda environments
   <https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html>`_.


Create a new virtual environment
................................

::

  $ conda create -n test-env

When asked if you want to proceed, enter ``y``.

This creates a new environment in ``[path/to/conda]/envs/`` with the same
version of Python that you are currently using. To use Python
version ``X.Y``, you can use the ``python=X.Y`` option::

  $ conda create -n py37-env python=3.7


Activating and deactivating environments
........................................

Environments can be activated with::

  $ conda activate test-env
  (test-env) $

And deactivated with::

  (test-env) $ conda deactivate
  $

You can switch between environments without needing to deactivate them first::

  (test-env) $ conda activate py37-env
  (py37-env) $

Deleting environments
.....................

Environments can be deleting with::

  $ conda remove -n py37-env --all

If deleting a currently active environment you will have to deactivate it
first.

Managing installed packages
...........................

Packages can be installed and uninstalled using pip or conda::

  (test-env) $ pip install pydicom
  (test-env) $ pip uninstall pydicom
  (test-env) $ conda install numpy
  (test-env) $ conda uninstall numpy

Different virtual environments can have different versions of the same package
installed::

  $ conda create -n pydicom-current && conda activate pydicom-current
  (pydicom-current) $ pip install pydicom
  (pydicom-current) $ python -c "import pydicom; print(pydicom.__version__)"
  1.4.0
  (pydicom-current) $ conda create -n pydicom-old && conda activate pydicom-old
  (pydicom-old) $ pip install pydicom==1.2
  (pydicom-old) $ python -c "import pydicom; print(pydicom.__version__)"
  1.2.0
