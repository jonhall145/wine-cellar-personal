import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView
from django_ratelimit.decorators import ratelimit

from wine_cellar.apps.core.views import BaseLabelScanView, BaseScanView
from wine_cellar.apps.household.mixins import RequireHouseholdMixin
from wine_cellar.apps.wine.services import BarcodeScanner

logger = logging.getLogger(__name__)


class WineScanView(BaseScanView):
    template_name = "scan_wine.html"


class WineScannedView(RequireHouseholdMixin, TemplateView):
    template_name = "core/scanned_beverage.html"

    def dispatch(self, request, *args, **kwargs):
        code = self.kwargs["code"]
        scanner = BarcodeScanner()
        wines = scanner.get_wines_by_barcode(code, self.request.user)

        if wines is not None and wines.exists():
            if wines.count() == 1:
                return redirect(reverse("wine-detail", kwargs={"pk": wines.first().pk}))
            self.extra_context = {
                "scanned_beverages": wines,
                "barcode": code,
                "card_template": "wine_card.html",
            }
            return super().dispatch(request, *args, **kwargs)

        request.session["pending_barcode"] = code
        self.extra_context = {
            "add_url": reverse("wine-add", kwargs={"code": code}),
        }
        return super().dispatch(request, *args, **kwargs)


class LabelScanView(BaseLabelScanView):
    template_name = "core/label_scan.html"
    add_url_name = "wine-add"

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import LabelScanForm

        return LabelScanForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "form" not in context:
            context["form"] = self.get_form_class()()
        return context

    def post(self, request, *args, **kwargs):
        import base64

        if "extraction_result" in request.session:
            del request.session["extraction_result"]

        result = self._handle_camera_capture(request)
        if result:
            return result

        image_data = request.POST.get("image_data")
        if image_data:
            if "," in image_data:
                image_data = image_data.split(",")[1]
            image_bytes = base64.b64decode(image_data)
            request.session["scanned_label"] = {
                "filename": "camera_capture.jpg",
                "size": len(image_bytes),
                "data": [image_data],
                "multi_image": False,
            }
            return redirect(self.add_url_name)

        form = self.get_form_class()(request.POST, request.FILES)
        if form.is_valid():
            return self._form_valid(form)
        return self.render_to_response(self.get_context_data(form=form))

    def _form_valid(self, form):
        import base64

        images = []
        for field_name in ["barcode_image", "front_image", "back_image"]:
            image = form.cleaned_data.get(field_name)
            if image:
                image_data = image.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")
                images.append(base64_image)

        if images:
            self.request.session["scanned_label"] = {
                "filename": "uploaded_images",
                "size": sum(len(base64.b64decode(img)) for img in images),
                "data": images,
                "multi_image": len(images) > 1,
            }

        return redirect(self.add_url_name)


class LabelScanResultView(RequireHouseholdMixin, TemplateView):
    """Process OCR results and pre-fill wine form."""

    template_name = "label_scan_result.html"

    def extract_wine_info(self, text):
        """Extract wine information from OCR text."""
        import re

        info = {}

        year_match = re.search(r"\b(19\d{2}|20[0-2]\d)\b", text)
        if year_match:
            info["vintage"] = int(year_match.group(1))

        abv_match = re.search(r"(\d+\.?\d*)\s*%?\s*(alc|abv|vol)", text, re.IGNORECASE)
        if abv_match:
            info["abv"] = float(abv_match.group(1))

        vol_match = re.search(r"(\d+\.?\d*)\s*(ml|cl|l)\b", text, re.IGNORECASE)
        if vol_match:
            vol = float(vol_match.group(1))
            unit = vol_match.group(2).lower()
            if unit == "ml":
                vol = vol / 1000
            elif unit == "cl":
                vol = vol / 100
            info["size"] = vol

        return info


@ratelimit(key="user", rate="10/m", method="POST", block=True)
@login_required
def extract_wine_vision_ajax(request):
    """AJAX endpoint for wine data extraction from uploaded images."""
    from wine_cellar.apps.core.views import extract_vision_ajax

    return extract_vision_ajax(
        request,
        barcode_scanner_factory=BarcodeScanner,
        vision_extractor_path="wine_cellar.apps.wine.services.WineVisionExtractor",
        beverage_label="wine",
    )


@ratelimit(key="user", rate="30/m", method="POST", block=True)
@login_required
def scan_barcode_ajax(request):
    """AJAX endpoint for server-side barcode scanning from captured images."""
    import json

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        images = data.get("images", [])
        single_image = data.get("image")
        if single_image:
            images.append(single_image)

        if not images:
            return JsonResponse({"error": "No image data provided"}, status=400)

        cleaned_images = []
        for img in images:
            if "," in img:
                img = img.split(",", 1)[1]
            cleaned_images.append(img)

        barcode_scanner = BarcodeScanner()
        barcodes = barcode_scanner.scan_images_for_barcodes(cleaned_images)

        if barcodes:
            return JsonResponse(
                {
                    "success": True,
                    "barcodes": barcodes,
                    "barcode": barcodes[0],
                }
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "barcodes": [],
                    "message": "No barcode detected in image",
                }
            )

    except Exception:
        logger.exception("Error in barcode scanning")
        return JsonResponse(
            {"error": "An internal error occurred while scanning the barcode."},
            status=500,
        )
