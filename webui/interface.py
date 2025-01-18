import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

import gradio as gr
import base64
from app.pipeline import ResearchPipeline, CachedGrobidParser
# from app.refparser import ReferenceParser
from grobid_parser import parse
from retrievers.crossref_paper import CrossrefPaper
from retrievers.s2_paper import CachedSemanticScholarWrapper
from retrievers.pypaperbot_download import PaperDownloader
import markdown

class RefParserUI:
    def __init__(self):
        self.title = "引文分析工具"
        self.pipeline = ResearchPipeline(cache_dir='./tmp')
    
    def view_pdf(self, pdf_file):
        """显示PDF文件"""
        with open(pdf_file.name,'rb') as f:
            pdf_data = f.read()
        b64_data = base64.b64encode(pdf_data).decode()
        return f"<embed src='data:application/pdf;base64,{b64_data}' type='application/pdf' width='100%' height='700px' />"

    def retrieve_citations(self, input_data, input_type="pdf"):
        """处理文献检索请求"""
        try:
            # 获取标题
            title = self._get_title(input_data, input_type)
            if not title:
                return "Could not extract or find title", "", ""
                
            # 获取引用信息
            info_html, citations_html, download_log = self._process_citations(title)
            return info_html, citations_html, download_log
            
        except Exception as e:
            return f"Error: {str(e)}", "", ""

    def _get_title(self, input_data, input_type):
        """从输入获取标题"""
        if input_type == "pdf":
            if not input_data:
                return None
            return "PDF processing not implemented yet"
        return input_data

    def _process_citations(self, title):
        """处理引用信息"""
        try:
            # 使用ResearchPipeline处理
            pipeline = ResearchPipeline(cache_dir='./tmp')
            result = pipeline.process_paper(title)
            
            # 生成HTML输出
            info_html = self._generate_paper_info_html(result['original_paper'])
            citations_html = self._generate_citations_html(result['citation_results'], result['citing_papers'])
            
            # 生成下载日志
            download_log = (
                f"原始论文: {result['original_paper'].title}\n"
                f"DOI: {result['original_paper'].doi}\n"
                f"DOIs保存至: {result['doi_file']}\n"
                f"引用论文数量: {len(result['citing_papers'])}\n"
                f"下载日志:\n{result['download_log']}"
            )
            
            return info_html, citations_html, download_log
            
        except Exception as e:
            error_msg = f"处理引用时出错: {str(e)}"
            print(error_msg)  # 打印错误信息以便调试
            return "", "", error_msg

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
        info_html += f"<p><b>Publication Date:</b> {paper.publication_date}</p>"
        info_html += "</div>"
        return info_html

    def _generate_citations_html(self, results, citing_papers):
        """生成引用列表HTML，包含引用上下文"""
        citations_html = "<div class='citations-list'>"
        citations_html += f"<h2>引用论文 ({len(results._items)})</h2>"
        
        # 创建DOI到引用上下文的映射
        doi_to_contexts = {paper.doi: paper.citation_contexts for paper in citing_papers}
        
        for citation in results._items:
            paper = citation.paper
            citations_html += "<div class='citation-item' style='margin-bottom: 20px; padding: 15px; border: 1px solid #ddd;'>"
            citations_html += f"<p><b>标题:</b> {paper.title}</p>"
            if paper.doi:
                citations_html += f"<p><b>DOI:</b> {paper.doi}</p>"
            
            # 添加引用上下文
            contexts = doi_to_contexts.get(paper.doi, [])
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
            grobid_parser = CachedGrobidParser(cache_dir='./tmp')
            xml = grobid_parser.parse_document(pdf_file.name)
            md = grobid_parser.parse_document_md(xml)
            res = markdown.markdown(md, extensions=['tables']).replace("<s>", "")
            res_rich_md = f'<div style="max-height: 775px; overflow-y: auto;">{res}</div>'
            res_xml = f'{xml}'
            res_md = f'{md}'
            
            xml_file = f"tmp/{pdf_file.name.split('/')[-1].replace('.pdf', '')}.grobid.xml"
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
            
            # 生成下载链接HTML
            download_links = "<div class='download-links'>"
            for paper in result['citing_papers']:
                safe_doi = paper.doi.replace('/', '_')
                download_links += f"""
                <div class='download-item'>
                    <p><b>Paper:</b> {paper.title}</p>
                    <a href='./tmp/papers/{safe_doi}.pdf' download>Download PDF</a>
                    <a href='./tmp/{safe_doi}.grobid.xml' download>Download XML</a>
                </div>
                """
            download_links += "</div>"
            
            # 生成引文内容
            citations = self._generate_citation_statements(result['citing_papers'])
            
            return paper_info, citing_papers, download_links, citations
            
        except Exception as e:
            return f"Error: {str(e)}", "", "", ""

    def _generate_citation_statements(self, citing_papers):
        """生成引文内容HTML"""
        html = "<div class='citation-statements'>"
        for paper in citing_papers:
            html += f"<div class='citing-paper'>"
            html += f"<h3>Citing Paper</h3>"
            html += f"<p><b>DOI:</b> {paper.doi}</p>"
            
            for ctx in paper.citation_contexts:
                html += f"""
                <div class='citation-context'>
                    <p><b>Section:</b> {ctx['section']}</p>
                    <p><b>Context:</b> {ctx['full_context']}</p>
                </div>
                """
            html += "</div><hr>"
        html += "</div>"
        return html

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
                                    view_btn = gr.Button("预览PDF")
                                with gr.Column():
                                    parse_btn = gr.Button("解析PDF")
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
                with gr.Tab("检索与解析"):
                    with gr.Row():
                        # 左侧: 输入和结果展示区
                        with gr.Column(scale=1):
                            gr.Markdown("### 输入论文标题或上传论文PDF")
                            title_input = gr.Textbox(lines=1, label="论文标题")
                            pdf_upload = gr.File(type="file", label="上传PDF")
                            search_btn = gr.Button("开始检索", variant="primary")
                            
                            with gr.Tabs():
                                with gr.Tab("论文信息"):
                                    paper_info = gr.HTML()
                                with gr.Tab("引用论文"):
                                    citing_papers = gr.HTML()
                                with gr.Tab("下载链接"):
                                    download_links = gr.HTML()
                        
                        # 右侧: 引文内容展示区
                        with gr.Column(scale=1):
                            gr.Markdown("### 引文内容")
                            citation_output = gr.HTML()

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
                outputs=[paper_info, citing_papers, download_links, citation_output]
            )

        return demo

def create_ui():
    """创建UI实例"""
    ui = RefParserUI()
    return ui.create_ui()
