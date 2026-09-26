from django.urls import path

from .views import AmenityListView, MediaDetailView, MediaListCreateView, MediaPresignView, MyPropertyListCreateView, PropertyDetailView, PublicUnitDetailView, PublicUnitSearchView, SavedUnitDetailView, SavedUnitListCreateView, UnitAvailabilityView, UnitDetailView, UnitListCreateView

urlpatterns = [
    path("amenities/", AmenityListView.as_view(), name="amenity-list"),
    path("saved/", SavedUnitListCreateView.as_view(), name="saved-unit-list-create"),
    path("saved/<int:unit_id>/", SavedUnitDetailView.as_view(), name="saved-unit-detail"),
    path("search/", PublicUnitSearchView.as_view(), name="public-unit-search"),
    path("listings/<slug:slug>/", PublicUnitDetailView.as_view(), name="public-unit-detail"),
    path("mine/", MyPropertyListCreateView.as_view(), name="property-list-create"),
    path("<int:property_id>/", PropertyDetailView.as_view(), name="property-detail"),
    path("<int:property_id>/units/", UnitListCreateView.as_view(), name="unit-list-create"),
    path("units/<int:unit_id>/", UnitDetailView.as_view(), name="unit-detail"),
    path("units/<int:unit_id>/availability/", UnitAvailabilityView.as_view(), name="unit-availability"),
    path("units/<int:unit_id>/media/", MediaListCreateView.as_view(), name="media-list-create"),
    path("units/<int:unit_id>/media/presign/", MediaPresignView.as_view(), name="media-presign"),
    path("media/<int:media_id>/", MediaDetailView.as_view(), name="media-detail"),
]
