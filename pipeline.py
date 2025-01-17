"""
Grobid XML to Markdown for cleaner LLM corpus

"""
import os


from grobid_parser import parse
from pdf_parser import Parser

class CachedGrobidParser:
    def __init__(self, cache_dir='./.tmp', use_cache=True):
        self.cache_dir = cache_dir
        self.use_cache = use_cache
        self.parser = Parser('grobid', host='127.0.0.1', port='8070')
        
        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)
        
    def _get_cache_path(self, file_path):
        """获取缓存文件路径"""
        # 使用文件名作为缓存文件名
        base_name = os.path.basename(file_path)
        cache_name = base_name.replace('.pdf', '.grobid.xml')
        return os.path.join(self.cache_dir, cache_name)
        
    def _check_cache(self, cache_path):
        """检查缓存是否存在且有效"""
        return os.path.exists(cache_path) and os.path.getsize(cache_path) > 0
    
    def parse_document(self, file_path):
        """解析文档，如果存在缓存则直接返回缓存结果"""
        cache_path = self._get_cache_path(file_path)
        
        # 检查缓存
        if self.use_cache and self._check_cache(cache_path):
            print(f"Cache hit: Using cached XML for {os.path.basename(file_path)}")
            with open(cache_path, 'r', encoding='utf-8') as f:
                xml_text = f.read()
        else:
            print(f"Cache miss: Parsing {os.path.basename(file_path)}")
            # 解析文档
            self.parser.parse('text', file_path, self.cache_dir, 50)
            # 读取生成的XML
            with open(cache_path, 'r', encoding='utf-8') as f:
                xml_text = f.read()
                
        return xml_text

def pipeline(file_path):
    # 创建解析器实例
    grobid = CachedGrobidParser(cache_dir='./.tmp', use_cache=True)
    xml_text = grobid.parse_document(file_path)

    # 解析XML内容
    res = parse.parse_document_xml(xml_text)
    result = [res.header, res.abstract, res.body, res.citations]
    
    print(res.header)
    title = result[0].title
    abstract = result[1]
    
    print(title, abstract)
    if len(title.strip()) != '':
        title_text = "\n\n# {title}\n\n"
    else:
        title_text = ''
    
    if len(abstract.strip()) != '':
        abstract_text = f"## Abstract\n\n{abstract}\n\n"
    else:
        abstract_text = ''
    
    final_text = f"{title_text}{abstract_text}{result[2]}"

    return xml_text, final_text

if __name__ == "__main__":
    file_path = 'example_data/Zero-Shot Distillation for Image Encoders_ How to Make Effective Use of Synthetic Data.pdf'
    xml_res, final_text = pipeline(file_path)

    