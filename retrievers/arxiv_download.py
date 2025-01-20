import subprocess
import os
import logging
from typing import List, Union

class ArxivDownloader:
    """arXiv论文下载器类"""
    
    def __init__(self, download_dir: str = "./downloaded_papers"):
        """
        初始化下载器
        
        Args:
            download_dir: 下载目录
        """
        self.download_dir = os.path.expanduser(download_dir)
        
        # 设置日志
        self._setup_logging()
        
        # 确保下载目录存在
        os.makedirs(self.download_dir, exist_ok=True)
        
    def _setup_logging(self):
        """配置日志"""
        log_file = os.path.join(self.download_dir, 'arxiv_download.log')
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def _extract_arxiv_id(self, doi: str) -> str:
        """从arXiv DOI中提取arXiv ID
        
        Args:
            doi: arXiv DOI (格式: 10.48550/arXiv.XXXX.XXXXX)
            
        Returns:
            str: arXiv ID
        """
        return doi.split('arXiv.')[-1]
    
    def download_by_doi(self, dois: Union[str, List[str]]) -> str:
        """通过DOI下载arXiv论文
        
        Args:
            dois: 单个DOI或DOI列表
            
        Returns:
            str: 下载日志
        """
        if isinstance(dois, str):
            dois = [dois]
            
        log_messages = []
        for doi in dois:
            try:
                # 从DOI中提取arXiv ID
                arxiv_id = self._extract_arxiv_id(doi)
                
                # 构建下载命令
                cmd = f'arxiv-downloader {arxiv_id} -d "{self.download_dir}"'
                
                # 执行下载
                result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
                
                # 重命名文件为safe_doi格式
                safe_doi = doi.replace('/', '_')
                # 查找下载的文件（arxiv-downloader下载的文件格式）
                for filename in os.listdir(self.download_dir):
                    if filename.startswith(arxiv_id) and filename.endswith('.pdf'):
                        old_name = os.path.join(self.download_dir, filename)
                        new_name = os.path.join(self.download_dir, f"{safe_doi}.pdf")
                        os.rename(old_name, new_name)
                        log_messages.append(f'Successfully downloaded and renamed arXiv paper: {doi}')
                        self.logger.info(f'Successfully downloaded arXiv paper: {doi}')
                        break
                else:
                    log_messages.append(f'Download completed but file not found for: {doi}')
                    
            except subprocess.CalledProcessError as e:
                error_msg = f'Failed to download arXiv paper: {doi}. Error: {e.stderr}'
                log_messages.append(error_msg)
                self.logger.error(error_msg)
                
        return '\n'.join(log_messages)
