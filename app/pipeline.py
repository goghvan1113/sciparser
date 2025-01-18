import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from retrievers.s2_paper import CachedSemanticScholarWrapper
from retrievers.pypaperbot_download import PaperDownloader
from retrievers.crossref_paper import CrossrefPaper
from retrievers.Publication import Document
from pdf_parser import Parser
from grobid_parser import parse
# from refparser import ReferenceParser


class ResearchDocument(Document):
    """研究论文文档类"""
    def __init__(self, title=None, doi=None):
        super().__init__(title, ref_type='title')
        self._doi = doi
        self._title = title
        self.citation_contexts = []  # 存储引用上下文
        self.reference_section = None  # 存储参考文献部分
        
    @property
    def title(self) -> str:
        return self._title
        
    @property
    def doi(self) -> str:
        return self._doi
        
class ResearchPipeline:
    def __init__(self, cache_dir=None):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tmp')
        self.pdf_dir = os.path.join(self.cache_dir, 'papers')
        self._ensure_directories()
        
    def _ensure_directories(self):
        """确保所需目录存在"""
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.pdf_dir, exist_ok=True)
    
    def process_paper(self, original_title):
        """处理论文的主要工作流"""
        try:
            # 1. 首先通过Crossref获取原始论文的DOI
            cr_paper = CrossrefPaper(ref_obj=original_title)
            paper_doi = cr_paper.doi
            
            # 如果Crossref未找到DOI，尝试使用S2Paper查找
            if not paper_doi:
                print("Crossref未找到DOI，尝试使用Semantic Scholar查找...")
                s2 = CachedSemanticScholarWrapper(timeout=3, use_cache=True)
                paper_doi = s2.get_doi_by_title(original_title)
                
            if not paper_doi:
                raise ValueError(f"无法找到论文的DOI: {original_title}")
            
            original_paper = ResearchDocument(title=original_title, doi=paper_doi)
            
            # 2. 使用S2Paper获取引用信息
            if not s2:  # 如果之前未创建s2实例
                s2 = CachedSemanticScholarWrapper(timeout=3, use_cache=True)
            citation_results = s2.get_paper_citations(original_paper.doi)
            
            # 3. 保存DOIs到文件
            safe_doi = original_paper.doi.replace('/', '_')
            doi_file = os.path.join(self.cache_dir, f"{safe_doi}_citing_DOIs.txt")
            s2.save_dois_to_file(doi_file)
            
            # 4. 下载PDF文件
            downloader = PaperDownloader(
                download_dir=self.pdf_dir,
                scholar_pages=1,
                scholar_results=1,
                use_doi_as_filename=True,
                python_path="/home/gaof23/miniconda3/envs/ca/bin/python"  # 指定Python解释器路径
            )
            download_log = downloader.download_by_doi_file(doi_file)
            
            # 5. 解析下载的PDF文件并提取引用上下文
            citing_papers = []
            grobid_parser = CachedGrobidParser(cache_dir=self.cache_dir)
            
            for doi in s2.citing_dois:
                safe_citing_doi = doi.replace('/', '_')
                pdf_path = os.path.join(self.pdf_dir, f"{safe_citing_doi}.pdf")
                
                if os.path.exists(pdf_path):
                    # 解析PDF得到XML
                    xml_text = grobid_parser.parse_document(pdf_path)
                    xml_path = os.path.join(self.cache_dir, f"{safe_citing_doi}.grobid.xml")
                    
                    # 使用ReferenceParser提取引用信息
                    parser = ReferenceParser(xml_path, None)
                    references = parser.parse_references()
                    
                    # 创建CitingPaper对象
                    citing_paper = ResearchDocument(doi=doi)
                    
                    # 查找引用原始论文的上下文
                    for ref_id, ref_data in references.items():
                        ref_title = ref_data['reference_details'].get('title', '')
                        if self._titles_match(ref_title, original_title):
                            citing_paper.citation_contexts.extend(ref_data['citations'])
                            citing_paper.reference_section = ref_data['reference_details']
                    
                    if citing_paper.citation_contexts:  # 只添加包含引用上下文的论文
                        citing_papers.append(citing_paper)
            
            return {
                'original_paper': original_paper,
                'citing_papers': citing_papers,
                'citation_results': citation_results,
                'doi_file': doi_file,
                'download_log': download_log
            }
            
        except Exception as e:
            raise Exception(f"处理论文时出错: {str(e)}")
    
    def _titles_match(self, title1, title2):
        """比较两个标题是否匹配（忽略大小写和空格）"""
        if not title1 or not title2:
            return False
        return title1.lower().replace(' ', '') == title2.lower().replace(' ', '')

    def process_paper_from_pdf(self, pdf_path):
        """从PDF文件处理论文的工作流"""
        try:
            # 1. 解析PDF得到XML
            grobid_parser = CachedGrobidParser(cache_dir=self.cache_dir)
            xml_text = grobid_parser.parse_document(pdf_path)

            # 2. 从XML中提取标题
            res = parse.parse_document_xml(xml_text)
            result = [res.header, res.abstract, res.body]
            title_elem = result[0].title
            if len(title_elem.strip()) == '':
                raise ValueError("无法从PDF中提取标题")
            
            original_title = title_elem.strip()
            print(f"从PDF中提取的标题: {original_title}")
            
            # 3. 通过Crossref获取DOI
            cr_paper = CrossrefPaper(ref_obj=original_title)
            paper_doi = cr_paper.doi
            
            # 如果Crossref未找到DOI，尝试使用S2Paper查找
            if not paper_doi:
                print("Crossref未找到DOI，尝试使用Semantic Scholar查找...")
                s2 = CachedSemanticScholarWrapper(timeout=3, use_cache=True)
                paper_doi = s2.get_doi_by_title(original_title)
            
            if not paper_doi:
                raise ValueError(f"无法找到论文的DOI，标题: {original_title}")
            
            # 4. 重命名PDF和XML文件
            safe_doi = paper_doi.replace('/', '_')
            new_pdf_path = os.path.join(self.pdf_dir, f"{safe_doi}.pdf")
            new_xml_path = os.path.join(self.cache_dir, f"{safe_doi}.grobid.xml")
            
            # 移动文件到新位置
            os.rename(pdf_path, new_pdf_path)
            current_xml_path = os.path.join(self.cache_dir, f"{os.path.basename(pdf_path).replace('.pdf', '')}.grobid.xml")
            os.rename(current_xml_path, new_xml_path)
            
            # 5. 使用现有pipeline处理论文
            return self.process_paper(original_title)
            
        except Exception as e:
            raise Exception(f"处理PDF文件时出错: {str(e)}")

