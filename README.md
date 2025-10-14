#  Handwritten PDF to Text (using TesseractOCR)

This script converts scanned or handwritten PDF files into text using **Tesseract OCR** only.  
It includes preprocessing steps for better accuracy and automatically saves results in JSON format.

---

##  Requirements
```bash
pip install pytesseract pdf2image opencv-python-headless
```

---

##  Setup
1. Mount Google Drive in Colab.
2. Create folders in Drive:
   ```
   MyDrive/
   ├── OCR_PDFs/       # Input PDFs
   └── OCR_Results/    # JSON output
   ```
3. Update folder paths in the script if needed.

---

##  How It Works
- Converts each PDF page to an image (`dpi=300`)
- Applies preprocessing (grayscale → binarize → denoise → deskew)
- Extracts text using Tesseract
- Saves results as `yourfile_ocr_results.json` in Drive

---

##  Example Output
```json
{
  "Page_1": { "Tesseract": "Extracted text here..." },
  "Page_2": { "Tesseract": "More text..." }
}
```
*
