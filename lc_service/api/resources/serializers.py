from django.urls import reverse
from rest_framework import serializers

from .models import Resource


class ResourceSerializer(serializers.ModelSerializer):
    """Read representation used for list/retrieve responses."""

    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = (
            "id",
            "resource_type",
            "subject",
            "title",
            "title_status",
            "file_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_file_url(self, obj):
        """Public, browser-facing URL for the UI to fetch/display the PDF.

        This is the plain authenticated endpoint (JWT, owner-only) — not
        the signed internal URL used for the Django->FastAPI callback
        (see `services.build_internal_file_url`).
        """
        request = self.context.get("request")
        path = reverse("resources:resource-file", kwargs={"pk": obj.pk})
        return request.build_absolute_uri(path) if request else path


class ResourceUploadSerializer(serializers.ModelSerializer):
    """Write representation used for POST /api/resources/."""

    class Meta:
        model = Resource
        fields = ("id", "resource_type", "subject", "file")
        read_only_fields = ("id",)

    def validate_file(self, value):
        name = getattr(value, "name", "") or ""
        content_type = getattr(value, "content_type", "") or ""
        if not name.lower().endswith(".pdf") and content_type != "application/pdf":
            raise serializers.ValidationError("Only PDF files are supported.")
        return value
