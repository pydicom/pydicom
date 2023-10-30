"""
==========================================
Format the output of the data set printing
==========================================

This example illustrates how to print the data set in your own format.

"""

# authors : Guillaume Lemaitre <g.lemaitre58@gmail.com>
# license : MIT

from pydicom import examples

print(__doc__)


def myprint(ds, indent=0):
    """Go through all items in the dataset and print them with custom format

    Modelled after Dataset._pretty_str()
    """
    dont_print = ["Pixel Data", "File Meta Information Version"]

    indent_string = "   " * indent
    next_indent_string = "   " * (indent + 1)

    for elem in ds:
        if elem.VR == "SQ":  # a sequence
            print(indent_string, elem.name)
            for sequence_item in elem.value:
                myprint(sequence_item, indent + 1)
                print(next_indent_string + "---------")
        else:
            if elem.name in dont_print:
                print("""<item not printed -- in the "don't print" list>""")
            else:
                repr_value = repr(elem.value)
                if len(repr_value) > 50:
                    repr_value = repr_value[:50] + "..."
                print(f"{indent_string} {elem.name} = {repr_value}")


ds = examples.mr
myprint(ds)
