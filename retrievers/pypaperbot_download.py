# PyPaperBot Downloader
import subprocess
import os
import logging
from datetime import datetime
from typing import List, Optional, Union
from pathlib import Path

class PaperDownloader:
    """论文下载器类"""
    
    def __init__(self, download_dir: str = "./downloaded_papers",
                 min_year: Optional[int] = None,
                 scholar_pages: int = 1,
                 scholar_results: int = 1,
                 scihub_mirror: Optional[str] = None,
                 use_doi_as_filename: bool = True,
                 python_path: Optional[str] = None):
        """
        初始化下载器
        
        Args:
            download_dir: 下载目录
            min_year: 最小发表年份
            scholar_pages: Google Scholar搜索页数
            scholar_results: 每页结果数
            scihub_mirror: Sci-Hub镜像地址
            use_doi_as_filename: 是否使用DOI作为文件名
            python_path: Python解释器路径，如果为None则使用系统默认的python
        """
        self.download_dir = os.path.expanduser(download_dir)
        self.min_year = min_year
        self.scholar_pages = scholar_pages
        self.scholar_results = scholar_results
        self.scihub_mirror = scihub_mirror
        self.use_doi_as_filename = use_doi_as_filename
        self.python_path = python_path or 'python'  # 如果未指定则使用系统默认的python
        
        # 设置日志
        self._setup_logging()
        
        # 确保下载目录存在
        os.makedirs(self.download_dir, exist_ok=True)
        
    def _setup_logging(self):
        """配置日志"""
        log_file = os.path.join(self.download_dir, 'download.log')
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def _build_command(self, download_type: str, value: str) -> str:
        """
        构建下载命令
        
        Args:
            download_type: 下载类型 ('query', 'doi', 'doi_file')
            value: 对应的值
        
        Returns:
            构建好的命令字符串
        """
        # 使用指定的Python解释器路径
        cmd = [f'"{self.python_path}" -m PyPaperBot']
        
        # 添加主要参数
        if download_type == 'query':
            cmd.append(f'--query="{value}"')
        elif download_type == 'doi':
            cmd.append(f'--doi="{value}"')
        elif download_type == 'doi_file':
            cmd.append(f'--doi-file="{value}"')
        
        # 添加通用参数
        cmd.append(f'--dwn-dir="{self.download_dir}"')
        
        if download_type == 'query':
            cmd.append(f'--scholar-pages={self.scholar_pages}')
            cmd.append(f'--scholar-results={self.scholar_results}')
            
        if self.min_year:
            cmd.append(f'--min-year={self.min_year}')
            
        if self.scihub_mirror:
            cmd.append(f'--scihub-mirror="{self.scihub_mirror}"')
            
        if self.use_doi_as_filename:
            cmd.append('--use-doi-as-filename')
            
        return ' '.join(cmd)
    
    def download_by_query(self, queries: Union[str, List[str]]) -> str:
        """
        通过查询词下载论文
        
        Args:
            queries: 单个查询词或查询词列表
        
        Returns:
            下载日志
        """
        if isinstance(queries, str):
            queries = [queries]
            
        log_messages = []
        for query in queries:
            try:
                cmd = self._build_command('query', query)
                result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
                log_messages.append(f'Successfully processed query: "{query}"')
                self.logger.info(f'Successfully downloaded paper for query: {query}')
            except subprocess.CalledProcessError as e:
                error_msg = f'Failed to process query: "{query}". Error: {e.stderr}'
                log_messages.append(error_msg)
                self.logger.error(error_msg)
                
        return '\n'.join(log_messages)
    
    def download_by_doi(self, dois: Union[str, List[str]]) -> str:
        """
        通过DOI下载论文
        
        Args:
            dois: 单个DOI或DOI列表
        
        Returns:
            下载日志
        """
        if isinstance(dois, str):
            dois = [dois]
            
        log_messages = []
        for doi in dois:
            try:
                cmd = self._build_command('doi', doi)
                result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
                
                # 重命名文件，将%替换为_
                old_name = os.path.join(self.download_dir, f"{doi.replace('/', '_')}.pdf")
                new_name = os.path.join(self.download_dir, f"{doi.replace('/', '_').replace('%', '_')}.pdf")
                if os.path.exists(old_name) and '%' in old_name:
                    os.rename(old_name, new_name)
                    
                log_messages.append(f'Successfully processed DOI: "{doi}"')
                self.logger.info(f'Successfully downloaded paper for DOI: {doi}')
            except subprocess.CalledProcessError as e:
                error_msg = f'Failed to process DOI: "{doi}". Error: {e.stderr}'
                log_messages.append(error_msg)
                self.logger.error(error_msg)
                
        return '\n'.join(log_messages)
    
    def download_by_doi_file(self, file_path: str) -> str:
        """
        通过DOI文件下载论文
        
        Args:
            file_path: DOI文件路径
        
        Returns:
            下载日志
        """
        try:
            cmd = self._build_command('doi_file', file_path)
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            
            # 读取DOI文件并重命名包含%的文件
            with open(file_path, 'r') as f:
                dois = [line.strip() for line in f if line.strip()]
                
            for doi in dois:
                old_name = os.path.join(self.download_dir, f"{doi.replace('/', '_')}.pdf")
                new_name = os.path.join(self.download_dir, f"{doi.replace('/', '_').replace('%', '_')}.pdf")
                if os.path.exists(old_name) and '%' in old_name:
                    os.rename(old_name, new_name)
            
            log_msg = f'Successfully processed DOI file: "{file_path}"'
            self.logger.info(log_msg)
            return log_msg
        except subprocess.CalledProcessError as e:
            error_msg = f'Failed to process DOI file: "{file_path}". Error: {e.stderr}'
            self.logger.error(error_msg)
            return error_msg


if __name__ == "__main__":
    # 使用示例
    downloader = PaperDownloader(
        download_dir="tmp/papers",
        scholar_pages=1,
        scholar_results=1,
        use_doi_as_filename=True,
        python_path="/path/to/your/python"  # 指定Python解释器路径
    )
    
    # 1. 通过查询下载
    log = downloader.download_by_query("Attention is all you need")
    print(log)
    
    # # 2. 通过DOI下载
    # log = downloader.download_by_doi("10.1038/nature14539")
    # print(log)
    
    # # 3. 通过DOI文件下载
    # log = downloader.download_by_doi_file("dois.txt")
    # print(log)