from django.urls import path

from .views import NotificationListView, NotificationReadView, UnreadCountView

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("unread-count/", UnreadCountView.as_view(), name="notification-unread-count"),
    path("read/", NotificationReadView.as_view(), name="notification-read"),
]
