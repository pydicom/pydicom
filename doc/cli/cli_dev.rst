

Extending the CLI
=================

You can create your own 'subcommands' for the ``pydicom`` command,
by adding entry points to your package's setup.py file, specifying a callback
function to register the subcommand and its arguments.

If you wanted to create two subcommands, 'command1' and 'command2',
you setup.py file should include something like:

.. code-block:: python

    if __name__ == '__main__':
        setup(
            name="yourpackage",
            # various setup options...,
            entry_points = {
                "pydicom_subcommands": [
                    "command1 = yourpackage.command1module.add_subparser",
                    "command2 = yourpackage.command2module.add_subparser"
                ]
            }
        )


The ``"pydicom_subcommands"`` is a literal string; this must not be 
changed or *pydicom* will not find your subcommand.

The ``add_subparser`` function name could be changed if you wish, but usually
would be used by convention, and is assumed in the following examples.

In the module you have specified, create the ``add_subparser`` function,
which takes a single argument ``subparsers``, and a ``do_command`` function,
which will take the call when you subcommand is actually used at the command
line::

    from pydicom.cli.main import filespec_help, filespec_parser

    def add_subparser(subparsers):
        # Register the sub-parser
        subparser = subparsers.add_parser(
            "subcommandname",
            description="Summary of your subcommand"
        )

        subparser.add_argument(
            "filespec",
            help=filespec_help,
            type=filespec_parser
        )
        subparser.add_argument(
        ...
        )

        subparser.set_defaults(func=do_command)


And define your command function::

    def do_command(args):
        ds, element = args.filespec

        if args.yourarg:
            # Do something...

        # work with the dataset ds or element as needed...

The ``pydicom`` command uses Python's 
:ref:`argparse<https://docs.python.org/3/library/argparse.html`_ library to 
process commands.

The above code snippets show adding the ``filespec`` argument, and processing
the resulting dataset in the ``do_command()`` function.  This is 
recommended if you wish to use the filespec as was seen in the :ref:`cli_show`
and :ref:`cli_codify` sections.  If not, you can just create a normal
arg with the type set to ``argparse.FileType`` to open files yourself.
