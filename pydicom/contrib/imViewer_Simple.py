# ==========================================================================
# imViewer-Simple.py
#
#    An example program that opens uncompressed DICOM images and
# converts them via numPy and PIL to be viewed in wxWidgets GUI
# apps.  The conversion is currently:
#
#    pydicom->NumPy->PIL->wxPython.Image->wxPython.Bitmap
#
# Gruesome but it mostly works.  Surely there is at least one
# of these steps that could be eliminated (probably PIL) but
# haven't tried that yet and I may want some of the PIL manipulation
# functions.
#
#    This won't handle RLE, embedded JPEG-Lossy, JPEG-lossless,
# JPEG2000, old ACR/NEMA files, or anything wierd.  Also doesn't
# handle some RGB images that I tried.
#
#    Have added Adit Panchal's LUT code.  It helps a lot, but needs
# to be further generalized.  Added test for window and/or level
# as 'list' type - crude, but it worked for a bunch of old MR and
# CT slices I have.
#
# Testing:      minimal
#               Tried only on WinXP sp2 using numpy 1.3.0
#               and PIL 1.1.7b1, Python 2.6.4, and wxPython 2.8.10.1
#
# Dave Witten:  Nov. 11, 2009
# ==========================================================================
import pydicom
import wx
from pydicom import compat
have_PIL = True
try:
    import PIL.Image
except ImportError:
    have_PIL = False
have_numpy = True
try:
    import numpy as np
except ImportError:
    have_numpy = False

# ----------------------------------------------------------------
#  Initialize image capabilities.
# ----------------------------------------------------------------
wx.InitAllImageHandlers()


def MsgDlg(window, string, caption='OFAImage', style=wx.YES_NO | wx.CANCEL):
    """Common MessageDialog."""
    dlg = wx.MessageDialog(window, string, caption, style)
    result = dlg.ShowModal()
    dlg.Destroy()
    return result


class ImFrame(wx.Frame):
    """Class for main window."""

    def __init__(self, parent, title):
        """Create the pydicom image example's main frame window."""

        wx.Frame.__init__(self, parent, id=-1, title="", pos=wx.DefaultPosition,
                          size=wx.Size(w=1024, h=768),
                          style=wx.DEFAULT_FRAME_STYLE | wx.SUNKEN_BORDER | wx.CLIP_CHILDREN)

        # --------------------------------------------------------
        # Set up the menubar.
        # --------------------------------------------------------
        self.mainmenu = wx.MenuBar()

        # Make the 'File' menu.
        menu = wx.Menu()
        item = menu.Append(wx.ID_ANY, '&Open', 'Open file for editing')
        self.Bind(wx.EVT_MENU, self.OnFileOpen, item)
        item = menu.Append(wx.ID_ANY, 'E&xit', 'Exit Program')
        self.Bind(wx.EVT_MENU, self.OnFileExit, item)
        self.mainmenu.Append(menu, '&File')

        # Attach the menu bar to the window.
        self.SetMenuBar(self.mainmenu)

        # --------------------------------------------------------
        # Set up the main splitter window.
        # --------------------------------------------------------
        self.mainSplitter = wx.SplitterWindow(self, style=wx.NO_3D | wx.SP_3D)
        self.mainSplitter.SetMinimumPaneSize(1)

        # -------------------------------------------------------------
        # Create the folderTreeView on the left.
        # -------------------------------------------------------------
        self.dsTreeView = wx.TreeCtrl(self.mainSplitter, style=wx.TR_LINES_AT_ROOT | wx.TR_HAS_BUTTONS)

        # --------------------------------------------------------
        # Create the ImageView on the right pane.
        # --------------------------------------------------------
        self.imView = wx.Panel(self.mainSplitter, style=wx.VSCROLL | wx.HSCROLL | wx.CLIP_CHILDREN)
        self.imView.Bind(wx.EVT_PAINT, self.OnPaint)
        self.imView.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.imView.Bind(wx.EVT_SIZE, self.OnSize)

        # --------------------------------------------------------
        # Install the splitter panes.
        # --------------------------------------------------------
        self.mainSplitter.SplitVertically(self.dsTreeView, self.imView)
        self.mainSplitter.SetSashPosition(300, True)

        # --------------------------------------------------------
        # Initialize some values
        # --------------------------------------------------------
        self.dcmdsRoot = False
        self.foldersRoot = False
        self.loadCentered = True
        self.bitmap = None
        self.Show(True)

    def OnFileExit(self, event):
        """Exits the program."""
        self.Destroy()
        event.Skip()

    def OnSize(self, event):
        "Window 'size' event."
        self.Refresh()

    def OnEraseBackground(self, event):
        "Window 'erase background' event."
        pass

    def populateTree(self, ds):
        """ Populate the tree in the left window with the [desired]
        dataset values"""
        if not self.dcmdsRoot:
            self.dcmdsRoot = self.dsTreeView.AddRoot(text="DICOM Objects")
        else:
            self.dsTreeView.DeleteChildren(self.dcmdsRoot)
        self.recurse_tree(ds, self.dcmdsRoot)
        self.dsTreeView.ExpandAll()

    def recurse_tree(self, ds, parent, hide=False):
        """ order the dicom tags """
        for data_element in ds:
            if isinstance(data_element.value, compat.text_type):
                ip = self.dsTreeView.AppendItem(parent, text=compat.text_type(data_element))
            else:
                ip = self.dsTreeView.AppendItem(parent, text=str(data_element))

            if data_element.VR == "SQ":
                for i, ds in enumerate(data_element.value):
                    sq_item_description = data_element.name.replace(" Sequence", "")
                    item_text = "%s %d" % (sq_item_description, i + 1)
                    parentNodeID = self.dsTreeView.AppendItem(ip, text=item_text.rjust(128))
                    self.recurse_tree(ds, parentNodeID)

