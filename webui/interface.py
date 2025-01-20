import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

import gradio as gr
import base64
from app.pipeline import ResearchPipeline, CachedGrobidParser
from app.refparser import ReferenceParser
from grobid_parser import parse
from retrievers.crossref_paper import CrossrefPaper
from retrievers.s2_paper import CachedSemanticScholarWrapper
from retrievers.pypaperbot_download import PaperDownloader
import markdown

class RefParserUI:
    def __init__(self):
        self.title = "引文分析工具"
        self.pipeline = ResearchPipeline()
    
    def view_pdf(self, pdf_file):
        """显示PDF文件"""
        with open(pdf_file.name,'rb') as f:
            pdf_data = f.read()
        b64_data = base64.b64encode(pdf_data).decode()
        return f"<embed src='data:application/pdf;base64,{b64_data}' type='application/pdf' width='100%' height='700px' />"

    def _generate_references_html(self, references):
        """生成参考文献HTML"""
        ref_html = "<div style='max-height: 775px; overflow-y: auto;'>"
        for ref_id, ref_data in references.items():
            ref_html += f"<h3>Reference {ref_id}</h3>"
            details = ref_data['reference_details']
            ref_html += "<div style='margin-left: 20px;'>"
            ref_html += f"<p><b>Authors:</b> {', '.join(details['authors'])}</p>"
            ref_html += f"<p><b>Title:</b> {details['title']}</p>"
            ref_html += f"<p><b>Year:</b> {details['year']}</p>"
            
            if ref_data['citations']:
                ref_html += "<p><b>Citations:</b></p>"
                for citation in ref_data['citations']:
                    ref_html += "<div style='margin-left: 20px; margin-bottom: 10px; padding: 10px; background-color: #f5f5f5;'>"
                    ref_html += f"<p><b>Section:</b> {citation['section']}</p>"
                    ref_html += f"<p><b>Context:</b> {citation['full_context']}</p>"
                    ref_html += "</div>"
            ref_html += "</div><hr>"
        ref_html += "</div>"
        return ref_html

    def _generate_paper_info_html(self, paper):
        """生成论文信息HTML"""
        info_html = "<div class='paper-info'>"
        info_html += "<h2>Paper Information</h2>"
        info_html += f"<p><b>Title:</b> {paper.title}</p>"
        info_html += f"<p><b>DOI:</b> {paper.doi}</p>"
        info_html += "</div>"
        return info_html

    def _generate_citations_html(self, results, citing_papers):
        """生成引用列表HTML，包含引用上下文
        
        Args:
            results: 引用结果对象
            citing_papers: 引用论文列表
            
        Returns:
            str: 生成的HTML字符串
        """
        citations_html = "<div class='citations-list'>"
        citations_html += f"<h2>引用论文 ({len(results._items)})</h2>"
        
        # 创建DOI到引用上下文的映射
        doi_to_contexts = {paper.doi: paper.citation_contexts for paper in citing_papers}
        
        for citation in results._items:
            paper = citation.paper
            citations_html += "<div class='citation-item' style='margin-bottom: 20px; padding: 15px; border: 1px solid #ddd;'>"
            
            # 显示标题
            citations_html += f"<p><b>标题:</b> {paper.title}</p>"
            
            # 显示PaperId
            if hasattr(paper, 'paperId'):
                citations_html += f"<p><b>Semantic Scholar PaperId:</b> {paper.paperId}</p>"

            if hasattr(paper, 'year'):
                citations_html += f"<p><b>年份:</b> {paper.year}</p>"
            
            if hasattr(paper, 'journal'):
                journal_name = paper.journal.name if paper.journal else ''
                citations_html += f"<p><b>出版平台:</b> {journal_name}</p>"

            if hasattr(paper, 'url'):
                citations_html += f"<p><b>网址:</b> {paper.url}</p>"

            if hasattr(paper, 'authors'):
                # 从作者列表中提取每个作者的名字，处理可能的空值情况
                author_names = [author.name for author in paper.authors if author]
                citations_html += f"<p><b>作者:</b> {', '.join(author_names)}</p>"

            
            # 显示DOI（如果存在）
            if hasattr(paper, 'externalIds') and paper.externalIds.get('DOI'):
                doi = paper.externalIds['DOI']
                safe_doi = doi.replace('/', '_')
                citations_html += f"<p><b>DOI:</b> {doi}</p>"
                citations_html += f"<a href='tmp/papers/{safe_doi}.pdf' download>Download PDF</a> "
                citations_html += f"<a href='tmp/xmls/{safe_doi}.grobid.xml' download>Download XML</a>"
            
            # 添加引用上下文
            doi_for_context = paper.externalIds.get('DOI')
            contexts = doi_to_contexts.get(doi_for_context, [])
            if contexts:
                citations_html += "<div class='citation-contexts' style='margin-top: 10px;'>"
                citations_html += "<p><b>引用上下文:</b></p>"
                for context in contexts:
                    citations_html += f"<div style='margin-left: 20px; margin-top: 5px; padding: 10px; background-color: #f5f5f5;'>"
                    citations_html += f"<p><b>章节:</b> {context['section']}</p>"
                    citations_html += f"<p><b>内容:</b> {context['full_context']}</p>"
                    citations_html += "</div>"
                citations_html += "</div>"
            
            citations_html += "</div>"
        
        citations_html += "</div>"
        return citations_html
    
    def process_pdf_file(self, pdf_file):
        """处理上传的PDF文件并返回结果"""
        if not pdf_file:
            return "", "", "", "Please upload a PDF file first"
            
        try:
            grobid_parser = CachedGrobidParser() # 使用默认的缓存目录
            xml = grobid_parser.parse_document(pdf_file.name)
            md = grobid_parser.parse_document_md(xml)
            res = markdown.markdown(md, extensions=['tables']).replace("<s>", "")
            res_rich_md = f'<div style="max-height: 775px; overflow-y: auto;">{res}</div>'
            res_xml = f'{xml}'
            res_md = f'{md}'
            
            # 修正XML文件路径
            xml_file = os.path.join(self.pipeline.xml_dir, 
                                  f"{os.path.basename(pdf_file.name).replace('.pdf', '')}.grobid.xml")
            parser = ReferenceParser(xml_file, "references.json")
            references = parser.parse_references()
            
            ref_html = self._generate_references_html(references)
            return res_xml, res_md, res_rich_md, ref_html
            
        except Exception as e:
            return "", "", "", f"Error processing PDF: {str(e)}"

    def process_paper_request(self, title_input=None, pdf_input=None):
        """处理论文检索请求"""
        try:
            if title_input and pdf_input:
                return "请只输入标题或上传PDF", "", "", ""
            elif pdf_input:
                # 如果上传了PDF,使用PDF处理流程
                result = self.pipeline.process_paper_from_pdf(pdf_input.name)
            elif title_input:
                # 如果输入了标题,使用标题处理流程
                result = self.pipeline.process_paper(title_input)
            else:
                return "请输入标题或上传PDF", "", "", ""

            # 生成各部分输出
            paper_info = self._generate_paper_info_html(result['original_paper'])
            citing_papers = self._generate_citations_html(result['citation_results'], result['citing_papers'])
          
            return paper_info, citing_papers
            
        except Exception as e:
            return f"Error: {str(e)}", "", ""


    def process_author_request(self, author_input):
        """处理作者检索请求"""
        try:
            result = self.pipeline.process_author(author_input)
            return result
        except Exception as e:
            return f"Error: {str(e)}", ""
  
    def create_ui(self):
        """创建两个Tab的WebUI界面"""
        with gr.Blocks() as demo:
            gr.Markdown(f"<h1 align='center'>{self.title}</h1>")
            
            with gr.Tabs() as tabs:
                # Tab 1: PDF解析
                with gr.Tab("解析PDF"):
                    with gr.Row():
                        # 左侧: PDF上传和预览
                        with gr.Column():
                            pdf_input = gr.File(type="file", label="上传PDF文件")
                            with gr.Row():
                                with gr.Column():
                                    view_btn = gr.Button("预览PDF", variant="primary")
                                with gr.Column():
                                    parse_btn = gr.Button("解析PDF", variant="primary")
                            pdf_viewer = gr.HTML()
                          
                        # 右侧: 解析结果
                        with gr.Column():
                            with gr.Tabs():
                                with gr.Tab("XML结果"):
                                    xml_output = gr.Textbox(lines=36,)
                                with gr.Tab("Markdown"):
                                    md_output = gr.Textbox(lines=36,)
                                with gr.Tab("Rich Markdown"):
                                    rich_md_output = gr.HTML()
                                with gr.Tab("参考文献解析"):
                                    ref_output = gr.HTML()
                
                # Tab 2: 论文检索与解析
                with gr.Tab("文章检索与解析"):
                    with gr.Row():
                        # 左侧: 输入和结果展示区
                        with gr.Column(scale=1):
                            gr.Markdown("### 输入论文标题或上传论文PDF")
                            title_input = gr.Textbox(lines=1, label="论文标题")
                            pdf_upload = gr.File(type="file", label="上传PDF")
                            search_btn = gr.Button("检索与引文分析", variant="primary")
                            
                            with gr.Tabs():
                                with gr.Tab("论文信息"):
                                    paper_info = gr.HTML()
                  
                        # 右侧: 引文内容展示区
                        with gr.Column(scale=1):
                            gr.Markdown("### 引文内容")
                            citing_papers = gr.HTML()

                with gr.Tab("作者检索与解析"):
                    with gr.Row():
                        with gr.Column():
                            author_input = gr.Textbox(lines=1, label="作者姓名")
                            search_author_btn = gr.Button("检索与解析", variant="primary")
                        with gr.Column():
                            author_info = gr.HTML()
                            author_papers = gr.HTML()

            # 绑定事件处理
            view_btn.click(
                fn=self.view_pdf,
                inputs=pdf_input,
                outputs=pdf_viewer
            )
            
            parse_btn.click(
                fn=self.process_pdf_file,
                inputs=pdf_input,
                outputs=[xml_output, md_output, rich_md_output, ref_output]
            )
            
            search_btn.click(
                fn=self.process_paper_request,
                inputs=[title_input, pdf_upload],
                outputs=[paper_info, citing_papers]
            )

            search_author_btn.click(
                fn=self.process_author_request,
                inputs=[author_input],
                outputs=[author_info, author_papers]
            )

        return demo

def create_ui():
    """创建UI实例"""
    ui = RefParserUI()
    return ui.create_ui()
