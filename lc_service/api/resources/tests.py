import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Resource
from .tokens import make_file_access_token, verify_file_access_token

User = get_user_model()

# Minimal but structurally valid single-page PDF, so FileExtensionValidator
# (extension-based) and any future content sniffing keep working without
# needing a real multi-page fixture file.
MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n"
    b"%%EOF"
)

TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="lc_test_media_")


def make_pdf_upload(name="sample.pdf"):
    return SimpleUploadedFile(name, MINIMAL_PDF_BYTES, content_type="application/pdf")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ResourceModelTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def test_str_falls_back_to_filename_when_no_title(self):
        user = User.objects.create_user(email="owner@example.com", password="pass12345")
        resource = Resource.objects.create(
            owner=user,
            resource_type=Resource.ResourceType.BOOK,
            subject=Resource.Subject.BIOLOGY,
            file=make_pdf_upload(),
        )
        self.assertIn("sample", str(resource))
        self.assertEqual(resource.title_status, Resource.TitleStatus.PENDING)


class FileAccessTokenTests(APITestCase):
    def test_token_roundtrip(self):
        resource_id = "11111111-1111-1111-1111-111111111111"
        token = make_file_access_token(resource_id)
        self.assertTrue(verify_file_access_token(token, resource_id))

    def test_token_rejected_for_other_resource(self):
        token = make_file_access_token("11111111-1111-1111-1111-111111111111")
        self.assertFalse(
            verify_file_access_token(token, "22222222-2222-2222-2222-222222222222")
        )

    def test_garbage_token_rejected(self):
        self.assertFalse(verify_file_access_token("not-a-real-token", "abc"))


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ResourceAPITests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user(email="owner@example.com", password="pass12345")
        self.other_user = User.objects.create_user(email="other@example.com", password="pass12345")
        self.client.force_authenticate(user=self.user)

    @patch("lc_service.api.resources.views.services.extract_title", return_value="Extracted Title")
    def test_upload_success_sets_title_from_logic_service(self, mock_extract):
        url = reverse("resources:resource-list-create")
        response = self.client.post(
            url,
            {
                "file": make_pdf_upload(),
                "resource_type": Resource.ResourceType.BOOK,
                "subject": Resource.Subject.MATHEMATICS,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["title"], "Extracted Title")
        self.assertEqual(response.data["title_status"], Resource.TitleStatus.READY)
        mock_extract.assert_called_once()

    @patch("lc_service.api.resources.views.services.extract_title", return_value=None)
    def test_upload_falls_back_when_logic_service_unavailable(self, mock_extract):
        url = reverse("resources:resource-list-create")
        response = self.client.post(
            url,
            {
                "file": make_pdf_upload("my-notes.pdf"),
                "resource_type": Resource.ResourceType.PAPER,
                "subject": Resource.Subject.STATISTICS,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIn("my-notes", response.data["title"])
        self.assertEqual(response.data["title_status"], Resource.TitleStatus.FAILED)

    def test_upload_rejects_non_pdf(self):
        url = reverse("resources:resource-list-create")
        bad_file = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")
        response = self.client.post(
            url,
            {
                "file": bad_file,
                "resource_type": Resource.ResourceType.BOOK,
                "subject": Resource.Subject.BIOLOGY,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_requires_auth(self):
        self.client.force_authenticate(user=None)
        url = reverse("resources:resource-list-create")
        response = self.client.post(
            url,
            {
                "file": make_pdf_upload(),
                "resource_type": Resource.ResourceType.BOOK,
                "subject": Resource.Subject.BIOLOGY,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("lc_service.api.resources.views.services.extract_title", return_value="T")
    def test_list_only_returns_own_resources(self, mock_extract):
        Resource.objects.create(
            owner=self.user,
            resource_type=Resource.ResourceType.BOOK,
            subject=Resource.Subject.BIOLOGY,
            file=make_pdf_upload("mine.pdf"),
            title="Mine",
            title_status=Resource.TitleStatus.READY,
        )
        Resource.objects.create(
            owner=self.other_user,
            resource_type=Resource.ResourceType.BOOK,
            subject=Resource.Subject.BIOLOGY,
            file=make_pdf_upload("theirs.pdf"),
            title="Theirs",
            title_status=Resource.TitleStatus.READY,
        )

        url = reverse("resources:resource-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Mine")

    def test_delete_removes_row_and_rejects_other_users(self):
        resource = Resource.objects.create(
            owner=self.user,
            resource_type=Resource.ResourceType.BOOK,
            subject=Resource.Subject.BIOLOGY,
            file=make_pdf_upload("delete-me.pdf"),
            title="Delete Me",
            title_status=Resource.TitleStatus.READY,
        )
        other_resource = Resource.objects.create(
            owner=self.other_user,
            resource_type=Resource.ResourceType.BOOK,
            subject=Resource.Subject.BIOLOGY,
            file=make_pdf_upload("not-yours.pdf"),
            title="Not Yours",
            title_status=Resource.TitleStatus.READY,
        )

        # Can't delete someone else's resource.
        other_url = reverse("resources:resource-delete", kwargs={"pk": other_resource.pk})
        response = self.client.delete(other_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        own_url = reverse("resources:resource-delete", kwargs={"pk": resource.pk})
        response = self.client.delete(own_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Resource.objects.filter(pk=resource.pk).exists())

    def test_file_endpoint_owner_can_fetch(self):
        resource = Resource.objects.create(
            owner=self.user,
            resource_type=Resource.ResourceType.BOOK,
            subject=Resource.Subject.BIOLOGY,
            file=make_pdf_upload("readable.pdf"),
            title="Readable",
            title_status=Resource.TitleStatus.READY,
        )
        url = reverse("resources:resource-file", kwargs={"pk": resource.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_file_endpoint_rejects_other_users_without_token(self):
        resource = Resource.objects.create(
            owner=self.other_user,
            resource_type=Resource.ResourceType.BOOK,
            subject=Resource.Subject.BIOLOGY,
            file=make_pdf_upload("private.pdf"),
            title="Private",
            title_status=Resource.TitleStatus.READY,
        )
        url = reverse("resources:resource-file", kwargs={"pk": resource.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_file_endpoint_accepts_valid_signed_token_without_auth(self):
        resource = Resource.objects.create(
            owner=self.other_user,
            resource_type=Resource.ResourceType.BOOK,
            subject=Resource.Subject.BIOLOGY,
            file=make_pdf_upload("for-logic-service.pdf"),
            title="For Logic Service",
            title_status=Resource.TitleStatus.READY,
        )
        self.client.force_authenticate(user=None)
        token = make_file_access_token(resource.id)
        url = reverse("resources:resource-file", kwargs={"pk": resource.pk})
        response = self.client.get(url, {"token": token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_file_endpoint_rejects_token_for_different_resource(self):
        resource_a = Resource.objects.create(
            owner=self.user,
            resource_type=Resource.ResourceType.BOOK,
            subject=Resource.Subject.BIOLOGY,
            file=make_pdf_upload("a.pdf"),
        )
        resource_b = Resource.objects.create(
            owner=self.other_user,
            resource_type=Resource.ResourceType.BOOK,
            subject=Resource.Subject.BIOLOGY,
            file=make_pdf_upload("b.pdf"),
        )
        self.client.force_authenticate(user=None)
        token_for_a = make_file_access_token(resource_a.id)
        url_for_b = reverse("resources:resource-file", kwargs={"pk": resource_b.pk})
        response = self.client.get(url_for_b, {"token": token_for_a})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
