pydicom
=======

pydicom is a pure python package for working with [DICOM](http://medical.nema.org/) files. 
It was made for inspecting and modifying DICOM data in an easy "pythonic" way.
The modifications can be written again to a new file.  

As a pure python package, pydicom can run anywhere python runs without any other requirements, 
although [NumPy](http://www.numpy.org) is needed if manipulating pixel data.

pydicom is not a DICOM server, and is not primarily about viewing images. It is designed to let you 
manipulate data elements in DICOM files with python code.

Limitations -- the main limitation of the current version is that _compressed_ pixel data (e.g. JPEG) 
cannot be _written_ in an intelligent way as it can for uncompressed pixels. Compressed pixel data 
may be read in a format supported by Pillow or jpeg_ls (in particular, lossless JPEG2000 and lossless
JPEG-LS). If you want to write compressed pixel data, you need to compress the pixel data before
writing it to the PixelArray property
