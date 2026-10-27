#!/usr/bin/env python3
"""
CLI tool for Comic Book (CBZ, CBR, ZIP, RAR) to Lossless PDF conversion.
"""

import sys
import os
import argparse
import time
from converter import convert_comic_to_pdf

def print_banner():
    banner = r"""
  ____                  _      _____ _             
 / ___|___  _ __ ___   (_) ___|  ___| |_   ___  __
| |   / _ \| '_ ` _ \  | |/ __| |_  | | | | \ \/ /
| |__| (_) | | | | | | | | (__|  _| | | |_| |>  < 
 \____\___/|_| |_| |_| |_|\___|_|   |_|\__,_/_/\_\
  Lossless CBZ & CBR to PDF Converter
"""
    print(banner)

def format_size(bytes_num: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:3.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"

def progress_bar(message: str, progress: float):
    bar_length = 30
    filled = int(round(bar_length * progress))
    bar = '=' * filled + '-' * (bar_length - filled)
    percent = int(progress * 100)
    sys.stdout.write(f"\r  [{bar}] {percent}% : {message:<35}")
    sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser(
        description="Convert CBZ, CBR, ZIP, RAR comic books to PDF losslessly."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Input comic archive(s) (.cbz, .cbr, .zip, .rar) or folder(s)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory or specific output PDF file path",
        default=None
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Automatically open the converted PDF when done"
    )

    args = parser.parse_args()
    print_banner()

    start_time = time.time()
    converted_count = 0
    total_files = len(args.inputs)

    for idx, input_path in enumerate(args.inputs):
        input_path = os.path.abspath(input_path)
        if not os.path.exists(input_path):
            print(f"❌ Error: File not found: {input_path}")
            continue

        print(f"\n[{idx + 1}/{total_files}] Processing: {os.path.basename(input_path)}")
        
        output_file = None
        if args.output:
            if os.path.isdir(args.output) or len(args.inputs) > 1:
                os.makedirs(args.output, exist_ok=True)
                base = os.path.splitext(os.path.basename(input_path))[0]
                output_file = os.path.join(args.output, f"{base}.pdf")
            else:
                output_file = args.output

        try:
            res = convert_comic_to_pdf(input_path, output_file, progress_callback=progress_bar)
            print() # newline after progress
            print(f"  ✨ Saved to: {res['output_path']}")
            print(f"  📄 Pages: {res['page_count']} (JPEG: {res['jpeg_count']}, PNG: {res['png_count']}, Other: {res['other_count']})")
            print(f"  📦 PDF Size: {format_size(res['pdf_size_bytes'])} (Original images: {format_size(res['original_size_bytes'])})")
            
            meta = res.get('metadata') or {}
            if meta.get('title') or meta.get('series'):
                meta_str = f"Series: {meta.get('series') or 'N/A'}"
                if meta.get('number'):
                    meta_str += f" #{meta.get('number')}"
                if meta.get('writer'):
                    meta_str += f" | Writer: {meta.get('writer')}"
                print(f"  🏷️  Metadata: {meta_str}")

            converted_count += 1

            if args.open and sys.platform == 'darwin':
                os.system(f"open '{res['output_path']}'")

        except Exception as e:
            print(f"\n❌ Conversion failed: {str(e)}")

    elapsed = round(time.time() - start_time, 2)
    print(f"\n🎉 Done! Converted {converted_count}/{total_files} comics in {elapsed}s.")

if __name__ == "__main__":
    main()
