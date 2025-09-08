#!/usr/bin/env python3
"""
Table of Contents Extraction Script using pdfminer.six

This script uses the pdfminer.six library to extract Table of Contents from PDF files
that do not have bookmarks. It analyzes the text content to identify TOC patterns
and extracts the hierarchical structure.

Usage:
    python extract_toc_pdfminer.py input.pdf [output.txt]
    python extract_toc_pdfminer.py https://example.com/document.pdf [output.txt]

Example:
    python extract_toc_pdfminer.py document.pdf toc_output.txt
    python extract_toc_pdfminer.py document.pdf --format json --output toc.json
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

try:
    from pdfminer.high_level import extract_text
    from pdfminer.layout import LAParams
except ImportError as e:
    print("Error: pdfminer.six is required but not installed.")
    print("Install with: pip install pdfminer.six")
    sys.exit(1)

import requests


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


class TOCEntry:
    """Represents a Table of Contents entry."""
    
    def __init__(self, title: str, page: Optional[int] = None, level: int = 1):
        self.title = title.strip()
        self.page = page
        self.level = level
        self.children: List['TOCEntry'] = []
    
    def add_child(self, entry: 'TOCEntry') -> None:
        """Add a child entry to this TOC entry."""
        self.children.append(entry)
    
    def to_dict(self) -> Dict:
        """Convert TOC entry to dictionary format."""
        result = {
            'title': self.title,
            'level': self.level
        }
        if self.page is not None:
            result['page'] = self.page
        if self.children:
            result['children'] = [child.to_dict() for child in self.children]
        return result
    
    def to_text(self, indent: str = "  ") -> str:
        """Convert TOC entry to text format with indentation."""
        text = f"{indent * (self.level - 1)}{self.title}"
        if self.page is not None:
            text += f" .................. {self.page}"
        text += "\n"
        
        for child in self.children:
            text += child.to_text(indent)
        
        return text


class PDFTOCExtractor:
    """Extracts Table of Contents from PDF files using pdfminer.six."""
    
    def __init__(self, verbose: bool = False):
        self.logger = logging.getLogger(__name__)
        self.verbose = verbose
        
        # TOC detection patterns
        self.toc_titles = [
            "índice", "indice", "table of contents", "contents", 
            "tabla de contenidos", "contenido", "contenidos", 
            "sumario", "index", "sommario", "inhaltsverzeichnis",
            "table des matières", "matières"
        ]
        
        # Patterns for TOC entries
        self.page_number_pattern = re.compile(r'\.{3,}.*?(\d+)\s*$')
        self.numbered_list_pattern = re.compile(r'^(\d+(?:\.\d+)*\.?)\s+(.+)', re.MULTILINE)
        self.chapter_pattern = re.compile(r'^(chapter|ch\.?|section|sec\.?)\s+(\d+(?:\.\d+)*\.?)\s*:?\s*(.+)', re.IGNORECASE)
        self.roman_numeral_pattern = re.compile(r'^([ivxlcdm]+)\.\s+(.+)', re.IGNORECASE)
        
    def is_url(self, path: str) -> bool:
        """Check if the path is a URL."""
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def download_pdf(self, url: str, temp_path: Path) -> None:
        """Download PDF from URL to temporary file."""
        self.logger.info(f"Downloading PDF from: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        self.logger.info(f"Downloaded PDF to: {temp_path}")
    
    def extract_text_from_pdf(self, pdf_path: Union[str, Path]) -> str:
        """Extract text from PDF using pdfminer.six."""
        self.logger.info(f"Extracting text from PDF: {pdf_path}")
        
        # Configure layout analysis parameters for better text extraction
        laparams = LAParams(
            word_margin=0.1,
            char_margin=2.0,
            line_margin=0.5,
            boxes_flow=0.5,
            all_texts=False
        )
        
        try:
            text = extract_text(str(pdf_path), laparams=laparams)
            self.logger.info(f"Extracted {len(text)} characters from PDF")
            return text
        except Exception as e:
            self.logger.error(f"Failed to extract text from PDF: {e}")
            raise
    
    def find_toc_sections(self, text: str) -> List[Tuple[int, int, str]]:
        """Find potential TOC sections in the text."""
        lines = text.split('\n')
        toc_sections = []
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Check if line contains TOC title indicators
            for toc_title in self.toc_titles:
                if toc_title in line_lower:
                    # Look for the end of the TOC section
                    end_idx = self._find_toc_end(lines, i)
                    section_text = '\n'.join(lines[i:end_idx])
                    toc_sections.append((i, end_idx, section_text))
                    self.logger.debug(f"Found potential TOC section at lines {i}-{end_idx}")
                    break
        
        return toc_sections
    
    def _find_toc_end(self, lines: List[str], start_idx: int) -> int:
        """Find the end of a TOC section."""
        max_lines_to_check = min(50, len(lines) - start_idx)
        toc_pattern_count = 0
        last_toc_line = start_idx
        
        for i in range(start_idx + 1, start_idx + max_lines_to_check):
            if i >= len(lines):
                break
                
            line = lines[i].strip()
            if not line:
                continue
            
            # Check if line looks like a TOC entry
            if (self.page_number_pattern.search(line) or 
                self.numbered_list_pattern.match(line) or
                self.chapter_pattern.match(line)):
                toc_pattern_count += 1
                last_toc_line = i
            elif toc_pattern_count > 0 and not self._is_likely_toc_line(line):
                # Found non-TOC content after TOC patterns
                break
        
        # Return at least a few lines after the start, or the last TOC line
        return max(start_idx + 5, last_toc_line + 1)
    
    def _is_likely_toc_line(self, line: str) -> bool:
        """Check if a line is likely part of a TOC."""
        line = line.strip()
        if not line:
            return False
        
        # Check for common TOC patterns
        patterns = [
            self.page_number_pattern,
            self.numbered_list_pattern,
            self.chapter_pattern,
            self.roman_numeral_pattern
        ]
        
        return any(pattern.search(line) for pattern in patterns)
    
    def parse_toc_entries(self, toc_text: str) -> List[TOCEntry]:
        """Parse TOC entries from extracted text."""
        lines = [line.strip() for line in toc_text.split('\n') if line.strip()]
        entries = []
        
        for line in lines:
            entry = self._parse_toc_line(line)
            if entry:
                entries.append(entry)
        
        # Build hierarchical structure
        return self._build_hierarchy(entries)
    
    def _parse_toc_line(self, line: str) -> Optional[TOCEntry]:
        """Parse a single TOC line to extract title, level, and page number."""
        # Skip lines that are just TOC headers
        line_lower = line.lower()
        if any(title in line_lower for title in self.toc_titles):
            return None
        
        # Try to extract page number first
        page_match = self.page_number_pattern.search(line)
        page_num = None
        title = line
        
        if page_match:
            page_num = int(page_match.group(1))
            title = line[:page_match.start()].strip()
            # Remove trailing dots
            title = re.sub(r'\.+$', '', title).strip()
        
        # Determine hierarchy level based on numbering
        level = 1
        
        # Check for numbered entries (1.2.3 format)
        numbered_match = self.numbered_list_pattern.match(line)
        if numbered_match:
            number_part = numbered_match.group(1).rstrip('.')  # Remove trailing dot for counting
            title = numbered_match.group(2).strip()
            # Remove page numbers from title if present
            if page_match:
                title = title[:page_match.start()].strip() if page_match.start() < len(title) else title
                title = re.sub(r'\.+$', '', title).strip()
            
            level = number_part.count('.') + 1
        
        # Check for chapter patterns
        chapter_match = self.chapter_pattern.match(line)
        if chapter_match:
            title = chapter_match.group(3).strip()
            level = 1  # Chapters are typically top-level
        
        # Check for roman numerals
        roman_match = self.roman_numeral_pattern.match(line)
        if roman_match:
            title = roman_match.group(2).strip()
            level = 1  # Roman numerals typically indicate top-level
        
        # Clean up title
        title = re.sub(r'\.+$', '', title).strip()
        
        if title and len(title) > 1:  # Ensure we have a meaningful title
            return TOCEntry(title, page_num, level)
        
        return None
    
    def _build_hierarchy(self, entries: List[TOCEntry]) -> List[TOCEntry]:
        """Build hierarchical structure from flat list of TOC entries."""
        if not entries:
            return []
        
        root_entries = []
        stack = []  # Stack to keep track of parent entries at each level
        
        for entry in entries:
            # Pop from stack until we find the appropriate parent level
            while stack and stack[-1].level >= entry.level:
                stack.pop()
            
            if stack:
                # Add as child to the last entry in stack
                stack[-1].add_child(entry)
            else:
                # This is a root-level entry
                root_entries.append(entry)
            
            stack.append(entry)
        
        return root_entries
    
    def extract_toc(self, pdf_source: Union[str, Path]) -> List[TOCEntry]:
        """Extract Table of Contents from PDF file or URL."""
        temp_file = None
        
        try:
            # Handle URL downloads
            if isinstance(pdf_source, str) and self.is_url(pdf_source):
                temp_file = Path(f"/tmp/downloaded_pdf_{hash(pdf_source)}.pdf")
                self.download_pdf(pdf_source, temp_file)
                pdf_path = temp_file
            else:
                pdf_path = Path(pdf_source)
                if not pdf_path.exists():
                    raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            # Extract text from PDF
            text = self.extract_text_from_pdf(pdf_path)
            
            # Find TOC sections
            toc_sections = self.find_toc_sections(text)
            
            if not toc_sections:
                self.logger.warning("No TOC sections found in the PDF")
                return []
            
            # Parse TOC entries from all found sections
            all_entries = []
            for start_idx, end_idx, section_text in toc_sections:
                self.logger.info(f"Processing TOC section (lines {start_idx}-{end_idx})")
                entries = self.parse_toc_entries(section_text)
                all_entries.extend(entries)
            
            self.logger.info(f"Extracted {len(all_entries)} TOC entries")
            return all_entries
        
        finally:
            # Clean up temporary file
            if temp_file and temp_file.exists():
                temp_file.unlink()


def save_toc_as_text(entries: List[TOCEntry], output_path: Path) -> None:
    """Save TOC entries as formatted text."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("Table of Contents\n")
        f.write("=" * 50 + "\n\n")
        
        for entry in entries:
            f.write(entry.to_text())


