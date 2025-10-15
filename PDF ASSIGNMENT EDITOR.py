import os
import uuid
import json
import cv2
import pytesseract
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pdf2image import convert_from_path
app = Flask(__name__)
app.secret_key = os.urandom(24)
BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_ROOT = os.path.join(BASE_DIR, "outputs")
FONT_FOLDER = os.path.join(BASE_DIR, "static", "fonts")
DEFAULT_FONT = os.path.join(FONT_FOLDER, r"C:\Users\KIIT\PycharmProjects\Projects-ML\Assignment editor\static\fonts\QEDonaldRoss.ttf")
KIIT_PAGE_PATH = r"C:\Users\KIIT\Downloads\WhatsApp Image 2025-10-15 at 7.28.53 PM.jpeg"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_ROOT, exist_ok=True)
os.makedirs(FONT_FOLDER, exist_ok=True)
def ensure_job_dirs(job_id):
    job_dir = os.path.join(OUTPUT_ROOT, job_id)
    os.makedirs(job_dir, exist_ok=True)
    return job_dir
def preprocess_image(img_path):
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    img = cv2.fastNlMeansDenoising(img, h=30)
    coords = np.column_stack(np.where(img > 0))
    if coords.size == 0:
        angle = 0.0
    else:
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
    (h, w) = img.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
def create_handwritten_page(text, background, font_path, font_size=34, noise_strength=5, blur_radius=0.6):
    width, height = 1200, 1600
    if background == "white":
        paper = Image.new("RGB", (width, height), color=(255, 255, 255))
    elif background == "cream":
        paper = Image.new("RGB", (width, height), color=(250, 245, 230))
    elif background == "kiit" and os.path.exists(KIIT_PAGE_PATH):
        paper = Image.open(KIIT_PAGE_PATH).convert("RGB").resize((width, height))
    else:
        paper = Image.new("RGB", (width, height), color=(255, 255, 255))
    texture = np.random.normal(loc=0, scale=8, size=(height, width, 3)).astype(np.int16)
    paper_np = np.array(paper, dtype=np.int16)
    paper_np = np.clip(paper_np + texture, 0, 255).astype(np.uint8)
    paper = Image.fromarray(paper_np)
    try:
        font = ImageFont.truetype(font_path, int(font_size * 1.5))
    except Exception:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(paper)
    x, y = 100, 150
    import textwrap
    for line in text.split("\n"):
        for wrapped in textwrap.wrap(line, width=60):  # wrap long lines naturally
            draw.text((x, y), wrapped, fill=(40, 30, 20), font=font)
            y += font_size + 20
    paper = paper.filter(ImageFilter.GaussianBlur(blur_radius))
    paper_np = np.array(paper, dtype=np.uint8)
    noise = np.random.normal(0, noise_strength, paper_np.shape).astype(np.int16)
    distorted_np = np.clip(paper_np + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(distorted_np)
def ocr_pdf_to_json(pdf_path, out_json_path, tmp_dir):
    pages = convert_from_path(pdf_path, dpi=300)
    results = {}
    for i, page in enumerate(pages, start=1):
        page_file = os.path.join(tmp_dir, f"page_{i}.png")
        page.save(page_file, "PNG")
        proc_img = preprocess_image(page_file)
        cv2.imwrite(os.path.join(tmp_dir, f"preproc_{i}.png"), proc_img)
        tess_text = pytesseract.image_to_string(proc_img)
        results[f"Page_{i}"] = {"Tesseract": tess_text.strip()}
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    return out_json_path
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded = request.files.get("pdf")
        if not uploaded or uploaded.filename == "":
            flash("No PDF uploaded.")
            return redirect(request.url)
        job_id = uuid.uuid4().hex
        job_dir = ensure_job_dirs(job_id)
        pdf_path = os.path.join(job_dir, uploaded.filename)
        uploaded.save(pdf_path)
        json_path = os.path.join(job_dir, f"{os.path.splitext(uploaded.filename)[0]}_ocr.json")
        ocr_pdf_to_json(pdf_path, json_path, job_dir)
        return redirect(url_for("edit", job_id=job_id))
    return render_template("index.html")
@app.route("/edit/<job_id>", methods=["GET", "POST"])
def edit(job_id):
    job_dir = os.path.join(OUTPUT_ROOT, job_id)
    if not os.path.exists(job_dir):
        flash("Job not found.")
        return redirect(url_for("index"))
    json_files = [f for f in os.listdir(job_dir) if f.endswith("_ocr.json")]
    if not json_files:
        flash("OCR JSON not found for this job.")
        return redirect(url_for("index"))
    json_path = os.path.join(job_dir, json_files[0])
    if request.method == "POST":
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for page_key in data.keys():
            form_key = f"text__{page_key}"
            if form_key in request.form:
                data[page_key]["Tesseract"] = request.form.get(form_key, "").strip()
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        flash("Edits saved.")
        return redirect(url_for("edit", job_id=job_id))
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return render_template("edit.html", job_id=job_id, data=data)
@app.route("/generate/<job_id>", methods=["POST"])
def generate(job_id):
    job_dir = os.path.join(OUTPUT_ROOT, job_id)
    if not os.path.exists(job_dir):
        flash("Job not found.")
        return redirect(url_for("index"))
    json_files = [f for f in os.listdir(job_dir) if f.endswith("_ocr.json")]
    if not json_files:
        flash("OCR JSON not found.")
        return redirect(url_for("edit", job_id=job_id))
    json_path = os.path.join(job_dir, json_files[0])
    background = request.form.get("background", "white")
    font_size = int(request.form.get("font_size", 34))
    font_file = request.files.get("font")
    if font_file and font_file.filename != "":
        font_filename = f"user_font_{uuid.uuid4().hex}.ttf"
        font_path = os.path.join(job_dir, font_filename)
        font_file.save(font_path)
    else:
        font_path = DEFAULT_FONT if os.path.exists(DEFAULT_FONT) else None
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    images = []
    for _, content in data.items():
        text = content.get("Tesseract", "")
        img = create_handwritten_page(text, background, font_path, font_size)
        images.append(img)

    if not images:
        flash("No pages to generate.")
        return redirect(url_for("edit", job_id=job_id))
    out_pdf = os.path.join(job_dir, f"{job_id}_handwritten.pdf")
    images[0].save(out_pdf, save_all=True, append_images=images[1:], resolution=300.0)
    return redirect(url_for("download", job_id=job_id, filename=os.path.basename(out_pdf)))
@app.route("/download/<job_id>/<filename>", methods=["GET"])
def download(job_id, filename):
    job_dir = os.path.join(OUTPUT_ROOT, job_id)
    file_path = os.path.join(job_dir, filename)
    if not os.path.exists(file_path):
        flash("File not found.")
        return redirect(url_for("index"))
    return send_file(file_path, as_attachment=True)
if __name__ == "__main__":
    app.run(debug=True)
