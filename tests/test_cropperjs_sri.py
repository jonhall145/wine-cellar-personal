from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CROPPER_JS_SCRIPT = (
    '<script src="https://cdnjs.cloudflare.com/ajax/libs/'
    'cropperjs/1.6.1/cropper.min.js" '
    'integrity="sha512-9KkIqdfN7ipEW6B6k+Aq20PV31bjODg4AA52W+tYtAE0'
    'jE0kMx49bjJ3FgvS56wzmyfMUHbQ4Km2b7l9+Y/+Eg==" '
    'crossorigin="anonymous"></script>'
)


def test_images_template_uses_sri_for_cropperjs():
    content = (REPO_ROOT / "wine_cellar/templates/core/beverage_images.html").read_text(
        encoding="utf-8"
    )
    assert CROPPER_JS_SCRIPT in content
