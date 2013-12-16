# reindent_private.py
"""One-time script to read the pydicom _private_dict and reformat without as much spacing
(originally printed out by pprint)
"""

if __name__ == "__main__":
    from dicom._private_dict import private_dictionaries
    
    outfilename = "new_private_dict.py"
    
    outfile = open(outfilename, "wb")
    
    keys = private_dictionaries.keys()
    lines = ['private_dictionaries = {']
    
    for private_key in sorted(keys):
        lines.append("    '{key}': {{".format(key=private_key))
        current_dict = private_dictionaries[private_key]
        for key in sorted(current_dict.keys()):
            lines.append("        '{key}': {val:s},".format(key=key, val=current_dict[key]))
        lines.append("    },")
    lines.append("}")
    outfile.write("\n".join(lines))
    outfile.close()
    