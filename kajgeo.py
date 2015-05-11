#!/usr/bin/env python
# -*- coding: latin-1 -*-

"""
Geo functions for distances, bearings, speeds, latitudes and longitudes
"""

from math import radians, degrees, sin, cos, tan, asin, atan2
from math import sqrt, pi, log
from time import strftime


def km_h(speed_in_m_s):
    """km_h(10) = 36 <=> 10 m/s = 36 km/h"""
    return 3.6 * speed_in_m_s


def m_s(speed_in_km_h):
    """m_s(36) = 10 <=> 36 km/h = 10 m/s"""
    return speed_in_km_h / 3.6


def distance(lat1, lon1, lat2, lon2):
    """in km using haversine formula"""
    # convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # haversine formula
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))

    # 6367 km is the radius of the Earth
    km = 6367 * c
    return km


def bearing(lat1, lon1, lat2, lon2):
    """Bearing = direction, in degrees"""
    # convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    direction = atan2(asin(cos(lat1) * sin((lon2 - lon1) / 2)),
                      lat2 - lat1)
    return (degrees(direction) + 360) % 360


def decdeg2dms(dd):
    """60.5 -> (60, 30, 0.0)"""
    mnt, sec = divmod(dd * 3600, 60)
    deg, mnt = divmod(mnt, 60)
    return int(deg), int(mnt), sec


def dms2decdeg(deg, mnt, sec):
    """60, 30, 0.0 -> 60.5"""
    return deg + mnt / float(60) + sec / float(3600)


def lat_ns(lat_dd):
    """N or S"""
    return "N" if lat_dd > 0 else "S"


def lon_we(lon_dd):
    """W or E"""
    return "E" if lon_dd > 0 else "W"


def lat_dms_fmt(lat_dd):
    """60°11′35″N"""
    (lat_d, lat_m, lat_s) = decdeg2dms(lat_dd)
    ns = lat_ns(lat_dd)
    return "%s°%s′%s″%s" % (lat_d, lat_m, "{:.0f}".format(lat_s), ns)


def lon_dms_fmt(lon_dd):
    """ 21°54′25″E"""
    (lon_d, lon_m, lon_s) = decdeg2dms(lon_dd)
    we = lon_we(lon_dd)
    return "%s°%s′%s″%s" % (lon_d, lon_m, "{:.0f}".format(lon_s), we)


def lat_lon_5(lat_or_lon):
    """Cut off after 5 decimals"""
    return "{:.5f}".format(lat_or_lon)


def lat2y(lat_dd):
    """Mercator"""
    return log(tan(pi / 4 + radians(lat_dd) / 2))


def lon2x(lon_dd):
    """Mercator"""
    return radians(lon_dd)


def lat2canvasy(lat, min_lat, max_lat, ymin, ymax, y_center):
    """ Project on canvas"""
    lat, min_lat, max_lat = map(lat2y, [lat, min_lat, max_lat])
    return (ymax - y_center - (lat - min_lat) * (ymax - ymin - 2 * y_center)
            / (max_lat - min_lat))


def lon2canvasx(lon, min_lon, max_lon, xmin, xmax, x_center):
    """ Project on canvas"""
    lon, min_lon, max_lon = map(lon2x, [lon, min_lon, max_lon])
    return (xmin + x_center + (lon - min_lon) * (xmax - xmin - 2 * x_center)
            / (max_lon - min_lon))


def km2lat_diff(km):
    """km to latitude difference"""
    return float(km) / 10000 * 90
    # 10000 km from equator to pole is divided into 90 degrees


def km2lon_diff(km, lat):
    return km2lat_diff(km) / sin(radians(90 - lat))


def lat_diff2km(lat_diff):
    return float(lat_diff) * 10000 / 90


def lon_diff2km(lon_diff, lat):
    return lon_diff * sin(radians(90 - lat)) * 10000 / 90


