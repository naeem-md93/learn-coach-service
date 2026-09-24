from django.contrib import admin

from .models import Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'resource_type', 'subject', 'title_status', 'created_at')
    list_filter = ('resource_type', 'subject', 'title_status')
    search_fields = ('title', 'owner__email')
    readonly_fields = ('id', 'created_at', 'updated_at')
