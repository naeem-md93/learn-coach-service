import os

from django.http import FileResponse, Http404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Resource
from .serializers import ResourceSerializer, ResourceUploadSerializer
from .tokens import verify_file_access_token


class ResourceListCreateView(generics.ListCreateAPIView):
    """GET /api/resources/ -> list of the caller's resources.

    POST /api/resources/ -> upload a new resource (multipart: file,
    resource_type, subject). Synchronously calls FastAPI's title
    extraction before responding, per CONTEXT.md's "light sync step on
    upload". Never fails the upload if the logic service is slow/down —
    falls back to the filename with title_status=failed instead.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return Resource.objects.filter(owner=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ResourceUploadSerializer
        return ResourceSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource = serializer.save(owner=request.user)

        title = services.extract_title(resource)
        if title:
            resource.title = title
            resource.title_status = Resource.TitleStatus.READY
        else:
            resource.title = os.path.basename(resource.file.name)
            resource.title_status = Resource.TitleStatus.FAILED
        resource.save(update_fields=["title", "title_status", "updated_at"])

        output = ResourceSerializer(resource, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class ResourceDeleteView(generics.DestroyAPIView):
    """DELETE /api/resources/<id>/ -> remove the resource row and its file."""

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ResourceSerializer
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return Resource.objects.filter(owner=self.request.user)

    def perform_destroy(self, instance):
        file_field = instance.file
        instance.delete()
        # Delete the file from disk after the row is gone; if this step
        # fails, an orphaned file is preferable to a broken row.
        if file_field:
            file_field.delete(save=False)


class ResourceFileView(APIView):
    """GET /api/resources/<id>/file/ -> streams the stored PDF.

    Two ways in, both landing here:
    - Browser/UI: normal JWT auth, owner-only (matches every other
      resource endpoint).
    - FastAPI: no user session available, so it instead presents a
      short-lived, resource-scoped signed `?token=` query param that
      Django itself minted and embedded in the URL it gave FastAPI (see
      `services.build_internal_file_url` / `tokens.py`). This keeps the
      endpoint from being a fully open file server while not requiring
      FastAPI to hold real user credentials, which it has no concept of.
    """

    permission_classes = (permissions.AllowAny,)

    def get(self, request, pk, *args, **kwargs):
        try:
            resource = Resource.objects.get(pk=pk)
        except Resource.DoesNotExist as exc:
            raise Http404 from exc

        token = request.query_params.get("token")
        if token and verify_file_access_token(token, resource.id):
            authorized = True
        else:
            user = request.user
            authorized = bool(
                user
                and user.is_authenticated
                and resource.owner_id == user.id
            )

        if not authorized:
            raise Http404

        if not resource.file:
            raise Http404

        return FileResponse(
            resource.file.open("rb"),
            content_type="application/pdf",
            filename=os.path.basename(resource.file.name),
        )
