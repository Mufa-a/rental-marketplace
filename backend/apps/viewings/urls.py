from django.urls import path

from .views import RequestActionView, RequestDetailView, RequestListCreateView, ViewingActionView

urlpatterns = [
    path("requests/", RequestListCreateView.as_view(), name="viewing-request-list"),
    path("requests/<int:request_id>/", RequestDetailView.as_view(), name="viewing-request-detail"),
    path("requests/<int:request_id>/<str:action>/", RequestActionView.as_view(), name="viewing-request-action"),
    path("<int:viewing_id>/<str:action>/", ViewingActionView.as_view(), name="viewing-action"),
]
