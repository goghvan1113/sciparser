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
from app.refparser import ReferenceParser
from retrievers.arxiv_download import ArxivDownloader


class ResearchDocument(Document):
    """研究论文文档类"""
    def __init__(self, title=None, doi=None):
        super().__init__(title, ref_type='title')
        self._doi = doi
        self._title = title
        self.citation_contexts = []  # 存储引用上下文
        self.reference_section = []  # 存储参考文献部分
        
    @property
    def title(self) -> str:
        return self._title
        
    @property
    def doi(self) -> str:
        return self._doi
        
class ResearchPipeline:
    def __init__(self, cache_dir=None):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tmp')
        self.xml_dir = os.path.join(self.cache_dir, 'xmls')
        self.pdf_dir = os.path.join(self.cache_dir, 'papers')
        self.doi_dir = os.path.join(self.cache_dir, 'citing_dois')
        self._ensure_directories()
        
    def _ensure_directories(self):
        """确保所需目录存在"""
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.pdf_dir, exist_ok=True)
        os.makedirs(self.xml_dir, exist_ok=True)
        os.makedirs(self.doi_dir, exist_ok=True)
    
    def get_doi_by_title(self, title: str) -> str:
        """通过标题获取DOI
        
        Args:
            title: 论文标题
            
        Returns:
            str: 论文DOI，如果未找到返回None
        """
        # 1. 首先通过Crossref获取DOI
        cr_paper = CrossrefPaper(ref_obj=title)
        paper_doi = cr_paper.doi
        
        # 2. 如果Crossref未找到，尝试使用S2Paper
        if not paper_doi:
            print("Crossref未找到DOI, 尝试使用Semantic Scholar查找...")
            s2 = CachedSemanticScholarWrapper(timeout=3, use_cache=True)
            paper_doi, _ = s2.get_doi_by_title(title)  # 只获取DOI，忽略paper_id
        
        return paper_doi

    def get_citations_and_save(self, paper_doi: str) -> tuple:
        """获取引用信息并保存DOI
        
        Args:
            paper_doi: 论文DOI
            
        Returns:
            tuple: (citing_titles, citing_dois, citing_paperIds, doi_file, no_doi_indices)
        """
        # 1. 获取引用信息
        s2 = CachedSemanticScholarWrapper(timeout=3, use_cache=True)
        citation_results = s2.get_paper_citations(paper_doi)
        
        # 2. 获取引用论文信息
        citing_titles = s2.citing_titles
        citing_dois = s2.citing_dois
        citing_paperIds = s2.citing_paperIds
        no_doi_indices = s2.no_doi_indices  # 获取没有DOI的文献索引
        
        # 3. 保存DOIs到文件
        safe_doi = paper_doi.replace('/', '_')
        doi_file = os.path.join(self.doi_dir, f"{safe_doi}.txt")
        s2.save_dois_to_file(doi_file)
        
        return citing_titles, citing_dois, citing_paperIds, doi_file, no_doi_indices, citation_results

    def download_papers(self, titles, doi_file, no_doi_indices) -> str:
        """下载论文PDF
        
        Args:
            titles: 论文标题列表
            doi_file: DOI文件路径
            no_doi_indices: 没有DOI的文献索引列表
            
        Returns:
            str: 下载日志
        """
        print("开始下载论文...")
        downloader = PaperDownloader(
            download_dir=self.pdf_dir,
            scholar_pages=1,
            scholar_results=1,
            use_doi_as_filename=True,
            python_path="/home/gaof23/miniconda3/envs/ca/bin/python"
        )
        
        arxiv_downloader = ArxivDownloader(download_dir=self.pdf_dir)
        
        log = ""
        
        # 读取DOI文件获取DOI列表
        with open(doi_file, 'r') as f:
            dois = [line.strip() for line in f if line.strip()]
        
        # 分离arXiv DOIs和普通DOIs
        arxiv_dois = []
        other_dois = []
        for doi in dois:
            if doi.startswith('10.48550/arXiv.'):
                arxiv_dois.append(doi)
            else:
                other_dois.append(doi)
        
        # 1. 首先处理arXiv论文
        if arxiv_dois:
            print(f"\n处理{len(arxiv_dois)}篇arXiv论文...")
            for doi in arxiv_dois:
                safe_doi = doi.replace('/', '_').replace('%2F', '_')
                pdf_path = os.path.join(self.pdf_dir, f"{safe_doi}.pdf")
                xml_path = os.path.join(self.xml_dir, f"{safe_doi}.grobid.xml")
                
                # 检查是否已有缓存
                if os.path.exists(pdf_path) or os.path.exists(xml_path):
                    print(f"文献已存在缓存: {safe_doi}")
                    log += f"\n文献已存在缓存: {safe_doi}"
                    continue
                
                # 如果没有缓存，使用arXiv下载器下载
                print(f"下载arXiv论文: {safe_doi}")
                download_log = arxiv_downloader.download_by_doi(doi)
                log += f"\n{download_log}"
        
        # 2. 然后处理其他DOI论文
        if other_dois:
            print(f"\n处理{len(other_dois)}篇非arXiv论文...")
            # 创建临时DOI文件
            temp_doi_file = os.path.join(self.doi_dir, "temp_dois.txt")
            with open(temp_doi_file, 'w') as f:
                for doi in other_dois:
                    f.write(f"{doi}\n")
            
            # 使用PyPaperBot下载
            for doi in other_dois:
                safe_doi = doi.replace('/', '_').replace('%2F', '_')
                pdf_path = os.path.join(self.pdf_dir, f"{safe_doi}.pdf")
                xml_path = os.path.join(self.xml_dir, f"{safe_doi}.grobid.xml")
                
                # 检查是否已有缓存
                if os.path.exists(pdf_path) or os.path.exists(xml_path):
                    print(f"文献已存在缓存: {safe_doi}")
                    log += f"\n文献已存在缓存: {safe_doi}"
                    continue
                
                # 如果没有缓存，下载文献
                print(f"下载文献: {safe_doi}")
                download_log = downloader.download_by_doi(doi)
                log += f"\n{download_log}"
                
                # 重命名文件（如果下载成功）
                old_name = os.path.join(self.pdf_dir, f"{doi.replace('/', '_')}.pdf")
                if os.path.exists(old_name) and '%' in old_name:
                    new_name = os.path.join(self.pdf_dir, f"{safe_doi}.pdf")
                    os.rename(old_name, new_name)
                    print(f"文件重命名: {safe_doi}")
            
            # 删除临时DOI文件
            if os.path.exists(temp_doi_file):
                os.remove(temp_doi_file)
        
        # # 3. 最后处理没有DOI的文献
        # no_doi_titles = [titles[i] for i in no_doi_indices]
        # if no_doi_titles:
        #     print(f"\n处理{len(no_doi_titles)}篇无DOI的文献...")
        #     for title in no_doi_titles:
        #         safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        #         pdf_path = os.path.join(self.pdf_dir, f"{safe_title}.pdf")
        #         xml_path = os.path.join(self.xml_dir, f"{safe_title}.grobid.xml")
                
        #         # 检查是否已有缓存
        #         if os.path.exists(pdf_path) and os.path.exists(xml_path):
        #             print(f"文献已存在缓存: {safe_title}")
        #             log += f"\n文献已存在缓存: {safe_title}"
        #             continue
                
        #         # 如果没有缓存，下载文献
        #         print(f"下载文献: {title}")
        #         download_log = downloader.download_by_query(title)
        #         log += f"\n{download_log}"
                
        #         # 重命名文件（如果下载成功）
        #         old_name = os.path.join(self.pdf_dir, f"{title}.pdf")
        #         if os.path.exists(old_name):
        #             new_name = os.path.join(self.pdf_dir, f"{safe_title}.pdf")
        #             os.rename(old_name, new_name)
        #             print(f"文件重命名: {safe_title}")
        
        # print("\n下载完成!")
        return log

    def parse_and_extract_citations(self, original_title: str, citing_dois: list) -> list:
        """解析PDF并提取引用上下文
        
        Args:
            original_title: 原始论文标题
            citing_dois: 引用论文的DOI列表
            
        Returns:
            list: 包含引用上下文的CitingPaper对象列表
        """
        print("下载完成，开始解析引用论文")
        citing_papers = []
        grobid_parser = CachedGrobidParser(cache_dir=self.cache_dir)
        
        for doi in citing_dois:
            safe_citing_doi = doi.replace('/', '_')
            pdf_path = os.path.join(self.pdf_dir, f"{safe_citing_doi}.pdf")
            
            if os.path.exists(pdf_path):
                # 解析PDF得到XML
                xml_text = grobid_parser.parse_document(pdf_path)
                xml_path = os.path.join(self.xml_dir, f"{safe_citing_doi}.grobid.xml")
                
                # 提取引用信息
                parser = ReferenceParser(xml_path, None)
                references = parser.parse_references()
                
                # 创建CitingPaper对象
                citing_paper = ResearchDocument(doi=doi)
                
                # 查找引用原始论文的上下文
                for ref_id, ref_data in references.items():
                    ref_title = ref_data['reference_details'].get('title', '')
                    if self._titles_match(ref_title, original_title):
                        citing_paper.citation_contexts.extend(ref_data['citations'])

                if citing_paper.citation_contexts:
                    citing_papers.append(citing_paper)
                    
        return citing_papers, grobid_parser

    def process_paper(self, original_title):
        """处理论文的主要工作流
        
        Args:
            original_title: 论文标题
            
        Returns:
            dict: 包含处理结果的字典
        """
        try:
            print("\n" + "="*50)
            print(f"开始处理论文: {original_title}")
            print("="*50 + "\n")
            
            # 1. 获取DOI
            print("1. 获取论文DOI...")
            cr_paper = CrossrefPaper(ref_obj=original_title)
            paper_doi = cr_paper.doi
            s2 = CachedSemanticScholarWrapper(timeout=3, use_cache=True)
            
            if not paper_doi:
                print("Crossref未找到DOI, 尝试使用Semantic Scholar查找...")
                paper_doi, _ = s2.get_doi_by_title(original_title)
                
            if not paper_doi:
                raise ValueError(f"无法找到论文的DOI: {original_title}")
            
            print(f"找到论文DOI: {paper_doi}")
            original_paper = ResearchDocument(title=original_title, doi=paper_doi)
            
            # 2. 获取引用信息
            print("\n2. 获取引用信息...")
            citing_titles, citing_dois, citing_paperIds, doi_file, no_doi_indices, citation_results = self.get_citations_and_save(paper_doi)
            print(f"找到{len(citing_titles)}篇引用论文")
            
            # 3. 下载PDF文件
            print("\n3. 下载引用论文PDF...")
            download_log = self.download_papers(citing_titles, doi_file, no_doi_indices)
            print(download_log)
            
            # 4. 解析PDF并提取引用上下文
            print("\n4. 解析PDF并提取引用上下文...")
            citing_papers, grobid_parser = self.parse_and_extract_citations(
                original_title, 
                citing_dois
            )
            print(f"成功提取{len(citing_papers)}篇论文的引用上下文")
            
            print("\n" + "="*50)
            print("处理完成!")
            print("="*50 + "\n")
            
            return {
                'original_paper': original_paper,
                'citing_papers': citing_papers,
                'citation_results': citation_results,
                'citation_dois': citing_dois,
                'citing_titles': citing_titles,
                'citing_paperIds': citing_paperIds,
                'doi_file': doi_file,
                'download_log': download_log,
                'crossref_paper': cr_paper,
                's2_wrapper': s2,
                'grobid_parser': grobid_parser
            }
            
        except Exception as e:
            print(f"\n处理论文时出错: {str(e)}")
            raise Exception(f"处理论文时出错: {str(e)}")

    def process_paper_from_pdf(self, pdf_path: str) -> dict:
        """从PDF文件处理论文
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            dict: 包含处理结果的字典
        """
        try:
            print("\n" + "="*50)
            print(f"开始处理PDF文件: {pdf_path}")
            print("="*50 + "\n")
            
            # 1. 解析PDF得到XML和标题
            print("1. 解析PDF获取标题...")
            grobid_parser = CachedGrobidParser(cache_dir=self.cache_dir)
            xml_text = grobid_parser.parse_document(pdf_path)
            
            res = parse.parse_document_xml(xml_text)
            title_elem = res.header.title
            if not title_elem.strip():
                raise ValueError("无法从PDF中提取标题")
            
            original_title = title_elem.strip()
            print(f"从PDF中提取的标题: {original_title}")
            
            # 2. 获取DOI并重命名文件
            print("\n2. 获取论文DOI...")
            cr_paper = CrossrefPaper(ref_obj=original_title)
            paper_doi = cr_paper.doi
            s2 = CachedSemanticScholarWrapper(timeout=3, use_cache=True)
            
            if not paper_doi:
                print("Crossref未找到DOI, 尝试使用Semantic Scholar查找...")
                paper_doi, _ = s2.get_doi_by_title(original_title)
                
            if not paper_doi:
                raise ValueError(f"无法找到论文的DOI: {original_title}")
            
            print(f"找到论文DOI: {paper_doi}")
            
            # 3. 复制并重命名PDF和XML文件
            print("\n3. 重命名文件...")
            safe_doi = paper_doi.replace('/', '_')
            new_pdf_path = os.path.join(self.pdf_dir, f"{safe_doi}.pdf")
            new_xml_path = os.path.join(self.xml_dir, f"{safe_doi}.grobid.xml")
            
            # 如果是上传的文件，先复制到papers目录
            if not pdf_path.startswith(self.pdf_dir):
                import shutil
                shutil.copy2(pdf_path, new_pdf_path)
                print(f"PDF文件已复制到: {new_pdf_path}")
            elif pdf_path != new_pdf_path:  # 如果已在papers目录但名字不同
                os.rename(pdf_path, new_pdf_path)
                print(f"PDF文件已重命名为: {new_pdf_path}")
            
            # 重命名XML文件
            current_xml_path = os.path.join(self.xml_dir, 
                f"{os.path.basename(pdf_path).replace('.pdf', '')}.grobid.xml")
            if os.path.exists(current_xml_path) and current_xml_path != new_xml_path:
                os.rename(current_xml_path, new_xml_path)
                print("XML文件重命名完成")
            
            original_paper = ResearchDocument(title=original_title, doi=paper_doi)
            
            # 4. 获取引用信息
            print("\n4. 获取引用信息...")
            citing_titles, citing_dois, citing_paperIds, doi_file, no_doi_indices, citation_results = self.get_citations_and_save(paper_doi)
            print(f"找到{len(citing_dois)}篇引用论文")
            
            # 5. 下载PDF文件
            print("\n5. 下载引用论文PDF...")
            download_log = self.download_papers(citing_titles, doi_file, no_doi_indices)
            
            # 6. 解析PDF并提取引用上下文
            print("\n6. 解析PDF并提取引用上下文...")
            citing_papers, grobid_parser = self.parse_and_extract_citations(
                original_title, 
                citing_dois
            )
            print(f"成功提取{len(citing_papers)}篇论文的引用上下文")
            
            print("\n" + "="*50)
            print("处理完成!")
            print("="*50 + "\n")
            
            return {
                'original_paper': original_paper,
                'citing_papers': citing_papers,
                'citation_results': citation_results,
                'citation_dois': citing_dois,
                'citing_titles': citing_titles,
                'citing_paperIds': citing_paperIds,
                'doi_file': doi_file,
                'download_log': download_log,
                'crossref_paper': cr_paper,
                's2_wrapper': s2,
                'grobid_parser': grobid_parser
            }
            
        except Exception as e:
            print(f"\n处理PDF文件时出错: {str(e)}")
            raise Exception(f"处理PDF文件时出错: {str(e)}")

    def _titles_match(self, title1, title2):
        """比较两个标题是否匹配（忽略大小写和空格）"""
        if not title1 or not title2:
            return False
        return title1.lower().replace(' ', '') == title2.lower().replace(' ', '')

