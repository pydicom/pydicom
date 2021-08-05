==========================================
Creating and managing virtual environments
==========================================

When it comes to the management of third-party packages, Python
has some complications:

* By default, every third-party package will be installed to same directory.
* Python is unable to differentiate between different versions of the same
  package installed to that directory

This means:

* If you're working on a project and you make a backwards incompatible
  change, then other projects that depend on it may be broken until you go
  through and update them all with the necessary changes.
* If you have two projects that depend on different version of the same
  package then it becomes impossible for both to function simultaneously.

In order to deal with these problems (and others) it's recommended that you
work within a Python `virtual environment
<https://virtualenv.pypa.io>`_, which is an
isolated environment with its own set of installed system and third-party
packages. Because these are maintained separately from both the system
installation of Python and other virtual environments we no longer have to
worry about the issues mentioned above.

In this tutorial you will:

* (pip only) Install a couple of packages that make using virtual environments
  easier
* Create new virtual environments and learn how to delete them
* Learn how to activate, deactivate and switch between environments
* Learn how to manage packages in a virtual environment

By the end of the tutorial you should have a fully functioning virtual
environment ready for installing *pydicom*.

If you're using pip as your package manager then continue reading. If you're
using conda then :ref:`start here<tut_venv_conda>`


.. _tut_venv_pip:

Using pip
=========

Install packages
----------------

First up, we're going to install a couple of packages that make managing
virtual environments a lot easier:
`virtualenv <https://pypi.org/project/virtualenv/>`_ and
`virtualenvwrapper <https://pypi.org/project/virtualenvwrapper/>`_::

  $ pip install virtualenv virtualenvwrapper

Create new virtual environments
-------------------------------

To create a new environment run::

  $ mkvirtualenv test-env

This should produce output similar to the following:

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

The output includes the location where the new environment will
be created, in this case at ``/home/user/env/test-env``. By default, new
environments will be created in the location specified by the ``WORKON_HOME``
environmental variable.

After creation, the new environment will be activated and ready to use, as
shown by the ``(test-env)`` before the prompt::

  (test-env) $

By default, a new virtual environment will be creating using the version of
Python you get from running the system's (not the virtual environment's)
``python`` command::

  $ python --version  # system Python
  Python 2.7.17
  $ mkvirtualenv default-env  # environment Python
  (default-env) $ python --version
  Python 2.7.17