class CachedGrobidParser:
    def __init__(self, cache_dir=None):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tmp')
        self.parser = Parser('grobid', host='127.0.0.1', port='8070')
        os.makedirs(cache_dir, exist_ok=True)
        
    def parse_document(self, pdf_path):
        """解析PDF文档并返回XML结果"""
        safe_name = os.path.basename(pdf_path).replace('.pdf', '')
        xml_path = os.path.join(self.cache_dir, f"{safe_name}.grobid.xml")
        
        if os.path.exists(xml_path) and os.path.getsize(xml_path) > 0:
            with open(xml_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        self.parser.parse('text', pdf_path, self.cache_dir, 50)
        with open(xml_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def parse_document_md(self, xml_text):
        # 这个函数是为了后面的Markdown转换
        res = parse.parse_document_xml(xml_text)
        result = [res.header, res.abstract, res.body]
        title = result[0].title
        abstract = result[1]

        if len(title.strip()) != '':
            title_text = f"\n\n# {title}\n\n"
        else:
            title_text = ''
        
        if len(abstract.strip()) != '':
            abstract_text = f"## Abstract\n\n{abstract}\n\n"
        else:
            abstract_text = ''
        
        final_text = f"{title_text}{abstract_text}{result[2]}"
        return final_text

def main():
    """测试主函数"""
    # 测试论文标题
    test_title = "Is synthetic data from diffusion models ready for knowledge distillation?"
    
    try:
        # 初始化pipeline
        pipeline = ResearchPipeline()
        
        print(f"开始处理论文: {test_title}")
        print("="*50)
        
        result = pipeline.process_paper_from_pdf("example_data/scientometrics.pdf")
        # 处理论文
        # result = pipeline.process_paper(test_title)
        
        # 打印结果
        print(f"原始论文:")
        print(f"标题: {result['original_paper'].title}")
        print(f"DOI: {result['original_paper'].doi}")
        print("-"*50)
        
        print(f"引用论文数量: {len(result['citing_papers'])}")
        print(f"DOI文件保存在: {result['doi_file']}")
        print("-"*50)
        
        # 打印每篇引用论文的引用上下文
        for i, paper in enumerate(result['citing_papers'], 1):
            print(f"\n引用论文 {i}:")
            print(f"DOI: {paper.doi}")
            print("\n引用上下文:")
            for j, context in enumerate(paper.citation_contexts, 1):
                print(f"\n上下文 {j}:")
                print(f"章节: {context['section']}")
                print(f"内容: {context['full_context']}")
            print("-"*50)
            
    except Exception as e:
        print(f"错误: {str(e)}")

if __name__ == "__main__":
    main()