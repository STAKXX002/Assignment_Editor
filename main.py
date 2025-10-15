import os
import cv2
import pytesseract
import numpy as np
import json
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pdf2image import convert_from_path

PDF_PATH = input("Enter the full path of the PDF file: ").strip()
OUTPUT_FOLDER = r"C:\Users\KIIT\Documents\OCR_Results"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
FONT_PATH = r"C:\Users\KIIT\PycharmProjects\Projects-ML\DancingScript-VariableFont_wght.ttf"

def preprocess_image(img_path):
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    img = cv2.fastNlMeansDenoising(img, h=30)
    coords = np.column_stack(np.where(img > 0))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = img.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return img

def create_handwritten_page(text, font_size=40, noise_strength=5, blur_radius=0.6):
    width, height = 1200, 1600
    paper_color = (250, 245, 230)
    paper = Image.new("RGB", (width, height), color=paper_color)
    texture = np.random.normal(loc=0, scale=8, size=(height, width, 3)).astype(np.int16)
    paper_np = np.array(paper, dtype=np.int16)
    paper_np = np.clip(paper_np + texture, 0, 255).astype(np.uint8)
    paper = Image.fromarray(paper_np)
    draw = ImageDraw.Draw(paper)
    font = ImageFont.truetype(FONT_PATH, font_size)
    x, y = 100, 150
    for line in text.split("\n"):
        draw.text((x, y), line, fill=(40, 30, 20), font=font)
        y += font_size + 20
    paper = paper.filter(ImageFilter.GaussianBlur(blur_radius))
    paper_np = np.array(paper, dtype=np.uint8)
    noise = np.random.normal(0, noise_strength, paper_np.shape).astype(np.int16)
    distorted_np = np.clip(paper_np + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(distorted_np)

def generate_handwritten_from_json(json_path, output_dir):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    images = []
    for i, (page_key, content) in enumerate(data.items(), start=1):
        text = content.get("Tesseract", "")
        img = create_handwritten_page(text)
        img_path = os.path.join(output_dir, f"{page_key}.png")
        img.save(img_path)
        images.append(img)
    return images

def compile_pdf(images, output_pdf):
    if not images:
        print("No pages to compile.")
        return
    images[0].save(output_pdf, save_all=True, append_images=images[1:], resolution=100.0)
    print(f"Handwritten PDF saved at: {os.path.abspath(output_pdf)}")

if not os.path.exists(PDF_PATH):
    raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

pdf_name = os.path.splitext(os.path.basename(PDF_PATH))[0]
print(f"Processing: {pdf_name}")

pages = convert_from_path(PDF_PATH, dpi=300)
results = {}

for i, page in enumerate(pages):
    img_path = os.path.join(OUTPUT_FOLDER, f"page_{i+1}.png")
    page.save(img_path, "PNG")
    print(f"OCR Page {i+1}/{len(pages)}...")
    proc_img = preprocess_image(img_path)
    cv2.imwrite(os.path.join(OUTPUT_FOLDER, f"preproc_{i+1}.png"), proc_img)
    tess_text = pytesseract.image_to_string(proc_img)
    results[f"Page_{i+1}"] = {"Tesseract": tess_text.strip()}

json_path = os.path.join(OUTPUT_FOLDER, f"{pdf_name}_ocr_results.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=4, ensure_ascii=False)
print(f"OCR JSON saved at: {json_path}")

handwritten_output_dir = os.path.join(OUTPUT_FOLDER, f"{pdf_name}_handwritten_pages")
os.makedirs(handwritten_output_dir, exist_ok=True)
handwritten_images = generate_handwritten_from_json(json_path, handwritten_output_dir)
output_pdf = os.path.join(OUTPUT_FOLDER, f"{pdf_name}_handwritten.pdf")
compile_pdf(handwritten_images, output_pdf)
print("Process completed successfully.")
