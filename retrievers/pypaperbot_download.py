# PyPaperBot Downloader
import subprocess  
import os 
import logging  

# Define Citation List
citations = ['Diffusion model as representation learner', 
             'On the design fundamentals of diffusion models: A survey', 
             'Dginstyle: Domain-generalizable semantic segmentation with image diffusion models and stylized semantic control', 
             'Data augmentation for object detection via controllable diffusion models', 
             'DiffuseMix: Label-Preserving Data Augmentation with Diffusion Models', 
             'Genview: Enhancing view quality with pretrained generative model for self-supervised learning', 
             'Zero-Shot Distillation for Image Encoders: How to Make Effective Use of Synthetic Data', 
             'What Makes a Good Dataset for Knowledge Distillation?', 
             'GenMix: Effective Data Augmentation with Generative Diffusion Model Image Editing', 
             'ToddlerDiffusion: Flash Interpretable Controllable Diffusion Model', 
             'DAKD: Data Augmentation and Knowledge Distillation using Diffusion Models for SAR Oil Spill Segmentation', 
             'A Data Augmentation Pipeline: Leveraging Controllable Diffusion Models and Automotive Simulation Software', 
             'Hierarchical-Latent Generative Models are Robust View Generators for Contrastive Representation Learning'
             ]



# Configure logging
logging.basicConfig(filename='pypaperbot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the function to run PyPaperBot for each citation title with error handling
def run_pypaperbot_query(citation_list, download_dir):
    for title in citation_list:
        # Construct the command with proper string escaping
        command = f'python -m PyPaperBot --query="{title}" --dwn-dir="{download_dir}" --scholar-pages=1 --scholar-results=1'
        try:
            # Execute the command
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            # Log successful execution
            logging.info(f'Successfully downloaded papers for query: "{title}"')
        except subprocess.CalledProcessError as e:
            # Log any errors that occur
            logging.error(f'Failed to download papers for query: "{title}". Error: {e.stderr}')

# Example usage
run_pypaperbot_query(citations, "/home/gaof23/projects/sciparser/query/downloaded_pdf")