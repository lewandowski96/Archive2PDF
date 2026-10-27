"""
Lossless Comic Book to PDF Converter Engine
Supports CBZ, CBR, CBT, CB7, ZIP, RAR, and image folders.
Uses direct stream injection (img2pdf) for true 100% mathematical losslessness.
"""

import os
import re
import io
import shutil
import tempfile
import zipfile
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable
from PIL import Image
import img2pdf

# Supported image extensions
VALID_IMAGE_EXTS = {
    '.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif',
    '.bmp', '.jp2', '.j2k', '.jpx', '.gif'
}

# Non-image files or hidden files to ignore
IGNORED_PREFIXES = ('__MACOSX', '._', '.DS_Store', 'Thumbs.db')

def natural_sort_key(s: str) -> list:
    """Natural alphanumeric sort key so page_2 comes before page_10."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

def find_tool(name: str) -> Optional[str]:
    """Find absolute path of an executable tool."""
    return shutil.which(name)

UNAR_PATH = find_tool('unar') or '/opt/homebrew/bin/unar' if os.path.exists('/opt/homebrew/bin/unar') else None

class ComicMetadata:
    """Parses and holds comic book metadata, usually from ComicInfo.xml."""
    def __init__(self):
        self.title: str = ""
        self.series: str = ""
        self.number: str = ""
        self.volume: str = ""
        self.summary: str = ""
        self.year: str = ""
        self.month: str = ""
        self.writer: str = ""
        self.penciller: str = ""
        self.inspace: str = ""
        self.publisher: str = ""
        self.genre: str = ""
        self.page_count: int = 0

    @classmethod
    def from_xml_bytes(cls, xml_bytes: bytes) -> 'ComicMetadata':
        meta = cls()
        try:
            root = ET.fromstring(xml_bytes)
            meta.title = (root.findtext('Title') or '').strip()
            meta.series = (root.findtext('Series') or '').strip()
            meta.number = (root.findtext('Number') or '').strip()
            meta.volume = (root.findtext('Volume') or '').strip()
            meta.summary = (root.findtext('Summary') or '').strip()
            meta.year = (root.findtext('Year') or '').strip()
            meta.month = (root.findtext('Month') or '').strip()
            meta.writer = (root.findtext('Writer') or '').strip()
            meta.penciller = (root.findtext('Penciller') or '').strip()
            meta.publisher = (root.findtext('Publisher') or '').strip()
            meta.genre = (root.findtext('Genre') or '').strip()
            page_count_txt = root.findtext('PageCount')
            if page_count_txt and page_count_txt.isdigit():
                meta.page_count = int(page_count_txt)
        except Exception:
            pass
        return meta

    def get_pdf_title(self, fallback_name: str) -> str:
        parts = []
        if self.series:
            parts.append(self.series)
        if self.volume:
            parts.append(f"Vol. {self.volume}")
        if self.number:
            parts.append(f"#{self.number}")
        if self.title and self.title not in parts:
            parts.append(f"- {self.title}")
        if self.year:
            parts.append(f"({self.year})")
        return " ".join(parts) if parts else fallback_name

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "series": self.series,
            "number": self.number,
            "volume": self.volume,
            "summary": self.summary,
            "year": self.year,
            "writer": self.writer,
            "penciller": self.penciller,
            "publisher": self.publisher,
            "genre": self.genre,
            "page_count": self.page_count
        }


class ComicExtractor:
    """Extracts pages and metadata from CBZ, CBR, or image folders."""
    
    @staticmethod
    def is_valid_image_file(filename: str) -> bool:
        base = os.path.basename(filename)
        if any(base.startswith(p) for p in IGNORED_PREFIXES):
            return False
        if any(part.startswith('.') for part in filename.split(os.sep)):
            return False
        ext = os.path.splitext(filename)[1].lower()
        return ext in VALID_IMAGE_EXTS

    @classmethod
    def extract_archive(cls, archive_path: str, temp_dir: str, progress_callback: Optional[Callable[[str, float], None]] = None) -> Tuple[List[str], ComicMetadata]:
        archive_path = os.path.abspath(archive_path)
        ext = os.path.splitext(archive_path)[1].lower()
        
        extracted_pages: List[str] = []
        metadata = ComicMetadata()
        
        if progress_callback:
            progress_callback("Extracting archive...", 0.1)

        # 1. If it's a directory, just scan images inside
        if os.path.isdir(archive_path):
            return cls._scan_directory(archive_path)

        # 2. Check if it's a ZIP/CBZ
        is_zip = False
        try:
            if zipfile.is_zipfile(archive_path):
                is_zip = True
        except Exception:
            pass

        if is_zip:
            extracted_pages, metadata = cls._extract_zip(archive_path, temp_dir, progress_callback)
        else:
            # 3. For CBR/RAR or other formats, use unar or rarfile
            extracted_pages, metadata = cls._extract_with_unar_or_rar(archive_path, temp_dir, progress_callback)

        return extracted_pages, metadata

    @classmethod
    def _scan_directory(cls, dir_path: str) -> Tuple[List[str], ComicMetadata]:
        pages = []
        meta = ComicMetadata()
        for root, _, files in os.walk(dir_path):
            for file in files:
                full_path = os.path.join(root, file)
                if cls.is_valid_image_file(file):
                    pages.append(full_path)
                elif file.lower() == 'comicinfo.xml':
                    try:
                        with open(full_path, 'rb') as xf:
                            meta = ComicMetadata.from_xml_bytes(xf.read())
                    except Exception:
                        pass
        pages.sort(key=lambda p: natural_sort_key(os.path.basename(p)))
        return pages, meta

    @classmethod
    def _extract_zip(cls, zip_path: str, temp_dir: str, progress_callback: Optional[Callable[[str, float], None]] = None) -> Tuple[List[str], ComicMetadata]:
        pages = []
        meta = ComicMetadata()
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()
            total_items = len(namelist)
            
            # Check for ComicInfo.xml
            for name in namelist:
                if os.path.basename(name).lower() == 'comicinfo.xml':
                    try:
                        meta = ComicMetadata.from_xml_bytes(zf.read(name))
                    except Exception:
                        pass
                    break

            # Filter valid image entries
            image_names = [n for n in namelist if cls.is_valid_image_file(n)]
            image_names.sort(key=natural_sort_key)

            for idx, name in enumerate(image_names):
                extracted_path = zf.extract(name, temp_dir)
                pages.append(extracted_path)
                if progress_callback and (idx % 10 == 0 or idx == len(image_names) - 1):
                    progress = 0.1 + 0.4 * ((idx + 1) / max(len(image_names), 1))
                    progress_callback(f"Unpacking page {idx + 1} of {len(image_names)}...", progress)

        return pages, meta

    @classmethod
    def _extract_with_unar_or_rar(cls, archive_path: str, temp_dir: str, progress_callback: Optional[Callable[[str, float], None]] = None) -> Tuple[List[str], ComicMetadata]:
        pages = []
        meta = ComicMetadata()

        # Try unar first
        unar_bin = UNAR_PATH or shutil.which('unar')
        extracted_ok = False
        if unar_bin and os.path.exists(unar_bin):
            try:
                cmd = [unar_bin, '-f', '-D', '-o', temp_dir, archive_path]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
                if res.returncode == 0:
                    extracted_ok = True
            except Exception as e:
                extracted_ok = False

        if not extracted_ok:
            # Fallback to rarfile if installed
            try:
                import rarfile
                if unar_bin:
                    rarfile.UNRAR_TOOL = unar_bin
                with rarfile.RarFile(archive_path) as rf:
                    for name in rf.namelist():
                        if os.path.basename(name).lower() == 'comicinfo.xml':
                            try:
                                meta = ComicMetadata.from_xml_bytes(rf.read(name))
                            except Exception:
                                pass
                            break
                    for name in rf.namelist():
                        if cls.is_valid_image_file(name):
                            p = rf.extract(name, temp_dir)
                            pages.append(p)
                    pages.sort(key=lambda p: natural_sort_key(os.path.basename(p)))
                    return pages, meta
            except Exception as e:
                pass

        # Scan whatever was extracted into temp_dir
        pages, scanned_meta = cls._scan_directory(temp_dir)
        if not meta.title and scanned_meta.title:
            meta = scanned_meta

        return pages, meta


class LosslessConverter:
    """
    Performs true lossless conversion from extracted images to PDF.
    - Embeds JPEG bitstreams directly (DCTDecode) with 0 re-compression.
    - Embeds PNG bitstreams directly (FlateDecode).
    - Preserves exact aspect ratio and per-page dimensions (portrait or landscape).
    - Injects rich metadata into the PDF header.
    """

    @staticmethod
    def inspect_images(page_paths: List[str]) -> List[Dict]:
        """Inspect page dimensions, formats, and sizes for previews."""
        info_list = []
        for idx, path in enumerate(page_paths):
            size_bytes = os.path.getsize(path)
            fmt = "Unknown"
            width, height = 0, 0
            try:
                with Image.open(path) as im:
                    fmt = im.format or os.path.splitext(path)[1][1:].upper()
                    width, height = im.size
            except Exception:
                pass
            info_list.append({
                "index": idx + 1,
                "filename": os.path.basename(path),
                "path": path,
                "format": fmt,
                "width": width,
                "height": height,
                "aspect": round(width / height, 3) if height else 1.0,
                "is_spread": (width > height) if height else False,
                "size_bytes": size_bytes
            })
        return info_list

    @classmethod
    def convert_to_pdf(
        cls,
        page_paths: List[str],
        output_pdf_path: str,
        metadata: Optional[ComicMetadata] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Dict:
        """
        Converts the list of page images to a PDF losslessly.
        Returns a dictionary with conversion statistics.
        """
        if not page_paths:
            raise ValueError("No comic book pages found in archive.")

        os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)

        if progress_callback:
            progress_callback("Analyzing pages for lossless direct injection...", 0.55)

        prepared_images = []
        temp_cleaned_files = []
        jpeg_count = 0
        png_count = 0
        converted_count = 0

        try:
            total = len(page_paths)
            for idx, p in enumerate(page_paths):
                # Verify image can be parsed directly by img2pdf
                # If img2pdf directly supports it without transcoding, we use the raw file path/bytes.
                # If an image has an unusual color space or corrupt EXIF that causes img2pdf to raise an error,
                # we fall back to a lossless Pillow PNG export (which retains 100% of the pixel values without loss).
                ext = os.path.splitext(p)[1].lower()
                is_safe = False

                if ext in ('.jpg', '.jpeg'):
                    jpeg_count += 1
                    is_safe = True
                elif ext == '.png':
                    png_count += 1
                    is_safe = True

                if is_safe:
                    prepared_images.append(p)
                else:
                    # Test if img2pdf accepts it directly
                    try:
                        with open(p, 'rb') as test_f:
                            img2pdf.convert(test_f.read())
                        prepared_images.append(p)
                        if ext == '.webp':
                            converted_count += 1
                    except Exception:
                        # Lossless fallback: decompress to uncompressed/Flate PNG
                        # Guaranteed exact pixel-for-pixel accuracy
                        with Image.open(p) as im:
                            temp_png = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                            im.save(temp_png.name, format='PNG', optimize=False)
                            temp_cleaned_files.append(temp_png.name)
                            prepared_images.append(temp_png.name)
                            converted_count += 1

                if progress_callback and (idx % 15 == 0 or idx == total - 1):
                    prog = 0.55 + 0.3 * ((idx + 1) / total)
                    progress_callback(f"Preparing page {idx + 1} of {total}...", prog)

            if progress_callback:
                progress_callback("Packaging PDF with lossless stream embedding...", 0.88)

            # Build PDF layout with img2pdf
            # Auto-dimensioning: each page's PDF box matches exact image dimension
            layout_fun = img2pdf.get_layout_fun(
                pagesize=None, # each page sizes to its image
                fit=img2pdf.FitMode.into
            )

            # Build metadata dict for img2pdf
            pdf_kwargs = {}
            if metadata:
                base_name = os.path.splitext(os.path.basename(output_pdf_path))[0]
                title = metadata.get_pdf_title(base_name)
                author = metadata.writer or metadata.publisher or "Comic Book"
                pdf_kwargs['title'] = title
                pdf_kwargs['author'] = author
                if metadata.summary:
                    pdf_kwargs['subject'] = metadata.summary
                keywords = []
                if metadata.series:
                    keywords.append(metadata.series)
                if metadata.genre:
                    keywords.append(metadata.genre)
                if metadata.year:
                    keywords.append(metadata.year)
                if keywords:
                    pdf_kwargs['keywords'] = keywords
                pdf_kwargs['creator'] = "ComicFlux Lossless Comic Engine"
                pdf_kwargs['producer'] = "img2pdf direct stream injector"

            pdf_bytes = img2pdf.convert(prepared_images, layout_fun=layout_fun, **pdf_kwargs)

            with open(output_pdf_path, 'wb') as out_f:
                out_f.write(pdf_bytes)

            if progress_callback:
                progress_callback("Conversion completed!", 1.0)

            pdf_size = os.path.getsize(output_pdf_path)
            original_images_size = sum(os.path.getsize(p) for p in page_paths)

            return {
                "success": True,
                "output_path": output_pdf_path,
                "page_count": total,
                "pdf_size_bytes": pdf_size,
                "original_size_bytes": original_images_size,
                "jpeg_count": jpeg_count,
                "png_count": png_count,
                "other_count": converted_count,
                "metadata": metadata.to_dict() if metadata else {}
            }

        finally:
            # Clean temporary fallback files
            for temp_f in temp_cleaned_files:
                try:
                    if os.path.exists(temp_f):
                        os.remove(temp_f)
                except Exception:
                    pass


def convert_comic_to_pdf(
    input_file: str,
    output_pdf_path: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> Dict:
    """High-level function: converts a CBZ/CBR/folder to PDF."""
    input_file = os.path.abspath(input_file)
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"File not found: {input_file}")

    if output_pdf_path is None:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_pdf_path = os.path.join(os.path.dirname(input_file), f"{base_name}.pdf")

    with tempfile.TemporaryDirectory(prefix="comic_convert_") as temp_dir:
        pages, metadata = ComicExtractor.extract_archive(input_file, temp_dir, progress_callback)
        if not pages:
            raise ValueError(f"No comic images found in {os.path.basename(input_file)}")

        result = LosslessConverter.convert_to_pdf(
            pages,
            output_pdf_path,
            metadata=metadata,
            progress_callback=progress_callback
        )
        return result
