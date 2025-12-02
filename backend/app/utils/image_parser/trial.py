import os
import json
from pathlib import Path
import fitz  # PyMuPDF
from llama_parse import LlamaParse


# ===============================
# CONFIG
# ===============================

PDF_PATH = r"C:\Users\vikas.singh1\Desktop\hp-ai-deck-generator\backend\app\utils\image_parser\PC_Catalogue_2014_nahladove_PDF_v2.pdf"
API_KEY = "llx-m7bfWCO60zBS90aScVHZjAj9iCTGq6KYZ6C3qKKE0uT4VGyQ"   # free-tier key (markdown-only)

OUTPUT_DIR = Path("output")
TEXT_DIR = OUTPUT_DIR / "text"
IMG_DIR = OUTPUT_DIR / "images"

TEXT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)


# ===============================
# PART 1 — LLAMAPARSE (FULL PDF → ONE MARKDOWN FILE)
# ===============================

def extract_full_markdown():
    print("🔹 Extracting full PDF text using LlamaParse…")

    parser = LlamaParse(
        api_key=API_KEY,
        result_type="markdown",
        extract_charts=True,
        auto_mode=True,
        auto_mode_trigger_on_image_in_page=True,
        auto_mode_trigger_on_table_in_page=True,
    )

    with open(PDF_PATH, "rb") as f:
        docs = parser.load_data(f, extra_info={"file_name": PDF_PATH})

    output_md_path = TEXT_DIR / "full_document.md"

    with open(output_md_path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(doc.text)

    print(f"✅ Saved full markdown at: {output_md_path}")
    return output_md_path






def extract_images_with_bold_title_detection():
    """
    Extract images and link the nearest bold (or fallback) title.
    Now extended to capture MULTI-LINE titles (above or below),
    but only within the strict horizontal band of the image.
    """

    import math
    import fitz

    print("🔹 Extracting images with multiline bold-aware title detection…")

    pdf = fitz.open(PDF_PATH)
    image_metadata = []

    def rect_for(span):
        b = span["bbox"]
        return fitz.Rect(b[0], b[1], b[2], b[3])

    for page_num in range(len(pdf)):
        page = pdf[page_num]
        spans = []

        page_dict = page.get_text("dict")

        # Extract all spans
        for block in page_dict["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span["text"].strip()
                    if not txt:
                        continue
                    spans.append({
                        "text": txt,
                        "font": span.get("font", ""),
                        "bbox": span.get("bbox"),
                        "size": span.get("size", None)
                    })

        # Bold detection
        for s in spans:
            s["is_bold"] = "bold" in s["font"].lower()

        images = page.get_images(full=True)

        for img_index, img in enumerate(images):

            # Save image
            xref = img[0]
            pix = fitz.Pixmap(pdf, xref)
            if pix.n < 5:
                img_bytes = pix.tobytes("png")
            else:
                pix = fitz.Pixmap(fitz.csRGB, pix)
                img_bytes = pix.tobytes("png")

            img_path = IMG_DIR / f"page_{page_num+1}_img_{img_index+1}.png"
            with open(img_path, "wb") as f:
                f.write(img_bytes)

            img_rect = page.get_image_bbox(img)
            img_left = img_rect.x0
            img_right = img_rect.x1

            # Strict horizontal alignment
            def horizontal_ok(span_rect):
                cx = (span_rect.x0 + span_rect.x1) / 2
                return img_left <= cx <= img_right

            spans_above = []
            spans_below = []

            for s in spans:
                r = rect_for(s)
                if not horizontal_ok(r):
                    continue

                if r.y1 <= img_rect.y0:
                    spans_above.append((s, r))

                elif r.y0 >= img_rect.y1:
                    spans_below.append((s, r))

            # Nearest span finder
            def nearest(span_list, bold_only):
                best = None
                best_dist = float("inf")

                for s, r in span_list:
                    if bold_only and not s["is_bold"]:
                        continue

                    if r.y1 <= img_rect.y0:
                        dist = img_rect.y0 - r.y1
                    else:
                        dist = r.y0 - img_rect.y1

                    if dist < best_dist:
                        best = (s, r, dist)
                        best_dist = dist

                return best

            # Prefer bold
            above_bold = nearest(spans_above, True)
            below_bold = nearest(spans_below, True)

            chosen = None
            direction = None

            if above_bold and below_bold:
                chosen = above_bold if above_bold[2] <= below_bold[2] else below_bold
                direction = "above" if chosen is above_bold else "below"
            elif above_bold:
                chosen = above_bold
                direction = "above"
            elif below_bold:
                chosen = below_bold
                direction = "below"
            else:
                # fallback
                a = nearest(spans_above, False)
                b = nearest(spans_below, False)
                if a and b:
                    chosen = a if a[2] <= b[2] else b
                    direction = "above" if chosen is a else "below"
                elif a:
                    chosen = a
                    direction = "above"
                elif b:
                    chosen = b
                    direction = "below"

            linked_text = ""
            distance = None

            if chosen:
                base_span, base_rect, distance = chosen

                # -------------------------------
                # MULTILINE TITLE EXPANSION LOGIC
                # -------------------------------
                final_lines = [base_span["text"]]

                if direction == "above":
                    # move upward capturing bold lines
                    current_top = base_rect.y0
                    while True:
                        found = None
                        for s, r in spans_above:
                            if r.y1 <= current_top and abs(current_top - r.y1) <= 2 * base_span["size"]:
                                if s["is_bold"]:
                                    found = (s, r)
                                    break
                        if not found:
                            break
                        final_lines.insert(0, found[0]["text"])
                        current_top = found[1].y0

                else:  # BELOW
                    current_bottom = base_rect.y1
                    while True:
                        found = None
                        for s, r in spans_below:
                            if r.y0 >= current_bottom and abs(r.y0 - current_bottom) <= 2 * base_span["size"]:
                                if s["is_bold"]:
                                    found = (s, r)
                                    break
                        if not found:
                            break
                        final_lines.append(found[0]["text"])
                        current_bottom = found[1].y1

                linked_text = " ".join(final_lines).strip()

                # 🔹 Print which image is linked to which title
                print(f"📌 Linked: page {page_num+1}, image {img_index+1} → '{linked_text}'")

            # Append result
            image_metadata.append({
                "page": page_num + 1,
                "image_file": str(img_path),
                "image_rect": [img_rect.x0, img_rect.y0, img_rect.x1, img_rect.y1],
                "chosen_direction": direction,
                "chosen_distance": distance,
                "linked_text": linked_text,
            })

    print(f"🖼️ Extracted {len(image_metadata)} images with multiline bold titles")
    return image_metadata






# ===============================
# RUN PIPELINE
# ===============================

# md_file = extract_full_markdown()
# image_metadata = extract_images_with_positions()
image_metadata = extract_images_with_bold_title_detection()

# Save image metadata to JSON
metadata_path = OUTPUT_DIR / "image_metadata.json"

with open(metadata_path, "w", encoding="utf-8") as f:
    json.dump(image_metadata, f, indent=4, ensure_ascii=False)

print(f"\n💾 Image metadata saved at: {metadata_path}")
print("\n🎉 Pipeline complete!")