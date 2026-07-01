"""Image preprocessing for OCR."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ProcessedPageImage:
    """Preprocessed page image metadata."""

    path: Path
    orientation_degrees: int = 0
    split_from_double_page: bool = False


class ImagePreprocessor:
    """Prepare scanned page images for downstream OCR engines."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process(
        self,
        image_path: Path,
        page_number: int,
        split_double_pages: bool = True,
    ) -> list[ProcessedPageImage]:
        """Run preprocessing and return one or more page images."""

        image: Image.Image = Image.open(image_path)
        image = ImageOps.exif_transpose(image)
        image = self._remove_borders(image)
        image = self._enhance(image)
        image = self._deskew_if_opencv_available(image)
        images = self._split_double_page(image) if split_double_pages else [image]

        processed: list[ProcessedPageImage] = []
        for index, page_image in enumerate(images):
            suffix = f"{page_number:05d}" if len(images) == 1 else f"{page_number:05d}_{index + 1}"
            output = self.output_dir / f"page_{suffix}.png"
            page_image.save(output)
            processed.append(
                ProcessedPageImage(path=output, split_from_double_page=len(images) > 1)
            )
        return processed

    def _enhance(self, image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        contrast = ImageEnhance.Contrast(grayscale).enhance(1.35)
        sharpened = contrast.filter(ImageFilter.UnsharpMask(radius=1.2, percent=140, threshold=3))
        return sharpened.filter(ImageFilter.MedianFilter(size=3))

    def _remove_borders(self, image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        inverted = ImageOps.invert(grayscale)
        bbox = inverted.point(lambda value: 255 if value > 18 else 0).getbbox()
        if bbox is None:
            return image
        left, upper, right, lower = bbox
        width, height = image.size
        margin = 10
        crop = (
            max(0, left - margin),
            max(0, upper - margin),
            min(width, right + margin),
            min(height, lower + margin),
        )
        cropped = image.crop(crop)
        if cropped.size[0] < width * 0.5 or cropped.size[1] < height * 0.5:
            return image
        return cropped

    def _deskew_if_opencv_available(self, image: Image.Image) -> Image.Image:
        try:
            import cv2
            import numpy as np
        except Exception:
            LOGGER.debug("OpenCV not available; skipping deskew")
            return image

        array = np.array(image)
        coords = np.column_stack(np.where(array < 245))
        if coords.size == 0:
            return image
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) < 0.25 or abs(angle) > 8:
            return image
        height, width = array.shape[:2]
        center = (width // 2, height // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            array,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return Image.fromarray(rotated)

    def _split_double_page(self, image: Image.Image) -> list[Image.Image]:
        width, height = image.size
        if width / max(height, 1) < 1.45:
            return [image]
        midpoint = width // 2
        left = image.crop((0, 0, midpoint, height))
        right = image.crop((midpoint, 0, width, height))
        return [left, right]
