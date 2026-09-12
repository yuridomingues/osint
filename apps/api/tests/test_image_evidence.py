import base64
import io

from PIL import Image

from app.image_evidence import analyze_image_bytes, hamming_hex
from app.models import ImageEvidenceImport


def make_image_bytes(color=(120, 80, 40)):
    image = Image.new("RGB", (320, 240), color=color)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    return out.getvalue()


def test_image_analysis_hashes_are_stable():
    data = make_image_bytes()
    one = analyze_image_bytes(data, "sample.jpg")
    two = analyze_image_bytes(data, "sample.jpg")

    assert one["sha256"] == two["sha256"]
    assert len(one["sha256"]) == 64
    assert len(one["ahash"]) == 16
    assert len(one["dhash"]) == 16
    assert one["width"] == 320
    assert one["height"] == 240


def test_perceptual_hamming_distance():
    assert hamming_hex("0000000000000000", "0000000000000000") == 0
    assert hamming_hex("0000000000000000", "0000000000000001") == 1


def test_image_payload_model_accepts_base64():
    data = make_image_bytes()
    payload = ImageEvidenceImport(
        filename="sample.jpg",
        content_type="image/jpeg",
        data_base64=base64.b64encode(data).decode(),
        search_web=False,
    )
    assert payload.filename == "sample.jpg"
