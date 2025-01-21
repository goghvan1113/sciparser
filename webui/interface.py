import sys
import os
import json

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
            
            # 不再传入auxiliar_file参数，使用默认路径
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

    def _generate_author_info_html(self, authors):
        """生成作者信息HTML"""
        info_html = "<div class='authors-list'>"
        
        for i, author in enumerate(authors):
            papers = author.get('papers', [])
            info_html += f"""
            <div class='author-item' style='margin-bottom: 20px; padding: 15px; border: 1px solid #ddd;'>
                <div class='author-basic-info'>
                    <p><b>作者{i+1}姓名:</b> {author.get('name', '')}</p>
                    <p><b>机构:</b> {', '.join(author.get('affiliations', [])) if author.get('affiliations') else '未知'}</p>
                    <p><b>论文数量:</b> {author.get('paperCount', '')}</p>
                    <p><b>总引用次数:</b> {author.get('citationCount', '')}</p>
                    <p><b>Semantic Scholar主页:</b> <a href="{author.get('url', '')}" target="_blank">{author.get('url', '')}</a></p>
                    <p><b>h指数:</b> {author.get('hIndex', '')}</p>
                </div>
                
                <div class='papers-list' id='papers_{i}'>
                    <h4>论文列表</h4>
                    <div class='papers-container' style='max-height: 400px; overflow-y: auto;'>
                    """
            
            # 添加论文列表
            for paper in papers:
                info_html += f"""
                        <div class='paper-item' style='margin-bottom: 15px; padding: 10px; background-color: #f5f5f5;'>
                            <p><b>标题:</b> {paper.get('title', '')}</p>
                            <p><b>年份:</b> {paper.get('year', '')}</p>
                            <p><b>引用次数:</b> {paper.get('citationCount', '')}</p>
                            <p><b>发表于:</b> {paper.get('venue', '')}</p>
                        </div>
                    """
                
            info_html += """
                    </div>
                </div>
            </div>
            """
        
        info_html += "</div>"
        return info_html

    def process_author_request(self, author_input, papers_visible=False):
        """处理作者检索请求"""
        try:
            result = self.pipeline.process_author(author_input)
            author_info = self._generate_author_info_html(result['authors'])
            
            # 根据papers_visible状态添加显示/隐藏样式
            style = """
            <style>
                .papers-list { display: %s; }
            </style>
            """ % ('block' if papers_visible else 'none')
            
            return style + author_info
            
        except Exception as e:
            return f"Error: {str(e)}"


    def process_author_papers(self, author_index, top_n):
        """处理作者论文解析请求"""
        try:
            result = self.pipeline.process_author_papers(int(author_index), int(top_n))
            
            # 生成HTML展示
            html = f"""
            <div style='padding: 20px;'>
                <h2>论文分析完成</h2>
                <p>已分析作者 <b>{result['author'].get('name')}</b> 的论文</p>
                <p>分析报告已保存至: {result['markdown_file']}</p>
                <p>共分析 {len(result['papers_results'])} 篇论文（按引用次数排序）</p>
                <hr>
                <div style='max-height: 500px; overflow-y: auto;'>
                    {self._generate_papers_analysis_html(result['papers_results'])}
                </div>
            </div>
            """
            return html
        except Exception as e:
            return f"Error: {str(e)}"

    def _generate_papers_analysis_html(self, papers_results):
        """生成论文分析结果的HTML"""
        html = ""
        for i, result in enumerate(papers_results, 1):
            html += f"""
            <div style='margin-bottom: 20px; padding: 10px; border: 1px solid #ddd;'>
                <h3>{i}. {result['title']}</h3>
                <p>发表年份: {result.get('year', '未知')}</p>
                <p>发表venue: {result.get('venue', '未知')}</p>
                <p>引用次数: {result.get('citationCount', 0)}</p>
                <p>分析结果: 见Markdown文件</p>
            </div>
            """
        return html
    
    def create_ui(self):
        """创建两个Tab的WebUI界面"""
        with gr.Blocks() as demo:
            gr.Markdown(f"<h1 align='center'>{self.title}</h1>")
            
            with gr.Tabs():
                # Tab 1: PDF解析
                with gr.Tab("解析文献PDF"):
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
                with gr.Tab("文献检索与解析"):
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

                # Tab 3: 作者检索与解析
                with gr.Tab("作者检索与解析"):
                    with gr.Row():
                        # 左侧列：作者搜索
                        with gr.Column(scale=1):
                            author_input = gr.Textbox(lines=1, label="作者姓名")
                            search_author_btn = gr.Button("检索作者", variant="primary")
                            papers_visible = gr.State(False)
                            toggle_papers_btn = gr.Button("展开/收起论文列表", variant="secondary")
                            author_info = gr.HTML()
                        
                        # 右侧列：论文分析
                        with gr.Column(scale=1):
                            with gr.Row():
                                author_index_input = gr.Number(
                                    label="作者序号", 
                                    minimum=1, 
                                    maximum=10, 
                                    step=1, 
                                    value=1
                                )
                                top_n_input = gr.Number(
                                    label="分析论文数量", 
                                    minimum=1, 
                                    maximum=10, 
                                    step=1, 
                                    value=1
                                )
                            parse_author_papers_btn = gr.Button("解析作者论文", variant="primary")
                            final_papers_info = gr.HTML()

                # 处理展开/收起按钮的点击事件
                def toggle_papers(author_name, visible):
                    return not visible, self.process_author_request(author_name, not visible)
                
                search_author_btn.click(
                    fn=self.process_author_request,
                    inputs=[author_input, papers_visible],
                    outputs=[author_info]
                )
                
                toggle_papers_btn.click(
                    fn=toggle_papers,
                    inputs=[author_input, papers_visible],
                    outputs=[papers_visible, author_info]
                )

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

            parse_author_papers_btn.click(
                fn=self.process_author_papers,
                inputs=[author_index_input, top_n_input],
                outputs=[final_papers_info]
            )

        return demo

def create_ui():
    """创建UI实例"""
    ui = RefParserUI()
    return ui.create_ui()