You can use a different version of Python (as long as one's installed)
by passing the ``-p path`` option, where ``path`` is the path to a Python
executable::

  $ mkvirtualenv -p /usr/bin/python3.7 py37-env
  (py37-env) $ python --version
  Python 3.7.5

Deleting environments
---------------------

Environments can be deleted from the ``WORKON_HOME`` directory by using
``rmvirtualenv [env name]``::

  (py37-env) $ rmvirtualenv default-env

However environments must be deactivated first:

.. code-block:: text

  (py37-env) $ rmvirtualenv py37-env
  Removing py37-env...
  ERROR: You cannot remove the active environment ('py37-env').
  Either switch to another environment, or run 'deactivate'.

Activating and deactivating
---------------------------

Environments can be deactivated with the ``deactivate`` command, which will
return you to the system::

  (py37-env) $ deactivate
  $ python --version
  Python 2.7.17

And activated with the ``workon`` command::

  $ workon test-env
  (test-env) $

You can switch between environments without needing to deactivate them first::

  (test-env) $ workon py37-env
  (py37-env) $


Managing packages
-----------------

Packages within the environment can be managed normally, just remember to
activate the environment first::

  (py37-env) $ pip install antigravity
  (py37-env) $ pip uninstall antigravity

And given it's one of the reasons we're using virtual environments, it's
not surprising that different environments can have different versions of the
same package installed::

  (py37-env) $ mkvirtualenv old
  (old) $ pip install pydicom==1.2
  (old) $ python -c "import pydicom; print(pydicom.__version__)"
  1.2.0
  (old) $ mkvirtualenv current
  (current) $ pip install pydicom
  (current) $ python -c "import pydicom; print(pydicom.__version__)"
  1.4.0


Final steps
-----------

Let's clean up the environments we created. First we'll take a look to
see what environments are available, then we'll delete them all::

  (current) $ deactivate
  $ lsvirtualenv -b
  current
  old
  py37-env
  test-env
  $ rmvirtualenv current
  $ rmvirtualenv old
  $ rmvirtualenv py37-env
  $ rmvirtualenv test-env

And finally, let's create a fresh virtual environment ready for installing
*pydicom*::

  $ mkvirtualenv pydicom
  (pydicom) $

If you want more information on using the ``virtualenvwrapper`` package, take a
look at the `command reference
<https://virtualenvwrapper.readthedocs.io/en/latest/command_ref.html>`_.

If you're using Python 3.3 or higher you may also be interested in the Python
`venv <https://docs.python.org/3/library/venv.html>`_ module which also allows
the creation virtual environments, but without the need for extra packages.

.. _tut_venv_conda:

Using conda
===========

Create a new virtual environment
--------------------------------

To create a new virtual environment we use the ``conda create`` command with
the ``-n [env name]`` flag::

  $ conda create -n test-env

When asked if you want to proceed, enter ``y``.

This creates a new environment ``test-env`` in ``[path/to/conda]/envs/`` with
the default version of Python used by the system. To use Python
version ``X.Y``, you can use the ``python=X.Y`` option::

  $ conda create -n py37-env python=3.7


Activating and deactivating environments
----------------------------------------

Environments must be activated before they can be used::

  $ conda activate py37-env
  (py37-env) $ python --version
  Python 3.7.5
  (py37-env) $ conda activate test-env
  (test-env) $

Deactivating the environment will return you to the previous environment::

  (test-env) $ conda deactivate
  (py37-env) $

To return to the base conda environment it's recommended you just use ``conda
activate``::

  (py35-env) $ conda activate
  $

You can switch between environments without needing to deactivate them first::

  $ conda activate test-env
  (test-env) $ conda activate py37-env
  (py37-env) $


Deleting environments
---------------------

Environments can be deleted with the ``conda remove`` command::

  $ conda remove -n test-env --all

However environments must be deactivate first::

  (py37-env) $ conda remove -n py37-env --all
  CondaEnvironmentError: cannot remove current environment. deactivate and run conda remove again


Managing installed packages
---------------------------

Packages within the environment can be managed normally, just remember to
activate the environment first::

  (py37-env) $ pip install antigravity
  (py37-env) $ pip uninstall antigravity
  (py37-env) $ conda install numpy
  (py37-env) $ conda uninstall numpy

Different virtual environments can have different versions of the same package
installed::

  (py37-env) $ conda create -n old && conda activate old
  (old) $ pip install pydicom==1.2
  (old) $ python -c "import pydicom; print(pydicom.__version__)"
  1.2.0
  (old) $ conda create -n current && conda activate current
  (current) $ pip install pydicom==1.4
  (current) $ python -c "import pydicom; print(pydicom.__version__)"
  1.4.0


Final steps
-----------

Let's clean up the environments we created. First we'll take a look to
see what environments are available, then we'll delete them all::

  (current) $ conda activate
  $ conda env list
  # conda environments:
  #
  base               *  /home/user/conda
  current               /home/user/conda/envs/current
  old                   /home/user/conda/envs/old
  py37-env              /home/user/conda/envs/py37-env
  $ conda remove -n current --all
  $ conda remove -n old --all
  $ conda remove -n py37-env --all

And finally, let's create a fresh virtual environment ready for installing
*pydicom*::

  $ conda create -n pydicom
  $ conda activate pydicom
  (pydicom) $

If you want more information on using virtual environments in conda, take a
look at `managing conda environments
<https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html>`_.
