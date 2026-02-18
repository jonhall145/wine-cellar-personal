from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CROPPER_JS_SCRIPT = (
    '<script src="https://cdnjs.cloudflare.com/ajax/libs/'
    'cropperjs/1.6.1/cropper.min.js" '
    'integrity="sha512-HqoaJUO8gm5CH+i8cqbXTadMtw0E2I2Uzjlvnzm8'
    'bxKE9GLoiT3+uLMEa19Ehx7mBeeSprucbQgiDq8FgWnbgA==" '
    'crossorigin="anonymous"></script>'
)


def test_wine_images_template_uses_sri_for_cropperjs():
    content = (
        REPO_ROOT / "wine_cellar/apps/wine/templates/wine_images.html"
    ).read_text(encoding="utf-8")
    assert CROPPER_JS_SCRIPT in content


def test_whisky_images_template_uses_sri_for_cropperjs():
    content = (
        REPO_ROOT / "wine_cellar/apps/whisky/templates/whisky/whisky_images.html"
    ).read_text(encoding="utf-8")
    assert CROPPER_JS_SCRIPT in content
