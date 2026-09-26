from django.contrib import admin
from .models import Outcome, Viewing, ViewingRequest
admin.site.register(ViewingRequest)
admin.site.register(Viewing)
admin.site.register(Outcome)
