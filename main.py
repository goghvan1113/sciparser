import gradio as gr
import base64
from PyPDF2 import PdfFileReader
from pipeline import pipeline
from refparser import ReferenceParser
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

with gr.Blocks() as demo:
    gr.Markdown(
        '''<p align="center" width="100%">
        <p> 
        <h1 align="center">RefParser</h1>
        '''
    )
    with gr.Row():
        with gr.Column():
            gr.Markdown('## Upload PDF')
            file_input = gr.File(type="file")
            with gr.Row():
                with gr.Column():
                    viewer_button = gr.Button("View PDF")
                with gr.Column():
                    parser_button = gr.Button("Parse PDF")
            file_out = gr.HTML()
        with gr.Column():
            gr.Markdown('## Parsing file')
            with gr.Tab("XML Result"):
                xml_out = gr.Textbox(lines=36)
            with gr.Tab("Markdown Result"):
                md_out = gr.Textbox(lines=36)
            with gr.Tab("Rich Markdown Result"):
                rich_md_out = gr.HTML()
            with gr.Tab("References"):
                ref_out = gr.HTML()
            
    viewer_button.click(view_pdf, inputs=file_input, outputs=file_out)
    parser_button.click(extract_text, inputs=file_input, outputs=[xml_out, md_out, rich_md_out, ref_out])

demo.launch(server_name="0.0.0.0", debug=True)
