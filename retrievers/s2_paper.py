from semanticscholar import SemanticScholar
from semanticscholar.PaginatedResults import PaginatedResults
from semanticscholar.Paper import Paper
from semanticscholar.Citation import Citation

import sqlite3
import json
import os

class CachedSemanticScholarWrapper:
    """SemanticScholar的缓存包装类"""
    
    def __init__(self, timeout=30, use_cache=True):
        self.sch = SemanticScholar(timeout=timeout)
        self.use_cache = use_cache
        self.last_request_cached = False  # 添加标记
        self._last_results = None  # 添加一个实例变量来存储最后的结果
        
        # 设置缓存数据库
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(base_dir, 'CACHE', 's2_citations.sqlite')
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            # 创建引用缓存表
            conn.execute('''CREATE TABLE IF NOT EXISTS citations
                          (paper_id TEXT PRIMARY KEY, 
                           data TEXT,
                           timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            # 创建标题-DOI缓存表
            conn.execute('''CREATE TABLE IF NOT EXISTS title_doi_cache
                          (title TEXT PRIMARY KEY,
                           doi TEXT,
                           timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
    def get_paper_citations(self, paper_id, fields=None, limit=100):
        """
        获取论文引用的包装方法，增加缓存功能
        
        Args:
            paper_id: 论文ID (DOI等)
            fields: 需要返回的字段列表
            limit: 返回结果数量限制
        """
        self.last_request_cached = False  # 重置标记
        
        if not self.use_cache:
            results = self.sch.get_paper_citations(paper_id, fields, limit)
            self._last_results = results  # 保存结果
            return results
            
        # 尝试从缓存获取
        cached_data = self._get_from_cache(paper_id)
        
        if cached_data is None:
            # 缓存未命中，调用原始方法并存储结果
            print(f"Cache miss for paper_id: {paper_id}")
            results = self.sch.get_paper_citations(paper_id)
            self._save_to_cache(paper_id, results)
            cached_data = results
        else:
            # 缓存命中
            self.last_request_cached = True
            print(f"Cache hit for paper_id: {paper_id}")
            
        # 处理fields过滤
        if fields is not None:
            cached_data = self._filter_fields(cached_data, fields)
            
        # 处理limit限制
        if limit is not None:
            cached_data = self._apply_limit(cached_data, limit)
        
        self._last_results = cached_data  # 保存结果
        return cached_data
        
    def _get_from_cache(self, paper_id):
        """从缓存中获取数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT data FROM citations WHERE paper_id = ?", 
                    (paper_id,)
                )
                result = cursor.fetchone()
                
                if result:
                    # 将JSON字符串转换回PaginatedResults对象
                    data = json.loads(result[0])
                    # 创建Citation对象，包装citingPaper数据
                    citations = []
                    for paper_data in data['items']:
                        # 创建包含citingPaper的数据结构
                        citation_data = {'citingPaper': paper_data}
                        citation = Citation(citation_data)
                        citations.append(citation)
                    
                    paginated_results = PaginatedResults(
                        requester=None,
                        data_type=Paper,
                        url="",
                        limit=len(citations)
                    )
                    # 直接设置私有属性
                    paginated_results._items = citations
                    paginated_results._next = data.get('next')
                    paginated_results._offset = data.get('offset')
                    paginated_results._total = data.get('total')
                    return paginated_results
                return None
        except Exception as e:
            print(f"Error reading from cache: {str(e)}")
            return None
            
    def _save_to_cache(self, paper_id, results):
        """保存数据到缓存，只保存 citingPaper 字段"""
        try:
            # 将PaginatedResults对象转换为可序列化的字典
            # Citation对象中的论文数据通过paper属性访问
            data = {
                'items': [citation.paper.raw_data for citation in results._items],  # 使用paper.raw_data获取原始数据
                'next': results.next,
                'offset': results.offset,
                'total': results.total
            }
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO citations (paper_id, data) VALUES (?, ?)",
                    (paper_id, json.dumps(data))
                )
                print(f"Successfully cached data for paper_id: {paper_id}")
        except Exception as e:
            print(f"Error saving to cache: {str(e)}")
            print(f"Citation data structure: {dir(results._items[0])}")  # 打印Citation对象的属性，帮助调试
            
    def _filter_fields(self, results, fields):
        """根据指定的fields过滤数据"""
        if not fields:
            return results
            
        # 创建新的Paper对象，只包含指定的字段
        filtered_papers = []
        for citation in results._items:
            filtered_data = {field: citation.paper.raw_data.get(field) for field in fields}
            # 创建包含citingPaper的数据结构
            citation_data = {'citingPaper': filtered_data}
            filtered_papers.append(Citation(citation_data))
            
        # 返回新的PaginatedResults对象
        paginated_results = PaginatedResults(
            requester=None,
            data_type=Paper,
            url="",
            limit=len(filtered_papers)
        )
        paginated_results._items = filtered_papers
        paginated_results._next = results.next
        paginated_results._offset = results.offset
        paginated_results._total = results.total
        return paginated_results
        
    def _apply_limit(self, results, limit):
        """应用limit限制"""
        paginated_results = PaginatedResults(
            requester=None,
            data_type=Paper,
            url="",
            limit=limit
        )
        paginated_results._items = results._items[:limit]  # 使用_items而不是data
        paginated_results._next = results.next
        paginated_results._offset = results.offset
        paginated_results._total = results.total
        return paginated_results

    def __getattr__(self, name):
        """将未实现的方法转发到原始SemanticScholar实例"""
        return getattr(self.sch, name)

    def was_last_request_cached(self):
        """返回上次请求是否使用了缓存"""
        return self.last_request_cached

    @property
    def citing_titles(self):
        """获取引用论文的标题列表"""
        if not self._last_results:
            return []
        return [citation['citingPaper'].get('title', '') 
                for citation in self._last_results.items 
                if citation['citingPaper'].get('title')]

    @property
    def citing_dois(self):
        """获取引用论文的DOI列表"""
        if not self._last_results:
            return []
        
        dois = []
        for citation in self._last_results.items:
            external_ids = citation['citingPaper'].get('externalIds', {})
            
            # 首先尝试获取DOI
            doi = external_ids.get('DOI')
            if doi and doi.strip():
                dois.append(doi)
                continue
            
            # 如果没有DOI但有arXiv ID，构建arXiv DOI
            arxiv_id = external_ids.get('ArXiv')
            if arxiv_id and arxiv_id.strip():
                arxiv_doi = f"10.48550/arXiv.{arxiv_id}"
                dois.append(arxiv_doi)
            
        return dois

    def save_dois_to_file(self, file_path: str = "s2_citing_dois.txt"):
        """将DOI列表保存到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for doi in self.citing_dois:
                    f.write(f"{doi}\n")
            return f"Successfully saved {len(self.citing_dois)} DOIs to {file_path}"
        except Exception as e:
            return f"Error saving DOIs to file: {str(e)}"

    def get_doi_by_title(self, title: str) -> str:
        """通过论文标题查询DOI（带缓存）
        
        Args:
            title: 论文标题
            
        Returns:
            str: 论文的DOI，如果未找到返回None
        """
        self.last_request_cached = False
        
        if self.use_cache:
            # 尝试从缓存获取
            cached_doi = self._get_doi_from_cache(title)
            if cached_doi is not None:
                self.last_request_cached = True
                print(f"Cache hit for title: {title}")
                return cached_doi
                
        try:
            # 使用search_paper搜索论文
            results = self.sch.search_paper(title, fields=['title', 'externalIds'])
            
            # 检查是否有结果
            if not results or not results.items:
                if self.use_cache:
                    self._save_doi_to_cache(title, None)  # 缓存未找到的结果
                return None
                
            # 获取第一个结果
            first_paper = results.items[0]
            
            # 检查标题是否匹配（忽略大小写和空格）
            if self._normalize_title(first_paper.title) == self._normalize_title(title):
                # 从externalIds中获取DOI
                doi = None
                if hasattr(first_paper, 'externalIds') and first_paper.externalIds.get('DOI'):
                    doi = first_paper.externalIds['DOI']
                
                # 保存到缓存
                if self.use_cache:
                    self._save_doi_to_cache(title, doi)
                    
                return doi
                    
            if self.use_cache:
                self._save_doi_to_cache(title, None)  # 缓存未找到的结果
            return None
            
        except Exception as e:
            print(f"通过标题查询DOI时出错: {str(e)}")
            return None
            
    def _get_doi_from_cache(self, title: str) -> str:
        """从缓存中获取DOI"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT doi FROM title_doi_cache WHERE title = ?",
                    (self._normalize_title(title),)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            print(f"从缓存读取DOI时出错: {str(e)}")
            return None
            
    def _save_doi_to_cache(self, title: str, doi: str):
        """保存DOI到缓存"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO title_doi_cache (title, doi) VALUES (?, ?)",
                    (self._normalize_title(title), doi)
                )
                print(f"Successfully cached DOI for title: {title}")
        except Exception as e:
            print(f"保存DOI到缓存时出错: {str(e)}")

    def _normalize_title(self, title: str) -> str:
        """标准化标题以进行比较（移除空格和转换为小写）"""
        if not title:
            return ""
        return title.lower().replace(' ', '')


# 使用示例
if __name__ == "__main__":
    # 创建带缓存的包装器实例
    sch = CachedSemanticScholarWrapper(timeout=3, use_cache=True)
    
    # 测试标题
    test_titles = [
        "Is synthetic data from diffusion models ready for knowledge distillation?",
        "Exploring graph pre-training for aspect-based sentiment analysis"
    ]
    
    print("="*50)
    print("测试通过标题获取DOI:")
    print("="*50)
    
    for title in test_titles:
        print(f"\n查询标题: {title}")
        # 第一次查询
        doi = sch.get_doi_by_title(title)
        print(f"DOI: {doi}")
        print(f"是否使用缓存: {sch.was_last_request_cached()}")
        
        # 第二次查询（应该使用缓存）
        print("\n再次查询相同标题:")
        doi = sch.get_doi_by_title(title)
        print(f"DOI: {doi}")
        print(f"是否使用缓存: {sch.was_last_request_cached()}")
        print("-"*50)
    
    print("\n"+"="*50)
    print("测试获取引用信息:")
    print("="*50)
    
    # 使用找到的DOI测试引用查询
    paper_id = '10.48550/arXiv.2305.12954'
    print(f"\n查询论文DOI: {paper_id}")
    results = sch.get_paper_citations(paper_id, fields=['title','externalIds'])
    
    # 检查是否使用了缓存
    print(f"是否使用缓存: {sch.was_last_request_cached()}")
    
    # 打印引用信息
    print("\n引用论文列表:")
    for i, item in enumerate(results.items, 1):
        paper = item['citingPaper']
        print(f"\n{i}. 标题: {paper['title']}")
        if 'DOI' in paper['externalIds']:
            print(f"   DOI: {paper['externalIds']['DOI']}")
    
    # 保存DOIs到文件
    doi_file = "test_citing_papers.txt"
    save_result = sch.save_dois_to_file(doi_file)
    print(f"\n{save_result}")