class CachedGrobidParser:
    def __init__(self, cache_dir=None):
        """初始化Grobid解析器
        
        Args:
            cache_dir: 缓存根目录,默认为项目根目录下的tmp
        """
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tmp')
        self.xml_dir = os.path.join(self.cache_dir, 'xmls')  # XML文件存储目录
        self.parser = Parser('grobid', host='127.0.0.1', port='8070')
        
        # 确保目录存在
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.xml_dir, exist_ok=True)
        
        self.last_request_cached = False
        
    def parse_document(self, pdf_path):
        """解析PDF文档并返回XML结果"""
        safe_name = os.path.basename(pdf_path).replace('.pdf', '')
        xml_path = os.path.join(self.xml_dir, f"{safe_name}.grobid.xml")
        
        if os.path.exists(xml_path) and os.path.getsize(xml_path) > 0:
            self.last_request_cached = True
            print(f"GROBID解析使用缓存: {safe_name}")
            with open(xml_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        self.last_request_cached = False
        print(f"GROBID解析发送请求: {safe_name}")
        # 直接将XML保存到xml_dir
        self.parser.parse('text', pdf_path, self.xml_dir, 50)
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
    test_title = "Graph Meets LLMs: Towards Large Graph Models"
    
    try:
        # 初始化pipeline
        pipeline = ResearchPipeline()
        
        print(f"开始处理论文: {test_title}")
        print("="*50)
        
        result = pipeline.process_paper_from_pdf("tmp/papers/10.48550_arXiv.2308.14522.pdf")
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