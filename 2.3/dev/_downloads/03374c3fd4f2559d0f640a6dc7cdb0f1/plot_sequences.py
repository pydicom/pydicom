"""
======================
Working with sequences
======================

This examples illustrates how to work with sequences.

"""

from pydicom.sequence import Sequence
from pydicom.dataset import Dataset

# create to toy datasets
block_ds1 = Dataset()
block_ds1.BlockType = "APERTURE"
block_ds1.BlockName = "Block1"

block_ds2 = Dataset()
block_ds2.BlockType = "APERTURE"
block_ds2.BlockName = "Block2"

beam = Dataset()
# note that you should add beam data elements like BeamName, etc; these are
# skipped in this example
plan_ds = Dataset()
# starting from scratch since we did not read a file
plan_ds.BeamSequence = Sequence([beam])
plan_ds.BeamSequence[0].BlockSequence = Sequence([block_ds1, block_ds2])
plan_ds.BeamSequence[0].NumberOfBlocks = 2

beam0 = plan_ds.BeamSequence[0]
print('Number of blocks: {}'.format(beam0.BlockSequence))

# create a new data set
block_ds3 = Dataset()
# add data elements to it as above and don't forget to update Number of Blocks
# data element
beam0.BlockSequence.append(block_ds3)
del plan_ds.BeamSequence[0].BlockSequence[1]
