import os
import torch
from transformers import AutoModel, AutoProcessor
from chandra.model.hf import generate_hf
from chandra.model.schema import BatchInputItem
from chandra.output import parse_markdown
from pdf2image import convert_from_path
from PIL import Image

POPPLER_PATH = r"C:\path\to\poppler\bin"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print("Используемое устройство:", DEVICE)

model = AutoModel.from_pretrained(
    "datalab-to/chandra",
    trust_remote_code=True
).to(DEVICE)

model.processor = AutoProcessor.from_pretrained("datalab-to/chandra")
model.eval()


def ocr_file(input_path, output_path="output.txt"):
    ext = os.path.splitext(input_path)[1].lower()
    batch = []

    if ext in [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"]:

        with Image.open(input_path) as image:
            image = image.convert("RGB")
            batch.append(BatchInputItem(image=image, prompt_type="ocr_layout"))

    elif ext == ".pdf":

        pages = convert_from_path(
            input_path,
            dpi=300,
            poppler_path=POPPLER_PATH
        )
        for page in pages:
            page = page.convert("RGB")
            batch.append(BatchInputItem(image=page, prompt_type="ocr_layout"))

    else:
        raise ValueError(f"Неподдерживаемый формат: {ext}")

    results = generate_hf(batch, model)

    all_text = []
    for r in results:
        t = parse_markdown(r.raw).text
        all_text.append(t)

    text_only = "\n\n=== PAGE BREAK ===\n\n".join(all_text)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text_only)

    print(f"Готово! Текст сохранён в {output_path}")


if __name__ == "__main__":
    # ocr_file("letter.jpg", "letter_txt.txt")
    # ocr_file("document.pdf", "doc_txt.txt")
    pass