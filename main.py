import gradio as gr
import base64
from PyPDF2 import PdfFileReader
from pipeline import pipeline
from refparser import ReferenceParser
from grobid_parser import parse
from pdf_parser import Parser
from retrievers.crossref_paper import CrossrefPaper, COCIPaper
from retrievers.s2_paper import CachedSemanticScholarWrapper
from retrievers.pypaperbot_download import download_papers
import markdown
import json

def view_pdf(pdf_file):
    with open(pdf_file.name,'rb') as f:
        pdf_data = f.read()
    b64_data = base64.b64encode(pdf_data).decode()
    return f"<embed src='data:application/pdf;base64,{b64_data}' type='application/pdf' width='100%' height='700px' />"

def extract_text(pdf_file):
    xml, md = pipeline(pdf_file.name)
    res = markdown.markdown(md, extensions=['tables']).replace("<s>", "")
    res_rich_md = f'<div style="max-height: 775px; overflow-y: auto;">{res}</div>'
    res_xml = f'{xml}'
    res_md = f'{md}'
    
    xml_file = f".tmp/{pdf_file.name.split('/')[-1].replace('.pdf', '')}.grobid.xml"
    parser = ReferenceParser(xml_file, "references.json")
    references = parser.parse_references()
    
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
    
    return res_xml, res_md, res_rich_md, ref_html

def retrieve_citations(input_data, input_type="pdf"):
    """处理文献检索请求"""
    try:
        # 根据输入类型获取标题
        if input_type == "pdf":
            if not input_data:
                return "Please upload a PDF file or enter a title", "", ""
            # 从PDF中提取标题 (这部分暂时不处理)
            return "PDF processing not implemented yet", "", ""
        else:
            # 直接使用输入的标题
            title = input_data
            
        if not title:
            return "Could not extract or find title", "", ""
            
        # 使用CrossrefPaper获取DOI
        cr_paper = CrossrefPaper(ref_obj=title)
        if not cr_paper.doi:
            return f"Could not find DOI for title: {title}", "", ""
            
        # 使用S2Paper获取引用信息
        sch = CachedSemanticScholarWrapper(timeout=3, use_cache=True)
        results = sch.get_paper_citations(cr_paper.doi)
        
        # 构建基本信息HTML
        info_html = f"<div style='max-height: 775px; overflow-y: auto;'>"
        info_html += f"<h2>Paper Information</h2>"
        info_html += f"<p><b>Title:</b> {cr_paper.title}</p>"
        info_html += f"<p><b>DOI:</b> {cr_paper.doi}</p>"
        info_html += f"<p><b>Publication Date:</b> {cr_paper.publication_date}</p>"
        info_html += f"<p><b>Publisher:</b> {cr_paper.publisher}</p>"
        info_html += "</div>"
        
        # 构建引用列表HTML
        citations_html = f"<div style='max-height: 775px; overflow-y: auto;'>"
        citations_html += f"<h2>Citing Papers ({len(results._items)})</h2>"
        
        # 收集下载所需的标题列表
        titles_for_download = []
        
        for citation in results._items:
            paper = citation.paper
            citations_html += f"<div style='margin-left: 20px; margin-bottom: 10px; padding: 10px; background-color: #f5f5f5;'>"
            citations_html += f"<p><b>Title:</b> {paper.title}</p>"
            if paper.doi:
                citations_html += f"<p><b>DOI:</b> {paper.doi}</p>"
            citations_html += "</div>"
            
            if paper.title:
                titles_for_download.append(paper.title)
        
        citations_html += "</div>"
        
        # 下载论文
        download_log = download_papers(titles_for_download)
        
        return info_html, citations_html, download_log
        
    except Exception as e:
        return f"Error: {str(e)}", "", ""

with gr.Blocks() as demo:
    gr.Markdown(
        '''<p align="center" width="100%">
        <p> 
        <h1 align="center">RefParser</h1>
        '''
    )
    
    with gr.Row():
        with gr.Column():
            # 左侧输入区域
            gr.Markdown('## Input')
            # 文件上传
            pdf_input = gr.File(type="file", label="Upload PDF")
            # 标题输入
            title_input = gr.Textbox(lines=1, label="Or Enter Paper Title")
            with gr.Row():
                parser_tab_btn = gr.Button("Parser")
                retriever_tab_btn = gr.Button("Retriever")
            pdf_view_out = gr.HTML()
            
        with gr.Column():
            # 右侧显示区域
            with gr.Tabs() as display_tabs:
                # Retriever 相关的标签页
                with gr.TabItem("Retriever") as retriever_tab:
                    with gr.Tab("Paper Info"):
                        paper_info = gr.HTML()
                    with gr.Tab("Citations"):
                        citations_list = gr.HTML()
                    with gr.Tab("Download Log"):
                        download_log = gr.Textbox(lines=10)

                # Parser 相关的标签页
                with gr.TabItem("Parser") as parser_tab:
                    with gr.Tab("XML Result"):
                        xml_out = gr.Textbox(lines=36)
                    with gr.Tab("Markdown Result"):
                        md_out = gr.Textbox(lines=36)
                    with gr.Tab("Rich Markdown Result"):
                        rich_md_out = gr.HTML()
                    with gr.Tab("References"):
                        ref_out = gr.HTML()
                
    # Parser Tab 事件
    parser_tab_btn.click(
        lambda: gr.Tabs(selected="Parser"),
        outputs=display_tabs
    )
    parser_tab_btn.click(
        extract_text,
        inputs=pdf_input,
        outputs=[xml_out, md_out, rich_md_out, ref_out]
    )
    
    # Retriever Tab 事件
    retriever_tab_btn.click(
        lambda: gr.Tabs(selected="Retriever"),
        outputs=display_tabs
    )
    # PDF输入的检索
    pdf_input.change(
        fn=lambda x: retrieve_citations(x, "pdf"),
        inputs=pdf_input,
        outputs=[paper_info, citations_list, download_log]
    )
    # 标题输入的检索
    title_input.submit(
        fn=lambda x: retrieve_citations(x, "title"),
        inputs=title_input,
        outputs=[paper_info, citations_list, download_log]
    )

demo.launch(server_name="0.0.0.0", debug=True)
