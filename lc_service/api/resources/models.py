import os
import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models


def resource_upload_path(instance, filename):
    """Store under MEDIA_ROOT/resources/<resource id>/<original filename>.

    Uses the model's own UUID primary key (already assigned before save,
    since it's a default rather than DB-assigned auto field) so each
    resource gets its own directory and re-uploads never collide.
    """
    return f"resources/{instance.id}/{filename}"


class Resource(models.Model):
    """A user-uploaded PDF (book or paper) — see CONTEXT.md `Resource`.

    Django owns this row (and the file on disk) as the single source of
    truth. FastAPI never persists anything about it; it only reads the PDF
    bytes via the HTTP file URL Django hands it (see `resources.services`).
    """

    class ResourceType(models.TextChoices):
        BOOK = "book", "Book"
        PAPER = "paper", "Paper"

    class Subject(models.TextChoices):
        # Open enum per CONTEXT.md — expected to grow over time. Modeled as
        # TextChoices (not a separate table) since it's a small, code-owned
        # list today; migrating to a lookup table later is a one-time data
        # migration if/when subjects become user-editable.
        BIOLOGY = "biology", "Biology"
        MATHEMATICS = "mathematics", "Mathematics"
        STATISTICS = "statistics", "Statistics"
        ELECTRONICS = "electronics", "Electronics"

    class TitleStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resources",
    )
    resource_type = models.CharField(max_length=16, choices=ResourceType.choices)
    subject = models.CharField(max_length=32, choices=Subject.choices)
    file = models.FileField(
        upload_to=resource_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
    )
    # Blank/null until FastAPI's title-extraction call completes; UI uses
    # title_status to know whether to show a placeholder/spinner.
    title = models.CharField(max_length=512, blank=True, default="")
    title_status = models.CharField(
        max_length=16,
        choices=TitleStatus.choices,
        default=TitleStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or os.path.basename(self.file.name)