def calc_nwse(tp_list):
    max_lat = -90
    max_lon = -180
    min_lat = 90
    min_lon = 180
    for tp in tp_list:
        max_lat = max(max_lat, tp.lat)
        max_lon = max(max_lon, tp.lon)
        min_lat = min(min_lat, tp.lat)
        min_lon = min(min_lon, tp.lon)
    mid_lat = (max_lat + min_lat) / 2
    mid_lon = (max_lon + min_lon) / 2
    return {'min': {'lat': min_lat, 'lon': min_lon},
            'max': {'lat': max_lat, 'lon': max_lon},
            'mid': {'lat': mid_lat, 'lon': mid_lon}}


class KML(object):
    """Output class for KML"""

    def __init__(self):
        self.heading_level = 0
        self.stamp = ""

    def doc_header(self, doc_name):
        self.stamp = "Copyright green-elk.com %s" % strftime("%d.%m.%Y %H:%M")

        k = """\
<?xml version="1.0" ?>
<kml xmlns="http://www.opengis.net/kml/2.2"\
 xmlns:kml21="http://earth.google.com/kml/2.1">
<!-- %s -->\n
<Document><name>%s</name>\n\n"""
        return k % (self.stamp, doc_name)

    @staticmethod
    def doc_footer():
        return ("</Document><!-- %s -->\n</kml>\n" %
                "-")  # self.logger.lib.response_time()

    def _indent(self):
        return "  " * self.heading_level

    def visibility_0(self, visibility):
        # visibility = 0 => don't show
        return ("" if visibility is None else
            "%s<visibility>%s</visibility>\n" % (self._indent(), visibility))

    def begin_section(self, heading, visibility=None, comment=""):
        self.heading_level += 1

        h = "%s<Folder><name>%s</name>%s%s\n"
        comment = "<!--KML.begin_section %s %s -->" % (self.heading_level,
                                                       comment)
        return h % (self._indent(), heading, self.visibility_0(visibility),
                    comment)

    def end_section(self, comment=""):
        blanks = self._indent()
        comment = "<!--KML.end_section %s %s -->" % (self.heading_level,
                                                     comment)
        self.heading_level -= 1
        return "%s</Folder>%s\n" % (blanks, comment)

    def placemark_header(self, name="Placemark name", visibility=None):
        # visibility = 0 => don't show
        h = "%s<Placemark><name>%s</name>%s\n"
        return h % (self._indent(), name, self.visibility_0(visibility))

    def placemark_footer(self):
        return "%s</Placemark>\n" % self._indent()

    def linestyle_header_footer(self, color="ff0000ff", width=4):
        h = "%s<Style><LineStyle><color>%s</color>"
        h += "%s<width>%s</width></LineStyle></Style>\n"
        return h % (self._indent(), color, self._indent(), width)

    @staticmethod
    def linestring_pure_header():
        return "<LineString><tessellate>1</tessellate><coordinates>\n"

    def linestring_header(self, color="ff0000ff", width=4, visibility=None):
        h = "<Style><LineStyle><color>%s</color>"
        h += "<width>%s</width></LineStyle></Style>\n"
        h += "   <LineString><tessellate>1</tessellate>%s<coordinates>\n"
        return h % (color, width, self.visibility_0(visibility))

    @staticmethod
    def linestring_footer():
        return "</coordinates></LineString>\n"

    @staticmethod
    def point_header_footer(coordinates, icon_url, label_scale=0.5,
                            icon_scale=1, label_color="FFFFFFFF"):
        h = """<Style><LabelStyle><scale>%s</scale></LabelStyle>
     <IconStyle><color>%s</color><scale>%s</scale>
       <Icon><href>%s</href></Icon></IconStyle></Style>
    <Point><coordinates>%s</coordinates></Point>\n"""
        return h % (label_scale, label_color, icon_scale, icon_url,
                    coordinates)

    @staticmethod
    def placemark_description(descr):
        return "<description><![CDATA[%s]]></description>\n" % descr

    @staticmethod
    def multigeometry_header():
        """Can contain many <LineString> tags (not usable in Google Maps)"""
        return "<MultiGeometry>\n"

    @staticmethod
    def multigeometry_footer():
        return "</MultiGeometry>\n"