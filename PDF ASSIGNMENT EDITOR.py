from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import json
import os

FONT_PATH = r"C:\Users\KIIT\PycharmProjects\Projects-ML\DancingScript-VariableFont_wght.ttf"
OUTPUT_DIR = "generated_pages"
os.makedirs(OUTPUT_DIR, exist_ok=True)
def create_handwritten_page(text, font_size=70, noise_strength=5, blur_radius=0.6):
    width, height = 1200, 1600

    # Light yellowish paper background
    paper_color = (250, 245, 230)
    paper = Image.new("RGB", (width, height), color=paper_color)

    # Add texture
    texture = np.random.normal(loc=0, scale=8, size=(height, width, 3)).astype(np.int16)
    paper_np = np.array(paper, dtype=np.int16)
    paper_np = np.clip(paper_np + texture, 0, 255).astype(np.uint8)
    paper = Image.fromarray(paper_np)

    # Draw text
    draw = ImageDraw.Draw(paper)
    font = ImageFont.truetype(FONT_PATH, font_size)

    x, y = 100, 150
    for line in text.split("\n"):
        draw.text((x, y), line, fill=(40, 30, 20), font=font)
        y += font_size + 20

    # Apply ink blur
    paper = paper.filter(ImageFilter.GaussianBlur(blur_radius))

    # Add GAN-like random noise
    paper_np = np.array(paper, dtype=np.uint8)
    noise = np.random.normal(0, noise_strength, paper_np.shape).astype(np.int16)
    distorted_np = np.clip(paper_np + noise, 0, 255).astype(np.uint8)
    paper = Image.fromarray(distorted_np)

    return paper

def generate_from_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pages = []
    page_items = list(data.items())  # [('Page_1', '...'), ('Page_2', '...')]

    for i, (page_key, text) in enumerate(page_items, start=1):
        print(f"Generating {page_key}...")
        img = create_handwritten_page(
            text=text,
            font_size=40,
            noise_strength=5,
            blur_radius=0.6,
        )
        img_path = os.path.join(OUTPUT_DIR, f"{page_key}.png")
        img.save(img_path)
        pages.append(img)

    return pages

def compile_pdf(images, output_pdf="handwritten_document.pdf"):
    print("Compiling into PDF...")
    images[0].save(
        output_pdf,
        save_all=True,
        append_images=images[1:],
        resolution=100.0,
    )
    print(f"PDF saved at: {os.path.abspath(output_pdf)}")

if __name__ == "__main__":
    json_path = r"C:\Users\KIIT\Downloads\class xi_ocr_results.json"
    generated_images = generate_from_json(json_path)
    compile_pdf(generated_images, "handwritten_pages.pdf")