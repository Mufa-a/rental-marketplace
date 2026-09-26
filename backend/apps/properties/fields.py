"""A GDAL-free Django field backed by PostGIS geography(Point, 4326).

The API stores longitude/latitude as a WKT point. PostGIS owns the spatial
type and functions; the Windows development runtime therefore does not need
to load native GDAL/GEOS libraries just to start Django.
"""
import re
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import models


@dataclass(frozen=True)
class GeographicPoint:
    longitude: float
    latitude: float

    @property
    def x(self):
        return self.longitude

    @property
    def y(self):
        return self.latitude


class PointField(models.Field):
    description = "PostGIS geography point (longitude, latitude)"

    def __init__(self, *args, geography=True, srid=4326, **kwargs):
        self.geography = geography
        self.srid = srid
        super().__init__(*args, **kwargs)

    def get_internal_type(self):
        return "TextField"

    def db_type(self, connection):
        if connection.vendor == "postgresql":
            kind = "geography" if self.geography else "geometry"
            return f"{kind}(Point,{self.srid})"
        return "text"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return None
        if isinstance(value, GeographicPoint):
            longitude, latitude = value.longitude, value.latitude
        elif isinstance(value, (tuple, list)) and len(value) == 2:
            longitude, latitude = value
        elif isinstance(value, str):
            match = re.fullmatch(r"(?:SRID=\d+;)?POINT\s*\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)", value, re.I)
            if not match:
                raise ValidationError("Location must be a WKT point.")
            longitude, latitude = map(float, match.groups())
        else:
            raise ValidationError("Location must contain longitude and latitude.")
        longitude, latitude = float(longitude), float(latitude)
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValidationError("Location coordinates are outside valid bounds.")
        return f"SRID={self.srid};POINT({longitude} {latitude})"

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        match = re.fullmatch(r"(?:SRID=\d+;)?POINT\s*\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)", value, re.I)
        if not match:
            raise ValueError("PostGIS returned an unexpected point representation.")
        longitude, latitude = map(float, match.groups())
        return GeographicPoint(longitude, latitude)

    def select_format(self, compiler, sql, params):
        if compiler.connection.vendor == "postgresql":
            return f"ST_AsText({sql})", params
        return sql, params

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["geography"] = self.geography
        kwargs["srid"] = self.srid
        return name, path, args, kwargs
