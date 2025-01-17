import gradio as gr
import base64
from pipeline import pipeline
from refparser import ReferenceParser
from grobid_parser import parse
from retrievers.crossref_paper import CrossrefPaper
from retrievers.s2_paper import CachedSemanticScholarWrapper
from retrievers.pypaperbot_download import PaperDownloader
import markdown
import os

class RefParserUI:
    def __init__(self):
        self.title = "RefParser"
    
    def view_pdf(self, pdf_file):
        """显示PDF文件"""
        with open(pdf_file.name,'rb') as f:
            pdf_data = f.read()
        b64_data = base64.b64encode(pdf_data).decode()
        return f"<embed src='data:application/pdf;base64,{b64_data}' type='application/pdf' width='100%' height='700px' />"

    def extract_text(self, pdf_file):
        """解析PDF文件"""
        xml, md = pipeline(pdf_file.name)
        res = markdown.markdown(md, extensions=['tables']).replace("<s>", "")
        res_rich_md = f'<div style="max-height: 775px; overflow-y: auto;">{res}</div>'
        res_xml = f'{xml}'
        res_md = f'{md}'
        
        xml_file = f".tmp/{pdf_file.name.split('/')[-1].replace('.pdf', '')}.grobid.xml"
        parser = ReferenceParser(xml_file, "references.json")
        references = parser.parse_references()
        
        ref_html = self._generate_references_html(references)
        return res_xml, res_md, res_rich_md, ref_html

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
            # 使用CrossrefPaper获取DOI
            cr_paper = CrossrefPaper(ref_obj=title)
            if not cr_paper.doi:
                return f"Could not find DOI for title: {title}", "", ""
            
            # 使用S2Paper获取引用信息
            sch = CachedSemanticScholarWrapper(timeout=3, use_cache=True)
            results = sch.get_paper_citations(cr_paper.doi)
            
            # 创建.tmp目录
            tmp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.tmp')
            os.makedirs(tmp_dir, exist_ok=True)
            
            # 保存DOI到文件，文件名使用原论文的DOI
            safe_doi = cr_paper.doi.replace('/', '_')  # 替换斜杠，避免路径问题
            doi_file_path = os.path.join(tmp_dir, f"{safe_doi}_citing_papers.txt")
            sch.save_dois_to_file(doi_file_path)
            
            # 生成HTML输出
            info_html = self._generate_paper_info_html(cr_paper)
            citations_html = self._generate_citations_html(results)
            
            # 创建下载器并下载论文
            pdf_dir = os.path.join(tmp_dir, 'papers')
            os.makedirs(pdf_dir, exist_ok=True)
            
            downloader = PaperDownloader(
                download_dir=pdf_dir,
                scholar_pages=1,
                scholar_results=1,
                use_doi_as_filename=True  # 使用DOI作为文件名
            )
            
            # 使用DOI文件下载
            download_log = downloader.download_by_doi_file(doi_file_path)
            
            # 添加文件保存信息到日志
            download_log = (f"DOIs saved to: {doi_file_path}\n"
                           f"PDFs will be downloaded to: {pdf_dir}\n"
                           f"{download_log}")
            
            return info_html, citations_html, download_log
            
        except Exception as e:
            error_msg = f"Error in _process_citations: {str(e)}"
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
        info_html = f"<div style='max-height: 775px; overflow-y: auto;'>"
        info_html += f"<h2>Paper Information</h2>"
        info_html += f"<p><b>Title:</b> {paper.title}</p>"
        info_html += f"<p><b>DOI:</b> {paper.doi}</p>"
        info_html += f"<p><b>Publication Date:</b> {paper.publication_date}</p>"
        info_html += f"<p><b>Publisher:</b> {paper.publisher}</p>"
        info_html += "</div>"
        return info_html

    def _generate_citations_html(self, results):
        """生成引用列表HTML"""
        citations_html = f"<div style='max-height: 775px; overflow-y: auto;'>"
        citations_html += f"<h2>Citing Papers ({len(results._items)})</h2>"
        
        for citation in results._items:
            paper = citation.paper
            citations_html += f"<div style='margin-left: 20px; margin-bottom: 10px; padding: 10px; background-color: #f5f5f5;'>"
            citations_html += f"<p><b>Title:</b> {paper.title}</p>"
            if paper.doi:
                citations_html += f"<p><b>DOI:</b> {paper.doi}</p>"
            citations_html += "</div>"
        
        citations_html += "</div>"
        return citations_html

    def create_ui(self):
        """创建Gradio界面"""
        with gr.Blocks() as demo:
            self._create_header()
            with gr.Row():
                with gr.Column():
                    input_elements = self._create_input_column()
                with gr.Column():
                    display_elements = self._create_display_column()
            
            self._setup_events(input_elements, display_elements)
            
        return demo

    def _create_header(self):
        """创建页面标题"""
        gr.Markdown(
            f'''<p align="center" width="100%">
            <p> 
            <h1 align="center">{self.title}</h1>
            '''
        )

    def _create_input_column(self):
        """创建输入列"""
        gr.Markdown('## Input')
        pdf_input = gr.File(type="file", label="Upload PDF")
        title_input = gr.Textbox(lines=1, label="Or Enter Paper Title")
        with gr.Row():
            parser_tab_btn = gr.Button("Parser")
            retriever_tab_btn = gr.Button("Retriever")
        pdf_view_out = gr.HTML()
        
        return {
            'pdf_input': pdf_input,
            'title_input': title_input,
            'parser_btn': parser_tab_btn,
            'retriever_btn': retriever_tab_btn,
            'pdf_view': pdf_view_out
        }

    def _create_display_column(self):
        """创建显示列"""
        with gr.Tabs() as display_tabs:
            with gr.TabItem("Retriever") as retriever_tab:
                paper_info = gr.HTML()
                citations_list = gr.HTML()
                download_log = gr.Textbox(lines=10)

            with gr.TabItem("Parser") as parser_tab:
                xml_out = gr.Textbox(lines=36)
                md_out = gr.Textbox(lines=36)
                rich_md_out = gr.HTML()
                ref_out = gr.HTML()
                
        return {
            'tabs': display_tabs,
            'paper_info': paper_info,
            'citations_list': citations_list,
            'download_log': download_log,
            'xml_out': xml_out,
            'md_out': md_out,
            'rich_md_out': rich_md_out,
            'ref_out': ref_out
        }

    def _setup_events(self, input_elements, display_elements):
        """设置事件处理"""
        # Parser Tab 事件
        input_elements['parser_btn'].click(
            lambda: gr.Tabs(selected="Parser"),
            outputs=display_elements['tabs']
        )
        input_elements['parser_btn'].click(
            self.extract_text,
            inputs=input_elements['pdf_input'],
            outputs=[
                display_elements['xml_out'],
                display_elements['md_out'],
                display_elements['rich_md_out'],
                display_elements['ref_out']
            ]
        )
        
        # Retriever Tab 事件
        input_elements['retriever_btn'].click(
            lambda: gr.Tabs(selected="Retriever"),
            outputs=display_elements['tabs']
        )
        input_elements['pdf_input'].change(
            fn=lambda x: self.retrieve_citations(x, "pdf"),
            inputs=input_elements['pdf_input'],
            outputs=[
                display_elements['paper_info'],
                display_elements['citations_list'],
                display_elements['download_log']
            ]
        )
        input_elements['title_input'].submit(
            fn=lambda x: self.retrieve_citations(x, "title"),
            inputs=input_elements['title_input'],
            outputs=[
                display_elements['paper_info'],
                display_elements['citations_list'],
                display_elements['download_log']
            ]
        )

def create_ui():
    """创建UI实例"""
    ui = RefParserUI()
    return ui.create_ui()
