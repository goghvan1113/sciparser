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
        
        # 设置缓存数据库
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(base_dir, 'CACHE', 's2_citations.sqlite')
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS citations
                          (paper_id TEXT PRIMARY KEY, 
                           data TEXT,
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
            return self.sch.get_paper_citations(paper_id, fields, limit)
            
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


# 使用示例
if __name__ == "__main__":
    # 创建带缓存的包装器实例
    sch = CachedSemanticScholarWrapper(timeout=3, use_cache=True)
    
    # 获取引用信息
    paper_id = '10.18653/v1/2023.findings-emnlp.234'
    results = sch.get_paper_citations(paper_id, fields=['title','externalIds'])
    
    # 检查是否使用了缓存
    if sch.was_last_request_cached():
        print(f"Results for {paper_id} were retrieved from cache")
    else:
        print(f"Results for {paper_id} were fetched from API")
        
    for item in results:
        print(item['citingPaper']['title'], item['citingPaper']['externalIds']['DOI'])
