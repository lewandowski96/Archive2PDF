# 📚 ComicFlux — Lossless Comic to PDF Converter

A high-performance comic book converter designed to convert **CBZ** and **CBR** archives into **PDF** while preserving **100% original quality (lossless)**.

---

## 💎 Why It Is Truly Lossless

Standard PDF converters decompress comic images into raw bitmap pixels and re-encode them as new JPEGs (often at 75–85% quality). This causes **generational quality loss, blurriness, and color distortion**.

**ComicFlux uses Direct Bitstream Injection (`img2pdf`)**:
- **JPEG images** (`.jpg`, `.jpeg`): The original JPEG DCT coefficient bitstream is embedded directly into the PDF container without decoding or re-compressing. **0.00% generation loss.**
- **PNG images** (`.png`): Embedded using PDF `FlateDecode` lossless streams.
- **Natural Alphanumeric Sorting**: Ensures `page_2` comes before `page_10`, preventing pages from being scrambled.
- **Double-Page Splash Spreads**: Dynamic per-page sizing ensures landscape splash pages display without letterbox bars.
- **Metadata Preservation**: Detects and extracts `ComicInfo.xml` (Title, Series, Issue #, Writer, Year, Summary) and writes them into PDF document properties.

---

## 🚀 How to Run

### 1. Web Application (GUI)
You can launch the web interface with a single command or by double-clicking:

- **Option A (Double-Click in Finder)**:
  Double-click `start_app.command`.

- **Option B (Terminal)**:
  ```bash
  python3 main.py
  ```

Your browser will automatically open to `http://127.0.0.1:8765`.
- **Drag & drop** single or multiple `.cbz`, `.cbr`, `.zip`, `.rar` files.
- Inspect extracted pages in the high-res Lightbox modal.
- Click **Convert** or **Convert All**.
- Download individual PDFs or **Download All as ZIP**.

---

### 2. Command Line Interface (CLI)
You can also convert comics directly from the terminal:

```bash
# Convert a single comic book
python3 cli.py "Spider-Man #01.cbz"

# Convert a comic and automatically open the PDF
python3 cli.py "Batman.cbr" --open

# Batch convert multiple comics into a specific folder
python3 cli.py ~/Downloads/Comics/*.cbz -o ~/Documents/PDFs/
```

---

## 🛠️ Requirements & System Setup

All core dependencies are installed. If setting up on a new environment:

```bash
# Install Python packages
pip install -r requirements.txt

# Install unar for CBR / RAR archive support (macOS)
brew install unar
```