def save_toc_as_json(entries: List[TOCEntry], output_path: Path) -> None:
    """Save TOC entries as JSON."""
    toc_data = {
        'table_of_contents': [entry.to_dict() for entry in entries],
        'total_entries': len(entries)
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(toc_data, f, ensure_ascii=False, indent=2)


def main():
    """Main function to run the TOC extraction script."""
    parser = argparse.ArgumentParser(
        description="Extract Table of Contents from PDF files using pdfminer.six",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python extract_toc_pdfminer.py document.pdf
    python extract_toc_pdfminer.py document.pdf --output toc.txt
    python extract_toc_pdfminer.py document.pdf --format json --output toc.json
    python extract_toc_pdfminer.py https://example.com/doc.pdf --verbose
        """
    )
    
    parser.add_argument(
        'input',
        help='Path to PDF file or URL'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output file path (default: input filename with .txt/.json extension)'
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize extractor
        extractor = PDFTOCExtractor(verbose=args.verbose)
        
        # Extract TOC
        logger.info(f"Extracting TOC from: {args.input}")
        toc_entries = extractor.extract_toc(args.input)
        
        if not toc_entries:
            logger.warning("No Table of Contents found in the PDF")
            return 1
        
        # Determine output path
        if args.output:
            output_path = args.output
        else:
            # Generate default output path
            input_path = Path(args.input) if not extractor.is_url(args.input) else Path("extracted_toc")
            ext = '.json' if args.format == 'json' else '.txt'
            output_path = input_path.with_suffix(ext)
        
        # Save TOC
        if args.format == 'json':
            save_toc_as_json(toc_entries, output_path)
        else:
            save_toc_as_text(toc_entries, output_path)
        
        logger.info(f"TOC saved to: {output_path}")
        
        # Print summary to console
        print(f"\nTable of Contents extracted successfully!")
        print(f"Found {len(toc_entries)} top-level entries")
        print(f"Output saved to: {output_path}")
        
        # Show preview of TOC
        if toc_entries:
            print("\nPreview of extracted TOC:")
            print("-" * 40)
            for i, entry in enumerate(toc_entries[:5]):  # Show first 5 entries
                print(entry.to_text().rstrip())
            if len(toc_entries) > 5:
                print("... (and more)")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to extract TOC: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())