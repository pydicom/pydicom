from io import BytesIO

from pydicom.config import logger, have_numpy

if have_numpy:
    import numpy as np

try:
    from PIL import Image, ImageCms
    from PIL.ImageCms import (
        applyTransform,
        getProfileDescription,
        getProfileName,
        ImageCmsProfile,
        ImageCmsTransform,
        isIntentSupported,
    )
    have_pillow = True
except ImportError:
    have_pillow = False


if have_numpy and have_pillow:

    class ColorManager(object):

        """Class for color management using ICC profiles."""

        def __init__(self, icc_profile: bytes):
            """

            Parameters
            ----------
            icc_profile: bytes
                ICC profile

            Raises
            ------
            ValueError
                When ICC Profile cannot be read.
            RuntimeError
                When color management is not possible due to missing
                dependencies.

            """
            try:
                self._icc_transform = self._build_icc_transform(icc_profile)
            except OSError:
                raise ValueError('Could not read ICC Profile.')

        def transform_frame(self, array: np.ndarray) -> np.ndarray:
            """Transforms a frame by applying the ICC profile.

            Parameters
            ----------
            array: numpy.ndarray
                Pixel data of a color image frame in form of an array with
                dimensions (Rows x Columns x SamplesPerPixel)

            Returns
            -------
            numpy.ndarray
                Color corrected pixel data of a image frame in form of an array
                with dimensions (Rows x Columns x SamplesPerPixel)

            Raises
            ------
            ValueError
                When `array` does not have 3 dimensions and thus does not represent
                a color image frame.

            """
            if array.ndim != 3:
                raise ValueError(
                    'Array has incorrect dimensions for a color image frame.'
                )
            image = Image.fromarray(array)
            applyTransform(image, self._icc_transform, inPlace=True)
            return np.asarray(image)

        @staticmethod
        def _build_icc_transform(icc_profile: bytes) -> ImageCmsTransform:
            """Builds an ICC Transformation object.

            Parameters
            ----------
            icc_profile: bytes
                ICC Profile

            Returns
            -------
            PIL.ImageCms.ImageCmsTransform
                ICC Transformation object

            """
            profile: bytes
            try:
                profile = ImageCmsProfile(BytesIO(icc_profile))
            except OSError:
                raise ValueError('Cannot read ICC Profile in image metadata.')
            name = getProfileName(profile).strip()
            description = getProfileDescription(profile).strip()
            logger.debug(f'found ICC Profile "{name}": "{description}"')

            logger.debug('build ICC Transform')
            intent = ImageCms.INTENT_RELATIVE_COLORIMETRIC
            if not isIntentSupported(
                profile,
                intent=intent,
                direction=ImageCms.DIRECTION_INPUT
            ):
                raise ValueError(
                    'ICC Profile does not support desired '
                    'color transformation intent.'
                )
            return ImageCms.buildTransform(
                inputProfile=profile,
                outputProfile=ImageCms.createProfile('sRGB'),
                inMode='RGB',  # according to PS3.3 C.11.15.1.1
                outMode='RGB'
            )

else:

    class ColorManager(object):

        """Class for color management using ICC profiles."""

        def __init__(self, icc_profile: bytes):
            """

            Parameters
            ----------
            icc_profile: bytes
                ICC profile

            Raises
            ------
            ValueError
                When ICC Profile cannot be read.
            RuntimeError
                When color management is not possible due to missing
                dependencies.

            """
            raise RuntimeError(
                'Color management requires "numpy" and "Pillow" packages '
                'to be installed.'
            )
