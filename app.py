import os
import time
from flask import Flask, render_template, request, redirect, send_from_directory, flash
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import re

UPLOAD_FOLDER = 'uploads'
VALIDATED_FOLDER = 'validated'

app = Flask(__name__)
app.secret_key = 'ai-validator-2025'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VALIDATED_FOLDER, exist_ok=True)

# OCR for Image
def extract_text_from_image(image_path):
    return pytesseract.image_to_string(Image.open(image_path))

# OCR for PDF
def extract_text_from_pdf(pdf_path):
    text = ""
    pages = convert_from_path(pdf_path, 300)
    for i, page in enumerate(pages):
        temp_path = os.path.join(UPLOAD_FOLDER, f'temp_page_{i}.jpg')
        page.save(temp_path, 'JPEG')
        text += extract_text_from_image(temp_path)
    return text

# Type Detection
def detect_document_type(text):
    text_lower = text.lower()
    if "income tax" in text_lower or "pan" in text_lower:
        return "PAN Card"
    elif "invoice" in text_lower:
        return "Invoice"
    elif "certificate" in text_lower:
        return "Certificate"
    elif "contract" in text_lower or "agreement" in text_lower:
        return "Contract"
    elif "aadhar" in text_lower or "uidai" in text_lower:
        return "Aadhar Card"
    else:
        return "Unknown Document"

# Validation
def validate_document(text, doc_type):
    results = {"Document Type": doc_type}
    if doc_type == "PAN Card":
        results['PAN'] = re.findall(r"[A-Z]{5}[0-9]{4}[A-Z]", text)
    elif doc_type == "Invoice":
        results['Invoice No'] = re.findall(r"INV[0-9]{3,}", text)
        results['Amount'] = re.findall(r"\₹?\d{2,}\.?\d*", text)
    elif doc_type == "Certificate":
        results['Issued To'] = re.findall(r"This is to certify that\s+(.*?)\s+has", text, re.DOTALL)
    elif doc_type == "Contract":
        results['Dates'] = re.findall(r"\d{2}/\d{2}/\d{4}", text)
    elif doc_type == "Aadhar Card":
        results['Aadhar Number'] = re.findall(r"\d{4}\s\d{4}\s\d{4}", text)
    
    results['Emails'] = re.findall(r"[\w\.-]+@[\w\.-]+", text)
    results['Phone Numbers'] = re.findall(r"\+?\d{10,12}", text)
    return results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    start_time = time.time()
    
    if 'document' not in request.files:
        flash("No file part.")
        return redirect('/')
    
    file = request.files['document']
    if file.filename == '':
        flash("No file selected.")
        return redirect('/')

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    if filename.lower().endswith('.pdf'):
        extracted_text = extract_text_from_pdf(file_path)
    else:
        extracted_text = extract_text_from_image(file_path)
    
    # ✅ FIXED: Proper indentation
    if not extracted_text.strip():
        return render_template(
            'result.html',
            text="❌ No text found in the uploaded document.",
            results={
                "Document Type": "Unknown",
                "Message": "No recognizable text was detected."
            },
            filename=filename,
            time_taken=0
        )

    doc_type = detect_document_type(extracted_text)
    validation_result = validate_document(extracted_text, doc_type)

    end_time = time.time()
    elapsed = round(end_time - start_time, 2)

    return render_template(
        'result.html',
        text=extracted_text,
        results=validation_result,
        filename=filename,
        time_taken=elapsed
    )

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