# --- Most of what is important happens below this line ---------------------

    def OnFileOpen(self, event):
        """Opens a selected file."""
        dlg = wx.FileDialog(self, 'Choose a file to add.', '', '', '*.*', wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            fullPath = dlg.GetPath()
            imageFile = dlg.GetFilename()
            # checkDICMHeader()
            self.show_file(imageFile, fullPath)

    def OnPaint(self, event):
        "Window 'paint' event."
        dc = wx.PaintDC(self.imView)
        dc = wx.BufferedDC(dc)

        # paint a background just so it isn't *so* boring.
        dc.SetBackground(wx.Brush("WHITE"))
        dc.Clear()
        dc.SetBrush(wx.Brush("GREY", wx.CROSSDIAG_HATCH))
        windowsize = self.imView.GetSizeTuple()
        dc.DrawRectangle(0, 0, windowsize[0], windowsize[1])
        bmpX0 = 0
        bmpY0 = 0
        if self.bitmap is not None:
            if self.loadCentered:
                bmpX0 = (windowsize[0] - self.bitmap.Width) / 2
                bmpY0 = (windowsize[1] - self.bitmap.Height) / 2
            dc.DrawBitmap(self.bitmap, bmpX0, bmpY0, False)

    # ------------------------------------------------------------
    #  ImFrame.ConvertWXToPIL()
    #  Expropriated from Andrea Gavana's
    #  ShapedButton.py in the wxPython dist
    # ------------------------------------------------------------
    def ConvertWXToPIL(self, bmp):
        """ Convert wx.Image Into PIL Image. """
        width = bmp.GetWidth()
        height = bmp.GetHeight()
        im = wx.EmptyImage(width, height)
        im.fromarray("RGBA", (width, height), bmp.GetData())
        return im

    # ------------------------------------------------------------
    #  ImFrame.ConvertPILToWX()
    #  Expropriated from Andrea Gavana's
    #  ShapedButton.py in the wxPython dist
    # ------------------------------------------------------------
    def ConvertPILToWX(self, pil, alpha=True):
        """ Convert PIL Image Into wx.Image. """
        if alpha:
            image = wx.EmptyImage(*pil.size)
            image.SetData(pil.convert("RGB").tostring())
            image.SetAlphaData(pil.convert("RGBA").tostring()[3::4])
        else:
            image = wx.EmptyImage(pil.size[0], pil.size[1])
            new_image = pil.convert('RGB')
            data = new_image.tostring()
            image.SetData(data)
        return image

    def get_LUT_value(self, data, window, level):
        """Apply the RGB Look-Up Table for the given data and window/level value."""
        if not have_numpy:
            raise ImportError("Numpy is not available. See http://numpy.scipy.org/ to download and install")
        if isinstance(window, list):
            window = window[0]
        if isinstance(level, list):
            level = level[0]
        return np.piecewise(data,
                            [data <= (level - 0.5 - (window - 1) / 2),
                             data > (level - 0.5 + (window - 1) / 2)],
                            [0, 255, lambda data: ((data - (level - 0.5)) / (window - 1) + 0.5) * (255 - 0)]
                            )

    # -----------------------------------------------------------
    # ImFrame.loadPIL_LUT(dataset)
    # Display an image using the Python Imaging Library (PIL)
    # -----------------------------------------------------------
    def loadPIL_LUT(self, dataset):
        if not have_PIL:
            raise ImportError("Python Imaging Library is not available. See http://www.pythonware.com/products/pil/ to download and install")
        if('PixelData' not in dataset):
            raise TypeError("Cannot show image -- DICOM dataset does not have pixel data")
        if('WindowWidth' not in dataset) or ('WindowCenter' not in dataset):  # can only apply LUT if these values exist
            bits = dataset.BitsAllocated
            samples = dataset.SamplesPerPixel
            if bits == 8 and samples == 1:
                mode = "L"
            elif bits == 8 and samples == 3:
                mode = "RGB"
            elif bits == 16:  # not sure about this -- PIL source says is 'experimental' and no documentation.
                mode = "I;16"  # Also, should bytes swap depending on endian of file and system??
            else:
                raise TypeError("Don't know PIL mode for %d BitsAllocated and %d SamplesPerPixel" % (bits, samples))
            size = (dataset.Columns, dataset.Rows)
            im = PIL.Image.frombuffer(mode, size, dataset.PixelData, "raw", mode, 0, 1)  # Recommended to specify all details by http://www.pythonware.com/library/pil/handbook/image.htm
        else:
            image = self.get_LUT_value(dataset.pixel_array, dataset.WindowWidth, dataset.WindowCenter)
            im = PIL.Image.fromarray(image).convert('L')  # Convert mode to L since LUT has only 256 values: http://www.pythonware.com/library/pil/handbook/image.htm
        return im

    def show_file(self, imageFile, fullPath):
        """ Load the DICOM file, make sure it contains at least one
        image, and set it up for display by OnPaint().  ** be
        careful not to pass a unicode string to read_file or it will
        give you 'fp object does not have a defer_size attribute,
        or some such."""
        ds = pydicom.read_file(str(fullPath))
        ds.decode()                                         # change strings to unicode
        self.populateTree(ds)
        if 'PixelData' in ds:
            self.dImage = self.loadPIL_LUT(ds)
            if self.dImage is not None:
                tmpImage = self.ConvertPILToWX(self.dImage, False)
                self.bitmap = wx.BitmapFromImage(tmpImage)
                self.Refresh()

# ------ This is just the initialization of the App  -------------------------


# =======================================================
# The main App Class.
# =======================================================
class App(wx.App):
    """Image Application."""

    def OnInit(self):
        """Create the Image Application."""
        ImFrame(None, 'wxImage Example')
        return True

# ---------------------------------------------------------------------
# If this file is running as main or a standalone test, begin execution here.
# ---------------------------------------------------------------------
if __name__ == '__main__':
    app = App(0)
    app.MainLoop()
