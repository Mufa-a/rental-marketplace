from django.urls import path
from .views import RequestActionView, RequestListCreateView, ViewingActionView
urlpatterns = [path("requests/", RequestListCreateView.as_view()), path("requests/<int:request_id>/<str:action>/", RequestActionView.as_view()), path("<int:viewing_id>/<str:action>/", ViewingActionView.as_view())]
