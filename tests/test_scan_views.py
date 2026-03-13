import json
from unittest.mock import patch

import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed


@pytest.mark.django_db
class TestWineScannedView:
    def test_single_match_redirects(
        self, client, user, wine_factory, wine_barcode_factory
    ):
        wine = wine_factory(user=user)
        wine_barcode_factory(wine=wine, user=user, barcode="1234567890")
        client.force_login(user)
        r = client.get(reverse("wine-scan", kwargs={"code": "1234567890"}))
        assert r.status_code == 302
        assert str(wine.pk) in r.url

    def test_no_match_shows_add_link(self, client, user):
        client.force_login(user)
        r = client.get(reverse("wine-scan", kwargs={"code": "UNKNOWN999"}))
        assert r.status_code == 200
        assertTemplateUsed(r, "core/scanned_beverage.html")
        assert "add_url" in r.context


@pytest.mark.django_db
class TestLabelScanView:
    def test_renders_form(self, client, user):
        client.force_login(user)
        r = client.get(reverse("label-scan"))
        assert r.status_code == 200
        assertTemplateUsed(r, "core/label_scan.html")

    def test_post_with_image_data(self, client, user):
        """Test posting base64 image data stores in session and redirects."""
        import base64

        img_data = base64.b64encode(b"fake-image-data").decode()
        client.force_login(user)
        r = client.post(
            reverse("label-scan"),
            {"image_data": f"data:image/jpeg;base64,{img_data}"},
        )
        assert r.status_code == 302


@pytest.mark.django_db
class TestScanBarcodeAjax:
    def test_get_not_allowed(self, client, user):
        client.force_login(user)
        r = client.get(reverse("wine-scan-barcode"))
        assert r.status_code == 405

    def test_invalid_json(self, client, user):
        client.force_login(user)
        r = client.post(
            reverse("wine-scan-barcode"),
            "not-json",
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_no_images(self, client, user):
        client.force_login(user)
        r = client.post(
            reverse("wine-scan-barcode"),
            json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400
        data = json.loads(r.content)
        assert "No image" in data["error"]

    @patch("wine_cellar.apps.wine.views.scan.BarcodeScanner")
    def test_barcode_found(self, MockScanner, client, user):
        mock_instance = MockScanner.return_value
        mock_instance.scan_images_for_barcodes.return_value = ["0123456789"]
        client.force_login(user)
        import base64

        img = base64.b64encode(b"fake").decode()
        r = client.post(
            reverse("wine-scan-barcode"),
            json.dumps({"image": img}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.content)
        assert data["success"] is True
        assert data["barcode"] == "0123456789"

    @patch("wine_cellar.apps.wine.views.scan.BarcodeScanner")
    def test_no_barcode_found(self, MockScanner, client, user):
        mock_instance = MockScanner.return_value
        mock_instance.scan_images_for_barcodes.return_value = []
        client.force_login(user)
        import base64

        img = base64.b64encode(b"fake").decode()
        r = client.post(
            reverse("wine-scan-barcode"),
            json.dumps({"image": img}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.content)
        assert data["success"] is False

    def test_strips_data_uri_prefix(self, client, user):
        """Test that data:image/... prefix is stripped from images."""
        import base64

        with patch("wine_cellar.apps.wine.views.scan.BarcodeScanner") as MockScanner:
            mock_instance = MockScanner.return_value
            mock_instance.scan_images_for_barcodes.return_value = []
            client.force_login(user)
            img = base64.b64encode(b"fake").decode()
            r = client.post(
                reverse("wine-scan-barcode"),
                json.dumps({"image": f"data:image/png;base64,{img}"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            # Verify the cleaned image (without prefix) was passed
            call_args = mock_instance.scan_images_for_barcodes.call_args[0][0]
            assert not any("data:" in i for i in call_args)


@pytest.mark.django_db
class TestLabelScanResultView:
    def test_extract_wine_info_vintage(self):
        from wine_cellar.apps.wine.views.scan import LabelScanResultView

        view = LabelScanResultView()
        info = view.extract_wine_info("Chateau Margaux 2015 Grand Vin")
        assert info["vintage"] == 2015

    def test_extract_wine_info_abv(self):
        from wine_cellar.apps.wine.views.scan import LabelScanResultView

        view = LabelScanResultView()
        info = view.extract_wine_info("13.5% alc by volume")
        assert info["abv"] == 13.5

    def test_extract_wine_info_volume_ml(self):
        from wine_cellar.apps.wine.views.scan import LabelScanResultView

        view = LabelScanResultView()
        info = view.extract_wine_info("750ml")
        assert info["size"] == 0.75

    def test_extract_wine_info_volume_cl(self):
        from wine_cellar.apps.wine.views.scan import LabelScanResultView

        view = LabelScanResultView()
        info = view.extract_wine_info("75cl")
        assert info["size"] == 0.75

    def test_extract_wine_info_volume_l(self):
        from wine_cellar.apps.wine.views.scan import LabelScanResultView

        view = LabelScanResultView()
        info = view.extract_wine_info("1.5l Magnum")
        assert info["size"] == 1.5

    def test_extract_wine_info_no_matches(self):
        from wine_cellar.apps.wine.views.scan import LabelScanResultView

        view = LabelScanResultView()
        info = view.extract_wine_info("just a label with no data")
        assert info == {}
