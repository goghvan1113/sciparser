import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

import json
import spacy
from lxml import etree
import re

class ReferenceParser:
    def __init__(self, xml_file, output_json_file, auxiliar_file):
        """
        Initialize the reference parser
        
        Args:
            xml_file: Path to input TEI XML file
            output_json_file: Path to output JSON file
        """
        self.xml_file = xml_file
        self.output_json_file = output_json_file
        self.nlp = self._load_spacy_model()
        self.auxiliar_file = auxiliar_file
    
    def customize_tokenizer(self, nlp, auxiliar_file):
        with open(auxiliar_file, 'r') as file:
            special_cases = json.load(file)
        for word, tokens in special_cases.items():
            nlp.tokenizer.add_special_case(word, tokens)
        return nlp

    def _load_spacy_model(self):
        """Load spaCy model for sentence segmentation"""
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Model not found. Installing en_core_web_sm model")
            spacy.cli.download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
        return nlp
    
    def test_model_segmentation(self, text):
        nlp = self._load_spacy_model()
        nlp = self.customize_tokenizer(nlp, self.auxiliar_file)
        doc = nlp(text)
        return [sent.text.strip() for sent in doc.sents]

    def get_text_before_ref(self, ref, ns):
        """Extract text before reference citation"""
        preceding_text = ref.xpath('preceding-sibling::text()', namespaces=ns)
        text_before_ref = " ".join(preceding_text).strip() if preceding_text else ""
        text_before_ref = re.sub(r'^[^\w\s]+', '', text_before_ref)
        sentences = self.test_model_segmentation(text_before_ref)
        text_before_ref = sentences[-1].strip() if sentences else ""
        return text_before_ref

    def get_text_after_ref(self, ref, ns):
        """Extract text after reference citation"""
        following_text = ref.xpath('following-sibling::text()', namespaces=ns)
        text_after_ref = " ".join(following_text).strip() if following_text else ""
        sentences = self.test_model_segmentation(text_after_ref)
        text_after_ref = sentences[0].strip() if sentences else ""
        return text_after_ref

    def extract_reference_details(self, ref_node, ns):
        """Extract details from a reference node"""
        # Extract authors
        authors = []
        for author in ref_node.findall('.//tei:author', namespaces=ns):
            name_parts = []
            forename = author.find('.//tei:forename', namespaces=ns)
            if forename is not None and forename.text:
                name_parts.append(forename.text)
            surname = author.find('.//tei:surname', namespaces=ns)
            if surname is not None and surname.text:
                name_parts.append(surname.text)
            if name_parts:
                authors.append(" ".join(name_parts))

        # Extract title - try different types of titles
        title = ""
        # First try title with level="a" (article title)
        title_node = ref_node.find('.//tei:title[@level="a"]', namespaces=ns)
        if title_node is not None and title_node.text:
            title = title_node.text
        # If not found, try title with level="m" (monograph/book title)
        if not title:
            title_node = ref_node.find('.//tei:title[@level="m"]', namespaces=ns)
            if title_node is not None and title_node.text:
                title = title_node.text
        # If still not found, try any title
        if not title:
            title_node = ref_node.find('.//tei:title', namespaces=ns)
            if title_node is not None and title_node.text:
                title = title_node.text

        # Extract year
        year = ""
        date_node = ref_node.find('.//tei:date', namespaces=ns)
        if date_node is not None and date_node.get('when'):
            year = date_node.get('when')[:4]  # Get just the year

        return {
            "authors": authors,
            "title": title,
            "year": year
        }

    def parse_references(self):
        """Parse references and their contexts from TEI XML"""
        tree = etree.parse(self.xml_file)
        root = tree.getroot()
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}

        # Dictionary to store reference details
        references = {}
        
        # First pass: collect all bibliographic references
        for ref_node in root.findall('.//tei:biblStruct', namespaces=ns):
            ref_id = ref_node.get('{http://www.w3.org/XML/1998/namespace}id', '')
            if ref_id:
                ref_details = self.extract_reference_details(ref_node, ns)
                references[ref_id] = {
                    "reference_details": ref_details,
                    "citations": []
                }

        # Track the current section heading
        last_head = None
        
        # Check section numbering style
        head_elements = root.findall(".//tei:div/tei:head", namespaces=ns)
        has_n_attribute = any("n" in head.attrib for head in head_elements)
        roman_numbers_pattern = r'^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})\.*(?:\.[A-Z0-9]+\.*)*\s+'
        has_roman_numeration = any(re.search(roman_numbers_pattern, head.text.strip() if head.text else "") 
                                  for head in head_elements)
        head_n_attribute = sum("n" in head.attrib for head in head_elements)
        head_no_n_attribute = sum("n" not in head.attrib for head in head_elements)

        # Second pass: collect all citations in the text
        for div in root.findall('.//tei:div', namespaces=ns):
            # Extract section heading
            head = div.find("./tei:head", namespaces=ns)
            if head is not None:
                head_text = head.text.strip() if head.text else ""
                
                # Handle different section numbering styles
                if head_n_attribute > head_no_n_attribute:
                    if has_n_attribute:
                        if 'n' in head.attrib:
                            n = head.get("n")
                            n_parts = n.split(".")
                            if '' in n_parts:
                                n_parts.remove('')
                            if len(n_parts) == 1:
                                if re.search(r'\b\d+(\.\d+)+\b', head_text):
                                    split_string = re.split(r'\b\d+(\.\d+)+\b', head_text)
                                    split_string = [substring.strip() for substring in split_string]
                                    last_head = split_string[0].strip()
                                else:
                                    last_head = head_text
                elif has_roman_numeration:
                    if re.search(r'^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})\.*\s+', head_text):
                        pattern = re.compile(r'^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})\.*\s+')
                        match = pattern.search(head_text)
                        if match:
                            match = match.group().strip()
                            last_head = head_text.replace(match, "")
                else:
                    last_head = head_text

            # Process citations in current section
            for ref in div.findall(".//tei:ref[@type='bibr']", namespaces=ns):
                target = ref.get('target', '').lstrip('#')
                if target in references:
                    text_before = self.get_text_before_ref(ref, ns)
                    ref_text = ref.text.strip() if ref.text else ""
                    text_after = self.get_text_after_ref(ref, ns)
                    
                    citation_context = {
                        "section": last_head,  # Add section heading
                        "text_before": text_before,
                        "citation": ref_text,
                        "text_after": text_after,
                        "full_context": f"{text_before} {ref_text} {text_after}".strip()
                    }
                    
                    references[target]["citations"].append(citation_context)

        # # Write results to JSON file
        # with open(self.output_json_file, 'w', encoding='utf-8') as f:
        #     json.dump(references, f, indent=2, ensure_ascii=False)

        return references

def main():
    """Main function to demonstrate usage"""
    xml_file = "/home/gaof23/projects/sciparser/tmp/xmls/10.1007_s41870-019-00409-4.grobid.xml"  # Input XML file path
    output_json = "references.json"    # Output JSON file path
    
    parser = ReferenceParser(xml_file, output_json)
    references = parser.parse_references()
    
    # Print some statistics
    print(f"Extracted {len(references)} references")
    total_citations = sum(len(ref['citations']) for ref in references.values())
    print(f"Found {total_citations} citations")

if __name__ == "__main__":
    main() 