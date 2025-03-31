import json
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import re
import os

logger = logging.getLogger(__name__)

class PaperParser:
    """
    Class for parsing OCR-processed academic paper JSONs
    """
    
    def __init__(self, output_dir: str = "output"):
        """
        Initialize the PaperParser
        
        Args:
            output_dir: Directory where parsed data will be saved
        """
    
    def parse_paper(self, ocr_data: Dict[str, Any], save_output: bool = False, output_filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse OCR-processed paper data
        
        Args:
            ocr_data: OCR-processed paper data
            save_output: Option to save parsed data as JSON
            output_filename: Name of the output JSON file (if None, auto-generated)
            
        Returns:
            Parsed paper structure
        """
        try:
            # Convert to dict if JSON string
            if isinstance(ocr_data, str):
                ocr_data = json.loads(ocr_data)
            
            # Create paper structure
            paper_structure = {
                "title": self._extract_title(ocr_data),
                "abstract": self._extract_abstract(ocr_data),
                "sections": self._extract_sections(ocr_data),
                "references": self._extract_references(ocr_data),
                "metadata": self._extract_metadata(ocr_data)
            }
            
            # Save parsed data
            if save_output:
                if output_filename is None:
                    # Create filename from title
                    safe_title = "".join(c if c.isalnum() else "_" for c in paper_structure["title"])
                    safe_title = safe_title[:50] if safe_title else "parsed_paper"  # Limit filename length
                    output_filename = f"parsed_{safe_title}.json"
                
                output_path = self.output_dir / output_filename
                self._save_parsed_data(paper_structure, output_path)
                logger.info(f"Parsed data saved: {output_path}")
            
            return paper_structure
        
        except Exception as e:
            logger.error(f"Error parsing paper: {e}")
            raise
    
    def parse_from_file(self, json_file_path: str, save_output: bool = True, output_filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse paper data from a JSON file
        
        Args:
            json_file_path: Path to the JSON file
            save_output: Option to save parsed data as JSON
            output_filename: Name of the output JSON file (if None, auto-generated)
            
        Returns:
            Parsed paper structure
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
            
            # Generate output filename from input if not specified
            if save_output and output_filename is None:
                input_filename = Path(json_file_path).stem
                output_filename = f"parsed_{input_filename}.json"
            
            return self.parse_paper(ocr_data, save_output, output_filename)
        except Exception as e:
            logger.error(f"Error reading JSON file: {e}")
            raise
    
    def _extract_title(self, ocr_data: Dict[str, Any]) -> str:
        """
        Extract paper title
        
        Args:
            ocr_data: OCR-processed paper data
            
        Returns:
            Paper title
        """
        try:
            if "pages" in ocr_data and len(ocr_data["pages"]) > 0:
                first_page = ocr_data["pages"][0]
                markdown = first_page.get("markdown", "")
                
                # Look for title line starting with # in markdown
                lines = markdown.split('\n')
                for line in lines:
                    if line.startswith('# '):
                        return line[2:].strip()
                
                # If no title found, look at first few lines of first page
                if lines and len(lines) > 0:
                    # First line is usually the title
                    return lines[0].strip()
            
            return "Title not found"
        
        except Exception as e:
            logger.error(f"Error extracting title: {e}")
            return "Title not found"
    
    def _extract_abstract(self, ocr_data: Dict[str, Any]) -> str:
        """
        Extract paper abstract
        
        Args:
            ocr_data: OCR-processed paper data
            
        Returns:
            Paper abstract
        """
        try:
            if "pages" in ocr_data and len(ocr_data["pages"]) > 0:
                first_page = ocr_data["pages"][0]
                markdown = first_page.get("markdown", "")
                
                # Look for abstract section
                abstract_match = re.search(r'(?:####\s*Abstract|Abstract)(?:\n+|\s+)(.*?)(?=\n\n\n|\n##|\n#)', markdown, re.DOTALL | re.IGNORECASE)
                if abstract_match:
                    return abstract_match.group(1).strip()
            
            return "Abstract not found"
        
        except Exception as e:
            logger.error(f"Error extracting abstract: {e}")
            return "Abstract not found"
    
    def _extract_sections(self, ocr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract paper sections with text, images, and formulas
        
        Args:
            ocr_data: OCR-processed paper data
            
        Returns:
            List of sections with their content
        """
        sections = []
        
        try:
            if "pages" not in ocr_data:
                return sections
            
            # Combine all pages' markdown content
            full_markdown = ""
            images_by_page = {}
            
            for page in ocr_data["pages"]:
                page_idx = page.get("index", 0)
                markdown = page.get("markdown", "")
                full_markdown += markdown + "\n\n"
                
                # Collect images from this page
                images = page.get("images", [])
                if images:
                    images_by_page[page_idx] = images
            
            # Split markdown into sections based on headers
            # Match both # and ## headers, as well as numbered headers like "1. Introduction"
            section_pattern = r'(?:^|\n)(?:#{1,2}\s+|(?:\d+\.)\s+)([^\n]+)(?:\n|$)'
            section_matches = list(re.finditer(section_pattern, full_markdown, re.MULTILINE))
            
            # If no sections found, treat the whole document as one section
            if not section_matches:
                section = {
                    "title": "Document",
                    "text": [full_markdown.strip()],
                    "images": [],
                    "formulas": []
                }
                
                # Add all images to this section
                for page_idx, images in images_by_page.items():
                    for img in images:
                        section["images"].append({
                            "page": page_idx,
                            "id": img.get("id", ""),
                            "base64": img.get("image_base64", ""),
                            "coordinates": {
                                "top_left_x": img.get("top_left_x", 0),
                                "top_left_y": img.get("top_left_y", 0),
                                "bottom_right_x": img.get("bottom_right_x", 0),
                                "bottom_right_y": img.get("bottom_right_y", 0)
                            }
                        })
                
                sections.append(section)
                return sections
            
            # Process each section
            for i, match in enumerate(section_matches):
                section_title = match.group(1).strip()
                section_start = match.start()
                
                # Determine section end (next section start or end of document)
                if i < len(section_matches) - 1:
                    section_end = section_matches[i + 1].start()
                else:
                    section_end = len(full_markdown)
                
                section_content = full_markdown[section_start:section_end].strip()
                
                # Remove the section title from the content
                section_content = re.sub(r'^(?:#{1,2}\s+|(?:\d+\.)\s+)([^\n]+)(?:\n|$)', '', section_content, 1)
                
                # Extract formulas (text between $ and $ or $$ and $$)
                formulas = []
                formula_pattern = r'\$\$(.*?)\$\$|\$(.*?)\$'
                formula_matches = re.finditer(formula_pattern, section_content, re.DOTALL)
                
                for f_match in formula_matches:
                    formula_text = f_match.group(1) or f_match.group(2)
                    if formula_text:
                        formulas.append(formula_text.strip())
                
                # Remove formulas from text for cleaner text content
                clean_text = re.sub(formula_pattern, ' FORMULA ', section_content)
                
                # Split text into paragraphs
                paragraphs = [p.strip() for p in clean_text.split('\n\n') if p.strip()]
                
                # Create section object
                section = {
                    "title": section_title,
                    "text": paragraphs,
                    "images": [],
                    "formulas": formulas
                }
                
                # Find images that belong to this section
                # This is a heuristic - we check if image references appear in the section content
                for page_idx, images in images_by_page.items():
                    for img in images:
                        img_id = img.get("id", "")
                        if img_id and img_id in section_content:
                            section["images"].append({
                                "page": page_idx,
                                "id": img_id,
                                "base64": img.get("image_base64", ""),
                                "coordinates": {
                                    "top_left_x": img.get("top_left_x", 0),
                                    "top_left_y": img.get("top_left_y", 0),
                                    "bottom_right_x": img.get("bottom_right_x", 0),
                                    "bottom_right_y": img.get("bottom_right_y", 0)
                                }
                            })
                
                sections.append(section)
            
            return sections
        
        except Exception as e:
            logger.error(f"Error extracting sections: {e}")
            return sections
    
    def _extract_references(self, ocr_data: Dict[str, Any]) -> List[str]:
        """
        Extract paper references
        
        Args:
            ocr_data: OCR-processed paper data
            
        Returns:
            List of references
        """
        references = []
        
        try:
            if "pages" not in ocr_data:
                return references
            
            # Combine all pages' markdown content
            full_markdown = ""
            for page in ocr_data["pages"]:
                full_markdown += page.get("markdown", "") + "\n\n"
            
            # Look for references section
            ref_match = re.search(r'(?:##\s*References|References)(?:\n+|\s+)(.*?)(?=\n\n\n|\n##|\n#|$)', full_markdown, re.DOTALL | re.IGNORECASE)
            if not ref_match:
                return references
            
            ref_content = ref_match.group(1).strip()
            
            # Try to extract references by pattern [1] or 1.
            ref_pattern = r'(?:\[(\d+)\]|\n(\d+)\.)\s+(.*?)(?=\n\[|\n\d+\.|$)'
            ref_matches = re.finditer(ref_pattern, '\n' + ref_content, re.DOTALL)
            
            for match in ref_matches:
                ref_num = match.group(1) or match.group(2)
                ref_text = match.group(3).strip()
                if ref_text:
                    references.append(f"[{ref_num}] {ref_text}")
            
            # If the above method doesn't work, try line by line
            if not references:
                lines = ref_content.split('\n')
                current_ref = ""
                
                for line in lines[1:]:  # First line might be the title
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check for new reference start
                    if re.match(r'^\[\d+\]|\d+\.', line):
                        if current_ref:
                            references.append(current_ref.strip())
                        current_ref = line
                    else:
                        if current_ref:
                            current_ref += " " + line
                
                # Add the last reference
                if current_ref:
                    references.append(current_ref.strip())
            
            return references
        
        except Exception as e:
            logger.error(f"Error extracting references: {e}")
            return references
    
    def _extract_metadata(self, ocr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract paper metadata
        
        Args:
            ocr_data: OCR-processed paper data
            
        Returns:
            Metadata dictionary
        """
        metadata = {
            'authors': [],
            'affiliations': [],
            'keywords': [],
            'doi': '',
            'publication_date': '',
            'journal': ''
        }
        
        try:
            if "pages" in ocr_data and len(ocr_data["pages"]) > 0:
                first_page = ocr_data["pages"][0]
                markdown = first_page.get("markdown", "")
                
                # Find authors
                # Usually they come after the title and before the abstract
                title = self._extract_title(ocr_data)
                if title != "Title not found" and title in markdown:
                    after_title = markdown[markdown.find(title) + len(title):]
                    abstract_idx = after_title.lower().find('abstract')
                    
                    if abstract_idx != -1:
                        author_section = after_title[:abstract_idx].strip()
                        # Split by lines and find potential authors
                        lines = author_section.split('\n')
                        for line in lines:
                            # Authors are usually separated by commas or <br>
                            if '<br>' in line:
                                potential_authors = line.split('<br>')
                                for author in potential_authors:
                                    if author.strip() and not author.strip().startswith('#'):
                                        metadata['authors'].append(author.strip())
                            elif ',' in line and not line.startswith('http') and not line.startswith('www'):
                                for author in line.split(','):
                                    if author.strip() and not author.strip().startswith('#'):
                                        metadata['authors'].append(author.strip())
                
                # Find affiliations
                affiliation_match = re.search(r'<br>(.*?)(?=\n\n|\n####)', markdown)
                if affiliation_match:
                    affiliation = affiliation_match.group(1).strip()
                    metadata['affiliations'].append(affiliation)
                
                # Find keywords
                keywords_idx = markdown.lower().find('keywords')
                if keywords_idx != -1:
                    keywords_text = markdown[keywords_idx:].split('\n', 1)[0]
                    if ':' in keywords_text:
                        keywords = keywords_text.split(':', 1)[1]
                        metadata['keywords'] = [k.strip() for k in keywords.split(',')]
                
                # Find DOI
                doi_match = re.search(r'doi[:\s]+([^\s]+)', markdown, re.IGNORECASE)
                if doi_match:
                    metadata['doi'] = doi_match.group(1)
            
            return metadata
        
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return metadata
    
    def _save_parsed_data(self, data: Dict[str, Any], output_path: Path) -> None:
        """
        Save parsed data to a JSON file
        
        Args:
            data: Data to save
            output_path: Output file path
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            raise

# TODO: Add support for more document types (e.g., arXiv papers, conference papers)
# TODO: Improve section detection for papers with non-standard formatting
# TODO: Add better formula extraction and rendering
# TODO: Implement citation network analysis
# TODO: Add support for extracting tables from papers
# TODO: Improve author name and affiliation parsing
# TODO: Add language detection and multilingual support
# TODO: Implement a caching mechanism for parsed papers
# TODO: Add validation for parsed paper structure