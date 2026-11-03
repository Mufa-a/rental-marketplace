from rest_framework import serializers
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ("id", "event", "title", "message", "link", "read", "read_at", "created_at")

    def get_read(self, obj):
        return obj.read_at is not None


class InboxPagination(CursorPagination):
    page_size = 30
    ordering = ("-created_at", "-id")


class NotificationListView(APIView):
    """GET /notifications/ — the signed-in user's in-app inbox, newest first."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        paginator = InboxPagination()
        rows = services.inbox(request.user)
        if request.query_params.get("unread") == "true":
            rows = rows.filter(read_at__isnull=True)
        page = paginator.paginate_queryset(rows, request, view=self)
        response = paginator.get_paginated_response(NotificationSerializer(page, many=True).data)
        response.data["unread"] = services.unread_count(request.user)
        return response


class NotificationReadView(APIView):
    """POST /notifications/read/ {"ids": [..]} marks those read; with no ids, marks everything read."""

    permission_classes = [IsAuthenticated]

    class ReadSerializer(serializers.Serializer):
        ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=200)

    def post(self, request):
        serializer = self.ReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.mark_read(request.user, serializer.validated_data.get("ids"))
        return Response({"marked_read": updated, "unread": services.unread_count(request.user)})


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"unread": services.unread_count(request.user)})
