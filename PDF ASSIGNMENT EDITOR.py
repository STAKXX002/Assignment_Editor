import os
import uuid
import json
import cv2
import pytesseract
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pdf2image import convert_from_path
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)
app.secret_key = os.urandom(24)
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env file")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    model = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_ROOT = os.path.join(BASE_DIR, "outputs")
FONT_FOLDER = os.path.join(BASE_DIR, "static", "fonts")
STATIC_FOLDER = os.path.join(BASE_DIR, "static")

# Use relative paths for portability
DEFAULT_FONT = os.path.join(FONT_FOLDER, "QEDonaldRoss.ttf")
KIIT_PAGE_PATH = os.path.join(STATIC_FOLDER, "images", "kiit_template.jpeg")  # Assumes you move it here

# --- Create Directories ---
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_ROOT, exist_ok=True)
os.makedirs(FONT_FOLDER, exist_ok=True)
os.makedirs(os.path.join(STATIC_FOLDER, "images"), exist_ok=True)
def ensure_job_dirs(job_id):
    job_dir = os.path.join(OUTPUT_ROOT, job_id)
    os.makedirs(job_dir, exist_ok=True)
    return job_dir
def ocr_pdf_to_json_gemini(pdf_path, out_json_path, tmp_dir):

    if not model:
        flash("Gemini AI model is not configured. Please check your API key.")
        return None
    try:
        pages = convert_from_path(pdf_path, dpi=200)
    except Exception as e:
        flash(f"Error converting PDF to images: {e}. Is Poppler installed and in your PATH?")
        return None
    results = {}
    prompt = """
    You are a highly accurate OCR engine. Extract all text from the provided image.
    Preserve line breaks. Return ONLY the extracted text, with no extra commentary,
    greetings, or markdown formatting.
    """
    for i, page_image in enumerate(pages, start=1):
        page_key = f"Page_{i}"
        try:
            response = model.generate_content([prompt, page_image])
            results[page_key] = {"Tesseract": response.text.strip()}
        except Exception as e:
            print(f"Error processing page {i} with Gemini: {e}")
            results[page_key] = {"Tesseract": f"Error extracting text from this page: {e}"}
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    return out_json_path
def create_handwritten_page(text, background, font_path, font_size=34, noise_strength=5, blur_radius=0.6):
    width, height = 1200, 1600
    if background == "kiit" and os.path.exists(KIIT_PAGE_PATH):
        paper = Image.open(KIIT_PAGE_PATH).convert("RGB").resize((width, height))
    elif background == "cream":
        paper = Image.new("RGB", (width, height), color=(250, 245, 230))
    else:  # Default to white
        paper = Image.new("RGB", (width, height), color=(255, 255, 255))
    texture = np.random.normal(loc=0, scale=8, size=(height, width, 3)).astype(np.int16)
    paper_np = np.array(paper, dtype=np.int16)
    paper_np = np.clip(paper_np + texture, 0, 255).astype(np.uint8)
    paper = Image.fromarray(paper_np)
    try:
        font = ImageFont.truetype(font_path, int(font_size * 1.5))
    except IOError:
        flash(f"Font not found at {font_path}. Using default.")
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(paper)
    x, y = 100, 150
    import textwrap
    for line in text.split("\n"):
        for wrapped_line in textwrap.wrap(line, width=60, replace_whitespace=False):
            draw.text((x, y), wrapped_line, fill=(40, 30, 20), font=font)
            y += font_size + 20
    paper = paper.filter(ImageFilter.GaussianBlur(blur_radius))
    paper_np = np.array(paper, dtype=np.uint8)
    noise = np.random.normal(0, noise_strength, paper_np.shape).astype(np.int16)
    distorted_np = np.clip(paper_np + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(distorted_np)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if 'pdf' not in request.files:
            flash("No file part in the request.")
            return redirect(request.url)

        uploaded_file = request.files["pdf"]
        if uploaded_file.filename == "":
            flash("No PDF file selected.")
            return redirect(request.url)

        if uploaded_file and uploaded_file.filename.endswith('.pdf'):
            job_id = uuid.uuid4().hex
            job_dir = ensure_job_dirs(job_id)
            pdf_path = os.path.join(job_dir, "source.pdf")
            uploaded_file.save(pdf_path)

            json_path = os.path.join(job_dir, "ocr_output.json")
            if ocr_pdf_to_json_gemini(pdf_path, json_path, job_dir):
                return redirect(url_for("edit", job_id=job_id))
            else:
                # OCR function flashed an error message already
                return redirect(url_for("index"))

    return render_template("index.html")


@app.route("/edit/<job_id>", methods=["GET", "POST"])
def edit(job_id):
    job_dir = os.path.join(OUTPUT_ROOT, job_id)
    json_path = os.path.join(job_dir, "ocr_output.json")

    if not os.path.exists(json_path):
        flash("Job not found or OCR data is missing.")
        return redirect(url_for("index"))

    if request.method == "POST":
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Update data from form
        for page_key in data.keys():
            form_key = f"text__{page_key}"
            if form_key in request.form:
                data[page_key]["Tesseract"] = request.form.get(form_key, "").strip()
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        flash("Edits saved successfully!")
        return redirect(url_for("edit", job_id=job_id))
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return render_template("edit.html", job_id=job_id, data=data)
@app.route("/generate/<job_id>", methods=["POST"])
def generate(job_id):
    job_dir = os.path.join(OUTPUT_ROOT, job_id)
    json_path = os.path.join(job_dir, "ocr_output.json")
    if not os.path.exists(json_path):
        flash("OCR data not found for this job.")
        return redirect(url_for("edit", job_id=job_id))
    background = request.form.get("background", "white")
    font_size = int(request.form.get("font_size", 34))
    font_choice = request.form.get("font_choice", "QEDonaldRoss.ttf")
    font_path = os.path.join(FONT_FOLDER, font_choice)
    if not os.path.exists(font_path):
        flash(f"Warning: Font file '{font_choice}' not found. Using default.")
        font_path = DEFAULT_FONT
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    images = []
    for page_key, content in data.items():
        text_content = content.get("Tesseract", "")
        if text_content:  # Only generate a page if there is text
            img = create_handwritten_page(text_content, background, font_path, font_size)
            images.append(img)
    if not images:
        flash("No text found to generate a PDF.")
        return redirect(url_for("edit", job_id=job_id))
    out_pdf_filename = f"{job_id}_handwritten.pdf"
    out_pdf_path = os.path.join(job_dir, out_pdf_filename)
    images[0].save(
        out_pdf_path,
        save_all=True,
        append_images=images[1:],
        resolution=100.0,
        quality=95
    )
    return redirect(url_for("download", job_id=job_id, filename=out_pdf_filename))

@app.route("/download/<job_id>/<filename>")
def download(job_id, filename):
    job_dir = os.path.join(OUTPUT_ROOT, job_id)
    file_path = os.path.join(job_dir, filename)
    if not os.path.exists(file_path):
        flash("File not found.")
        return redirect(url_for("index"))
    return send_file(file_path, as_attachment=True)
if __name__ == "__main__":
    app.run(debug=True)