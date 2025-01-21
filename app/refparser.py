## 参考github https://github.com/opencitations/cec/blob/main/extractor/cex/combined.py

import os
import sys
import time
from functools import wraps

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

import json
import spacy
from lxml import etree
import re

def timer_decorator(func):
    """计时装饰器，用于记录函数执行时间"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 获取或创建类的计时字典
        if not hasattr(args[0], '_timing_stats'):
            args[0]._timing_stats = {}
        
        # 更新函数的执行时间
        func_name = func.__name__
        if func_name not in args[0]._timing_stats:
            args[0]._timing_stats[func_name] = []
        args[0]._timing_stats[func_name].append(execution_time)
        
        return result
    return wrapper

class ReferenceParser:
    def __init__(self, xml_file, output_json_file, auxiliar_file=None):
        """
        Initialize the reference parser
        
        Args:
            xml_file: Path to input TEI XML file
            output_json_file: Path to output JSON file
            auxiliar_file: Path to special cases JSON file for tokenizer customization
        """
        self.xml_file = xml_file
        self.output_json_file = output_json_file
        
        # 设置默认的auxiliar_file路径
        if auxiliar_file is None:
            # 使用绝对路径指向项目根目录下的special_cases.json
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.auxiliar_file = os.path.join(base_dir, 'app/special_cases.json')
        else:
            self.auxiliar_file = auxiliar_file
        
        self._timing_stats = {}  # 存储各函数执行时间的字典
        
        # 加载spaCy模型并自定义tokenizer
        self.nlp = self._load_spacy_model()
        if os.path.exists(self.auxiliar_file):
            self.nlp = self.customize_tokenizer(self.nlp, self.auxiliar_file)
        else:
            print(f"Warning: auxiliar_file not found at {self.auxiliar_file}")
    
    @timer_decorator
    def customize_tokenizer(self, nlp, auxiliar_file):
        with open(auxiliar_file, 'r') as file:
            special_cases = json.load(file)
        for word, tokens in special_cases.items():
            nlp.tokenizer.add_special_case(word, tokens)
        return nlp

    @timer_decorator
    def _load_spacy_model(self):
        """Load spaCy model for sentence segmentation"""
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Model not found. Installing en_core_web_sm model")
            spacy.cli.download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
        return nlp
    
    @timer_decorator
    def test_model_segmentation(self, text):

        doc = self.nlp(text)
        
        return [sent.text.strip() for sent in doc.sents]

    @timer_decorator
    def get_text_before_ref(self, ref, ns):
        """Extract text before reference citation"""
        preceding_text = ref.xpath('preceding-sibling::text()', namespaces=ns)
        text_before_ref = " ".join(preceding_text).strip() if preceding_text else ""
        text_before_ref = re.sub(r'^[^\w\s]+', '', text_before_ref)
        sentences = self.test_model_segmentation(text_before_ref)
        text_before_ref = sentences[-1].strip() if sentences else ""
        return text_before_ref

    @timer_decorator
    def get_text_after_ref(self, ref, ns):
        """Extract text after reference citation"""
        following_text = ref.xpath('following-sibling::text()', namespaces=ns)
        text_after_ref = " ".join(following_text).strip() if following_text else ""
        sentences = self.test_model_segmentation(text_after_ref)
        text_after_ref = sentences[0].strip() if sentences else ""
        return text_after_ref

    @timer_decorator
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

    @timer_decorator
    def parse_references(self):
        """Parse references and their contexts from TEI XML"""
        start_time = time.time()
        
        # 记录开始解析的时间
        parse_start = time.time()
        tree = etree.parse(self.xml_file)
        root = tree.getroot()
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
        parse_time = time.time() - parse_start
        
        # 记录收集参考文献的时间
        ref_collect_start = time.time()
        references = {}
        for ref_node in root.findall('.//tei:biblStruct', namespaces=ns):
            ref_id = ref_node.get('{http://www.w3.org/XML/1998/namespace}id', '')
            if ref_id:
                ref_details = self.extract_reference_details(ref_node, ns)
                references[ref_id] = {
                    "reference_details": ref_details,
                    "citations": []
                }
        ref_collect_time = time.time() - ref_collect_start
        
        # 记录处理引用的时间
        citation_process_start = time.time()
        last_head = None
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

        citation_process_time = time.time() - citation_process_start
        
        # 计算总执行时间
        total_time = time.time() - start_time
        
        # 记录执行时间统计
        self._timing_stats['total_execution'] = total_time
        self._timing_stats['xml_parsing'] = parse_time
        self._timing_stats['reference_collection'] = ref_collect_time
        self._timing_stats['citation_processing'] = citation_process_time
        
        # 打印执行时间统计
        # self.print_timing_stats()
        
        return references

    def print_timing_stats(self):
        """打印各个部分的执行时间统计"""
        print("\n" + "="*50)
        print("执行时间统计:")
        print("="*50)
        
        # 打印总执行时间
        if 'total_execution' in self._timing_stats:
            print(f"\n总执行时间: {self._timing_stats['total_execution']:.2f} 秒")
        
        # 打印主要阶段时间
        print("\n主要阶段耗时:")
        if 'xml_parsing' in self._timing_stats:
            print(f"XML解析: {self._timing_stats['xml_parsing']:.2f} 秒")
        if 'reference_collection' in self._timing_stats:
            print(f"参考文献收集: {self._timing_stats['reference_collection']:.2f} 秒")
        if 'citation_processing' in self._timing_stats:
            print(f"引用处理: {self._timing_stats['citation_processing']:.2f} 秒")
        
        # 打印各函数平均执行时间
        print("\n各函数平均执行时间:")
        for func_name, times in self._timing_stats.items():
            if isinstance(times, list):  # 只处理函数调用时间列表
                avg_time = sum(times) / len(times)
                print(f"{func_name}: {avg_time:.4f} 秒 (调用 {len(times)} 次)")
        
        print("="*50 + "\n")

def main():
    """Main function to demonstrate usage"""
    xml_file = "/home/gaof23/projects/sciparser/tmp/xmls/10.1007_s41870-019-00409-4.grobid.xml"
    output_json = "references.json"
    auxiliar_file = "special_cases.json"
    
    parser = ReferenceParser(xml_file, output_json, auxiliar_file)
    references = parser.parse_references()
    
    # 打印统计信息
    print(f"Extracted {len(references)} references")
    total_citations = sum(len(ref['citations']) for ref in references.values())
    print(f"Found {total_citations} citations")

if __name__ == "__main__":
    main()