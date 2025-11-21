"""
Utility to run the PDF parser and (later) build embeddings + index.
For now it runs the `pdf_to_products` script and writes products.json into `data/processed`.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PDF_REL = Path('data') / 'raw' / 'PC_Catalogue_2014_nahladove_PDF_v2.pdf'
OUT_REL = Path('data') / 'processed' / 'products.json'


def run_pdf_extract():
    script = ROOT / 'backend' / 'app' / 'utils' / 'pdf_to_products.py'
    input_pdf = ROOT / PDF_REL
    output_json = ROOT / OUT_REL
    cmd = [sys.executable, str(script), '--input', str(input_pdf), '--output', str(output_json)]
    print('Running:', ' '.join(cmd))
    subprocess.check_call(cmd)


if __name__ == '__main__':
    run_pdf_extract()
