from django.urls import path

from .views import ResourceDeleteView, ResourceFileView, ResourceListCreateView

app_name = 'resources'

urlpatterns = [
    path('', ResourceListCreateView.as_view(), name='resource-list-create'),
    path('<uuid:pk>/', ResourceDeleteView.as_view(), name='resource-delete'),
    path('<uuid:pk>/file/', ResourceFileView.as_view(), name='resource-file'),
]
