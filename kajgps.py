#!/usr/bin/env python
# -*- coding: latin-1 -*-

"""
Geodata analysis of tracks; management of placemarks

External usage: kajgps -i=stdin -ifmt=gpx -o=stdout -ofmt=json -log=logfile
"""

from math import degrees, atan, atan2, log10, sqrt

import datetime
import codecs
import sys
import os
import csv
import importlib
import json

from kajlib import logged
from kajhtml import tr, td, tdr, red
import kajgeo as geo
import kajfmt as fmt
import kajlib as lib
import kajhtml
import kajsvg

if sys.version_info < (3,):
    range = xrange


class Point(object):
    """Pure coordinates without time stamp"""

    def __init__(self, lat, lon, alt=0.0, text=None):
        self.lat = float(lat)  # 60.19358
        self.lon = float(lon)  # 21.90803
        if alt == "":
            alt = 0
        alt = float(alt)
        self.alt = int(alt) if int(alt) == alt else alt
        self.text = text

    def __repr__(self):
        alt = "" if self.alt == 0 else ", alt=%s" % self.alt
        text = "" if self.text is None else ", text='%s'" % self.text
        return "Point(lat=%s, lon=%s%s%s)" % (self.lat_5(), self.lon_5(), alt,
                                              text)

    def __str__(self):
        return self.lat_lon_dms()

    def as_dict(self):  # Point as dictionary
        return dict(lat=self.lat, lon=self.lon, alt=self.alt, text=self.text)

    def as_coordinate_tag(self):  # 21.907574,60.196811,0
        return "%s,%s,%s " % (self.lon_5(), self.lat_5(), self.alt)

    def as_geojson_coordinate(self):  # [21.90757, 60.19681]
        return "[%s, %s]" % (self.lon_5(), self.lat_5())

    def as_json_coordinate(self):
        """ [{ "lat": 60.1801, "lon": 22.0633, "point_type": "trackpoint"}]"""
        return ('[{ "lat": %s, "lon": %s, "point_type": "trackpoint"}]' %
                (self.lat_5(), self.lon_5()))

    def lat_5(self):  # At most 5 decimals (6th decimal < 1 metre)
        return "{:.5f}".format(self.lat)

    def lon_5(self):  # At most 5 decimals (6th decimal < 1 metre)
        return "{:.5f}".format(self.lon)

    def lat_dms(self):  # 60°11′35″N
        return geo.lat_dms_fmt(self.lat)

    def lon_dms(self):  # 21°54′25″Ö
        return geo.lon_dms_fmt(self.lon)

    def lat_lon_dms(self):
        return self.lat_dms() + " " + self.lon_dms()

    def distance(self, other_point):  # in km as float
        return geo.distance(self.lat, self.lon,
                            other_point.lat, other_point.lon)

    def dist_km(self, other_point):  # Example: 12,3 km
        return fmt.km(self.distance(other_point))

    def dist_m(self, other_point):  # Example: 12.345 m
        return fmt.m(self.distance(other_point))

    def direction(self, other_point):  # in degrees as float
        return geo.bearing(self.lat, self.lon,
                           other_point.lat, other_point.lon)

    def dir_int(self, other_point):  # Example: 350
        return int(self.direction(other_point) + 0.5)

    def dir_fmt(self, other_point):  # Example: 350°
        return str(self.dir_int(other_point)) + "°"

    def is_same_lat_lon(self, other_point):  # Same position (alt may differ)
        return self.lat == other_point.lat and self.lon == other_point.lon


class Trackpoint(Point):
    """Coordinates with a time stamp"""

    def __init__(self, lat, lon, dateandtime, alt=0.0, text=None):
        super(Trackpoint, self).__init__(lat, lon, alt, text)
        if not isinstance(dateandtime, datetime.datetime):
            if not isinstance(dateandtime, str):
                raise Exception("class Trackpoint __init__: Unknown class %s" %
                                type(datetime).__name__)
            dateandtime = dateandtime.replace("T", " ").replace("Z", " ")
            dateandtime = fmt.datetime_from_ymd_hms(dateandtime)
        self.datetime = dateandtime

    def __repr__(self):
        alt = "" if self.alt == 0 else ", alt=%s" % self.alt
        text = "" if self.text is None else ", text='%s'" % self.text
        return "Trackpoint(lat=%s, lon=%s, datetime='%s %s'%s%s)" % (
            self.lat_5(), self.lon_5(),
            self.date_yymd(), self.time_hms(), alt, text)

    def __str__(self):
        s = (self.date_dmyy() + " " + self.time_hms() + " " +
             Point.__str__(self))
        if self.text is not None:
            s += " " + self.text
        return s

    def as_dict(self):  # Trackpoint as dictionary
        alt = self.alt
        if isinstance(alt, float):
            alt = "{:.1f}".format(alt)
        return {'lat': self.lat_5(), 'lon': self.lon_5(), 'alt': alt,
                'text': self.text, 'date': self.datetime.date(),
                'time': self.datetime.time()}

    def date_yymd(self):  # "2012-11-10"
        return fmt.yymd(self.datetime)

    def date_dmyy(self):  # "09.08.2012"
        return fmt.dmyy(self.datetime)

    def time_hms(self):  # "14:15:16"
        return fmt.hms(self.datetime)

    def time_hm(self):  # "14:15"
        return fmt.hm(self.datetime)

    def seconds(self, other_point):
        return abs(self.datetime - other_point.datetime).total_seconds()

    def speed(self, other_point):  # in km/h
        if self.seconds(other_point) > 0:
            return geo.km_h(self.distance(other_point) * 1000 / 
                            self.seconds(other_point))
        else:
            return 0


class Timepoint(Trackpoint):
    """Statistics for one minute hh:mm (hh:mm:00 until hh:m1:00, \
hh:m1 = one minute later)"""

    def __init__(self, lat, lon, dateandtime, alt=0.0, text=None, **kwargs):
        super(Timepoint, self).__init__(lat, lon, dateandtime, alt, text)
        self.minute = self.time_hm()  # One Timepoint per minute
        self.count = kwargs['count']
        self.distance = kwargs['distance']
        self.hm_up = kwargs['hm_up']
        self.hm_down = kwargs['hm_down']
        self.max_slope_up = kwargs['max_slope_up']
        self.max_slope_down = kwargs['max_slope_down']
        self.max_speed = kwargs['max_speed']
        self.dist_n = kwargs['dist_n']
        self.dist_e = kwargs['dist_e']
        self.dist_s = kwargs['dist_s']
        self.dist_w = kwargs['dist_w']
        self.activity_id = kwargs.get('activity_id', "")
        self.closest_pm = kwargs.get('closest_pm', None)
        self.segment = kwargs.get('segment', None)

    def __repr__(self):
        return str(self)

    def __str__(self):
        text = "" if self.text is None else "/ %s " % self.text
        hm_up = "" if self.hm_up == 0 else "%s m ^ " % int(self.hm_up)
        hm_down = "" if self.hm_down == 0 else "%s m v " % int(self.hm_down)
        max_slope = (self.max_slope_down if abs(self.hm_down) > self.hm_up else
                     self.max_slope_up)
        sep = "/ " if len(hm_up + hm_down) > 0 else ""
        m_n = "" if self.dist_n == 0 else fmt.m(self.dist_n) + " N "
        m_e = "" if self.dist_e == 0 else fmt.m(self.dist_e) + " E "
        m_s = "" if self.dist_s == 0 else fmt.m(self.dist_s) + " S "
        m_w = "" if self.dist_w == 0 else fmt.m(self.dist_w) + " W "
        s = (self.date_dmyy() + " " + self.minute + " " + self.activity_id +
             " (" + fmt.i1000(self.count) + "): " + fmt.m(self.distance) +
             " " + fmt.km(self.max_speed) + "/h " +
             fmt.onedecimal(max_slope) + "° ")
        return s + text + "/ " + hm_up + hm_down + sep + m_n + m_e + m_s + m_w

    def as_dict(self):  # Trackpoint as dictionary
        return {'minute': self.minute, 'date': self.datetime.date(),
                'time': self.datetime.time(), 'lat': self.lat_5(),
                'lon': self.lon_5(), 'alt': self.alt, 'text': self.text,
                'count': self.count, 'distance': self.distance,
                'max_speed': self.max_speed, 'activity_id': self.activity_id,
                'hm_up': self.hm_up, 'hm_down': self.hm_down,
                'max_slope_up': self.max_slope_up,
                'max_slope_down': self.max_slope_down,
                'dist_n': self.dist_n, 'dist_e': self.dist_e,
                'dist_s': self.dist_s, 'dist_w': self.dist_w}


class Placemark(Point):
    """Coordinates with KML Placemark like functionality and more"""

    def __init__(self, placemark, lat, lon, **kwargs):

        alt = kwargs.get('alt', 0.0)
        placetype_id = kwargs.get('placetype_id', '')
        text = ("%s (%s m)" % (placemark, alt) if placetype_id == "mountain"
                else placemark)

        Point.__init__(self, lat, lon, alt, text)
        self.placetype_id = placetype_id
        self.descr = kwargs.get('descr', '')
        self.order_user = kwargs.get('order_user', 0)
        self.folder = kwargs.get('folder', '')
        self.folder = ("*" + self.folder).split("*")[-1]
        # Skips levels prior to first "*" occurrence
        self.sub_area = self.folder.split("|")[0]
        # Picks "Portugal" from "Europe|*Portugal|Lisbon"
        sub_area_dict = _areas.get(self.sub_area, {})
        self.order_area = sub_area_dict.get('order_area', 0)
        self.order_sub_area = sub_area_dict.get('order_sub_area', 0)
        self.area = sub_area_dict.get('area', '')
        if self.area == "" and self.sub_area != "":
            userbug.add("Missing area for %s" % self.sub_area)
        self.folder = self.area + "|" + self.folder
        self.prominence = int(kwargs.get('prominence', 10))
        self.dynamic = kwargs.get('dynamic', False)
        self.color = kwargs.get('color', 'red')

        self.placetype = {'id': placetype_id, 'category': 'missing',
                          'url': '', 'svg': '',
                          'color': 'red', 'prominence': 9, 'terra': ''}
        self.has_valid_placetype = _placetypes.exists(self.placetype_id)
        if self.has_valid_placetype:
            p = _placetypes[self.placetype_id]
            prominence = 10 if p.prominence == "" else p.prominence
            self.placetype = {'id': placetype_id, 'category': p.category,
                              'url': p.url, 'svg': p.svg,
                              'color': p.color,
                              'prominence': int(prominence),
                              'terra': p.terra}
        self.tot_prominence = self.prominence + self.placetype['prominence']

    def __repr__(self):
        r = "Placemark(lat=" + self.lat_5() + ", lon=" + self.lon_5()
        r += ', placemark="' + str(self.text) + '", placetype_id="'
        r += str(self.placetype_id) + '", folder="' + str(self.folder) + '")'
        return r

    def __str__(self):
        s = self.text + ', ' + self.placetype_id + ", " + self.folder + ", "
        s += self.descr + ', ' + self.lat_lon_dms()
        return s

    def as_dict(self):  # Placemark as dictionary
        return {'placemark': self.text, 'placetype_id': self.placetype_id,
                'prominence': self.prominence, 'lat': self.lat_5(),
                'lon': self.lon_5(), 'alt': self.alt, 'folder': self.folder,
                'descr': self.descr, 'color': self.placetype['color']}

    def as_kml(self, with_descr=False):  # Placemark as kml
        k = kml.placemark_header(self.text).replace("&", "&amp;")
        icon_url = self.placetype['url']
        color = self.placetype['color']
        label_scale = 1 if self.prominence < 5 else 0.5
        k += kml.point_header_footer(self.as_coordinate_tag(),
                                     icon_url, label_scale=label_scale,
                                     label_color=color)
        if with_descr:
            k += kml.placemark_description(self.descr)
        k += kml.placemark_footer()
        return k

    def as_terra_gpx(self):
        id_ = _placetypes[self.placetype_id]
        # return gpx.terra(self.lat, self.lon, self.text, time="",
        # desc=self.descr, cmt=id.terra)

    def as_html(self, with_placetype_id=True, brief=True):
        td_placetype = td(self.placetype_id) if with_placetype_id else ""
        tot_prominence = "%s + %s = %s" % (self.prominence,
                            self.placetype['prominence'], self.tot_prominence)
        optional = "" if brief else (td(self.lat_5()) + td(self.lon_5())
                                     + tdr(self.alt) + td(self.descr))
        s = tr(td(self.text) + td_placetype + td(tot_prominence) +
             td(self.folder) + optional)
        return s

    def as_js(self):
        id_ = self.text.replace(" ", "")
        placetype = _placetypes[self.placetype_id]
        color = placetype.awecolor
        symbol = placetype.awesome
        s = '''\t\t{
            "geometry": {
                "coordinates": [
                    %s,
                    %s,
                    0
            ],
            "type": "Point"
            },
            "id": "id%s",
            "properties": {
                "description": "%s",
                "id": "pid%s",
                "marker-color": "%s",
                "marker-size": "2",
                "marker-symbol": "%s",
                "name": "%s",
                "title": "%s"
            },
            "type": "Feature"
        }''' % (self.lon_5(), self.lat_5(), id_, self.text, id_, color, symbol,
                self.text, self.text)
        return s

    def by_prominence(self):
        return self.tot_prominence

    def by_category(self):
        return (self.placetype['category'] + self.placetype_id +
                str(10 + self.tot_prominence) + self.text)

    def by_hierarchy(self):
        return self.order_sub_area * 10000 + self.order_user

    def by_lon(self):
        return self.lon

    def inside(self, p1, p2):
        if self.lat < p1.lat:
            return False
        if self.lat > p2.lat:
            return False
        if self.lon < p1.lon:
            return False
        if self.lon > p2.lon:
            return False
        return True


class Placetypes(lib.Config):
    """Commonalities of Placemarks of the same kind"""
    @staticmethod
    def img_url(url, size=40):
        h = '<img height="%s" width="%s" src="%s"/>' % (size, size, url)
        return "" if url == "" else h

    @staticmethod
    def svg_img_with_text(svg_icon, size=40):
        h = (Placetypes.img_url(Placetypes._svg_src(svg_icon), size=size)
             + " " + svg_icon)
        return "" if svg_icon == "" else h

    @staticmethod
    def _svg_src(svg_icon):
        return "file://" + os.path.join(_icon_dir, svg_icon + ".svg")

    def img(self, placetype, size=40):
        return self.img_url(placetype.url, size)

    def svg_img(self, placetype, size=40):
        url = self._svg_src(placetype.svg)
        return "" if placetype.svg == "" else self.img_url(url, size)


class Places(object):
    """Collection of Placemark objects"""

    def __init__(self, infile, **kwargs):
        self.pm_list = []
        self.name_dict = {}
        self.filename = infile
        self.kwargs = kwargs
        self.kwargs['infile'] = infile
        create_empty_collection = infile is None
        if create_empty_collection:
            return
        copy_other_collection = infile == "copy"
        if copy_other_collection:
            self._copy()
            return
        file_exists = os.path.isfile(infile)
        if not file_exists:
            raise Exception("class Places __init__: File %s not found " %
                            infile)
        file_type = infile.split(".")[-1]
        if file_type == 'csv':
            self._import_csv(infile)
        elif file_type == 'kml':
            self._import_kml(infile)
        else:
            raise Exception("class Places __init__: Unknown file_type " +
                            file_type)
        if self.kwargs.get('mode') != "edit":
            self.sort_by_prominence()
            self._create_name_dict()

    def __repr__(self):  # Unambiguous, from command line
        r = "Places('%s') # %s places" % (self.filename, self.count())

        for i, pm in enumerate(self):
            if i > 5:
                r += "  ..."
                break
            r += lib.indent(repr(pm), 2)
        return r

    def __str__(self):  # Readable, in program
        s = "%s placemarks from %s:" % (self.count(), self.filename)
        for i, pm in enumerate(self):
            if i > 20:
                s += "  ..."
                break
            s += lib.indent(str(pm), 2)
        return s

    def __format__(self, fmt_):
        if fmt_ == 'kml':
            return self.as_kml()
        elif fmt_ == 'html':
            return self.as_html()
        elif fmt_ == 'svg':
            return self.as_svg()

    def __getitem__(self, index):
        if isinstance(index, int):
            return self.pm_list[index]
        elif isinstance(index, str):
            i = self.name_dict[index]
            return self.pm_list[i]
        raise Exception("Unknown Places[] index type %s" %
                        type(index).__name__)

    def _create_name_dict(self):
        for i, pm in enumerate(self.pm_list):
            self.name_dict[pm.text] = i

    def count(self):
        return len(self.pm_list)

    def _import_csv(self, filename):
        with open(filename) as csvfile:
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                first_field = row['placemark']
                is_blank = len(first_field.strip()) == 0
                is_comment = (first_field + " ")[0] == "#"
                if not (is_blank or is_comment):
                    row['order_user'] = i
                    pm = Placemark(**row)
                    self.pm_list.append(pm)

    def _import_kml(self, filename):
        f = codecs.open(filename, 'r')
        # <Placemark>
        # <name>Allensbach</name>
        # <coordinates>9.066292622335864,47.7171522081462,0</coordinates>
        # </Placemark>
        i = 0
        is_line_string = False
        f_lat = f_lon = f_name = f_alt = ""
        folder_level = 0
        folder_or_placemark = ""
        folders = [''] * 6
        placetype_id = f_folder = ""  # Just to shut up warnings
        for line in f:
            has_folder = '<Folder>' in line or '<Document>' in line
            eof_folder = '</Folder>' in line or '</Document>' in line
            has_placemark = 'Placemark>' in line
            eof_placemark = '</Placemark>' in line
            has_name = '<name>' in line
            has_coordinates = '<coordinates>' in line
            has_placetype = '<styleUrl>' in line
            if has_folder:
                folder_level += 1
                folder_or_placemark = "folder"
            if eof_folder:
                folder_level -= 1
            if has_placemark:
                folder_or_placemark = "placemark"
            if has_name:
                tag_value = line.replace(">", "<").split('<')[2]
                if folder_or_placemark == 'folder':
                    f_folder = tag_value + " " + str(folder_level)
                    folders[folder_level] = tag_value
                    f_folder = "|".join(folders[0:folder_level + 1]).strip("|")
                else:  # placemark
                    f_name = tag_value.replace('&apos;', "'")
            if has_placetype:
                placetype_id = line.replace(">", "<").split('<')[2].strip("#")
            if has_coordinates:
                is_line_string = False
                has_comma = ',' in line
                if not has_comma:
                    is_line_string = True
                else:
                    line = line.replace(">", "<").split('<')[2].split(',')
                    f_lon, f_lat, f_alt = line
            if eof_placemark:
                if not is_line_string:
                    i += 1
                    pm = Placemark(lat=f_lat, lon=f_lon, placemark=f_name,
                                   alt=f_alt, placetype_id=placetype_id,
                                   folder=f_folder, order_user=i)
                    self.pm_list.append(pm)  # no folder known

    def add(self, pm):  # Add an individual Placemark object
        self.pm_list.append(pm)

    def _copy(self):
        original = self.kwargs.get('original')
        forced_breaks = self.kwargs.get('forced_breaks')
        p1 = self.kwargs.get('p1')
        p2 = self.kwargs.get('p2')

        if original is not None:
            for pm in original:
                if pm.inside(p1, p2):
                    self.add(pm)
        elif forced_breaks is not None:
            for fb in forced_breaks:
                pm = Placemark(fb.text, fb.lat, fb.lon)
                if pm.inside(p1, p2):
                    self.add(fb)

    def as_kml(self, with_descr=False):  # Places as kml
        k = kml.doc_header(self.filename)
        self.sort_by_hierarchy()
        i_folder_count = levels_now = i_common_levels = 0
        previous_folder = ""
        for pm in self.pm_list:
            folder_has_changed = (pm.folder != previous_folder)
            if folder_has_changed:
                last_folder_level = ("|" + pm.folder).split("|")[-1]
                if len(previous_folder) > 0:
                    levels_previous = len(previous_folder.split("|"))
                else:
                    levels_previous = 0
                levels_now = len(pm.folder.split("|"))
                i_common_levels = 0
                for i_folder in range(0, min(levels_previous, levels_now)):
                    if previous_folder.split("|")[i_folder] == \
                            pm.folder.split("|")[i_folder]:
                        i_common_levels += 1
                    else:
                        break
                # </close> levelsPrevious-iCommonLevels "old" folders
                for i_folder in range(0, levels_previous - i_common_levels):
                    k += kml.end_section("i_f %s / l_p-i_c %s-%s" % (i_folder, 
                                            levels_previous, i_common_levels))
                # <open> levels_now-i_common_levels "new" folders
                for i_folder in range(0, levels_now - i_common_levels):
                    k += kml.begin_section(pm.folder.split("|")[
                                        i_common_levels + i_folder],
                        comment=("i_c_l %s i_f %s" % 
                                 (i_common_levels, i_folder)))
                    i_folder_count += 1
            k += pm.as_kml(with_descr)
            previous_folder = pm.folder
        for i_folder in range(0, levels_now):
            k += kml.end_section("as_kml i_folder %s" % i_folder)
        k += kml.doc_footer()
        return k

    def as_html(self):
        self.sort_by_category()
        html.set_title_desc(self.kwargs['header'], self.kwargs['infile'])
        h = html.doc_header()
        h += html.start_table(column_count=3)
        last_category = last_placetype_id = ""
        for pm in self.pm_list:
            placetype_id = pm.placetype_id
            category = pm.placetype['category']
            if category != last_category:
                h += html.h3(category)
            if placetype_id != last_placetype_id:
                h += html.h4(placetype_id)
            h += pm.as_html(with_placetype_id=False)
            last_category = category
            last_placetype_id = placetype_id
        h += html.end_table()
        h += html.doc_footer()
        self.sort_by_prominence()
        return h

    def as_svg(self):

        if os.path.exists(_svg_icon_file):
            with codecs.open(_svg_icon_file) as f:
                svg_icons = f.read()
        else:
            userbug.add("Track as_svg missing icons file %s" % _svg_icon_file)
            svg_icons = ""

        title = self.kwargs['header']
        desc = fmt.current_timestamp()

        svg.empty_canvas()

        fixed = {'mid_lat': float(self.kwargs['lat']),
                 'mid_lon': float(self.kwargs['lon']),
                 'width_km': float(self.kwargs['km']),
                 'orientation': self.kwargs['mode']}
        svg_map = SVGMap(svg, fixed=fixed)
        svg.set_title(title, desc)
        s = ""
        s += svg.doc_header(more_defs=svg_icons)
        s += svg_map.svg_comment
        s += svg_map.draw_map_frame()
        s += svg_map.plot_map_grid(svg_map.spread_km)
        s += svg_map.draw_header(title, desc)
        s += svg_map.plot_scale()
        s += svg_map.draw_placemarks(self)
        #s += svg_map.svg.draw_pixels()  # for tracing non-printing of texts
        s += svg.doc_footer()
        return s

    #def as_terra_gpx(self):
        # g = gpx.doc_header("Terra Maps")
        #for pm in self.pm_list:
            #g += pm.as_terra_gpx()
            #g += gpx.doc_footer()
            #return g

    def as_js(self):
        js = '''wholefoods_json = {
    "features": [\n'''
        for pm in self.pm_list:
            js += pm.as_js() + ",\n"
        js = js.strip(",\n")
        js += "\n\t]\n}"
        return js

    def save_as(self, filename, extended=False):
        file_format = filename.split(".")[-1]
        if file_format == 'csv':
            self.save_as_csv(filename)
            return
        if file_format == 'kml':
            a_str = self.as_kml(extended)
        elif file_format == 'svg':
            a_str = self.as_svg()
        elif file_format == 'html':
            a_str = self.as_html()
        elif file_format == 'js':
            a_str = self.as_js()
        else:
            raise Exception("Unknown format %s" % str(file_format))
        lib.save_as(filename, a_str, verbose=True)

    def save_as_csv(self, filename):
        with open(filename, 'w') as csvfile:
            fieldnames = ['placemark', 'descr', 'placetype_id', 'prominence',
                          'lat', 'lon', 'alt', 'folder', 'color']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            h1, h2 = self._csv_header_instructions(filename)
            csvfile.write("\n%s\n%s\n" % (h1, h2))
            for placemark in self.pm_list:
                writer.writerow(placemark.as_dict())
            print("Wrote %s" % filename)

    def _csv_header_instructions(self, filename):
        count = len(self.pm_list)
        return lib.csv_header_instructions(count, 'placemark', filename)

    def closest_placemark(self, point):
        dist = 99999
        if self.count() == 0:
            empty = Placemark("-", -point.lat, (180+point.lon))
            return empty
            #raise Exception("closest_placemark: 0 placemarks to compute from.")
        closest_pm = self.pm_list[0]
        for pm in self.pm_list:
            if pm.dynamic:
                continue
            dist_pm = pm.distance(point)
            if dist_pm < dist:
                dist = dist_pm
                closest_pm = pm
        return closest_pm

    def sort_by_prominence(self):
        self.pm_list.sort(key=Placemark.by_prominence)

    def sort_by_category(self):
        self.pm_list.sort(key=Placemark.by_category)

    def sort_by_hierarchy(self):
        self.pm_list.sort(key=Placemark.by_hierarchy)

    def sort_by_lon(self):
        self.pm_list.sort(key=Placemark.by_lon)

class Tracklist(object):
    """Collection of Tracks, usually in one directory"""
    def __init__(self, infile, **kwargs):
        self.track_base_dir = infile
        kwargs['infile'] = infile
        self.kwargs = kwargs
        self.mode = kwargs.get('mode', 'skim')
        self.outfile = kwargs.get('outfile', "")
        self.activity_id = kwargs.get('activity', 'run')
        header = kwargs.get('header', "Track diary %datetime")
        self.header_nostamp = header.replace('%timestamp', '')
        self.header = header.replace('%timestamp', fmt.current_timestamp())
        self.parameters = kwargs.get('parameters', "")
        self.min_km = kwargs.get('km', '')
        self.min_date = datetime.datetime.min
        self.max_date = datetime.datetime.min
        self.map_area = {}
        self.tracks = []
        self.segments = []
        self.seg_dicts = []
        self.missing_placemarks = []

        # if _debug_object == "Tracklist":
        self._scan_hd(self.track_base_dir, self.mode)

    def __str__(self):
        s = "Tracklist %s mode %s tracks %s segments %s"
        return s % (self.track_base_dir, self.mode, len(self.tracks),
                    len(self.segments))

    @logged
    def _scan_hd(self, dir_, mode):
        file_extensions = tuple([".gpx", ".CSV", ".csv"])
        i = 0
        for directory, dirs, files in os.walk(dir_):
            for just_filename in files:
                if just_filename.endswith(file_extensions):
                    full_filename = os.path.join(directory, just_filename)
                    i += 1
                    track = Track(full_filename, mode=mode, diary=self)
                    if track.count() == 0:
                        continue
                    track_dict = track.as_dict()
                    if i == 1:
                        self.min_date = track.date
                        self.max_date = track.date
                    self.min_date = min(self.min_date, track.date)
                    self.max_date = max(self.max_date, track.date)
                    track_dict['track'] = track
                    self.tracks.append(track_dict)
                    if mode == "segments":
                        for segment in track.segments:
                            seg_dict = segment.as_dict()
                            self.segments.append(seg_dict)
        self._calc_nwse()
        self._calc_values()
        if mode != "segments":
            self._sort_tracks(self.parameters)
        else:
            self.segments.sort(key=lambda x: x['date'])
            self._calc_activity_stats()

    def _calc_nwse(self):
        max_lat = -90
        max_lon = -180
        min_lat = 90
        min_lon = 180
        for track_dict in self.tracks:
            map_area = track_dict['track'].map_area
            max_lat = max(max_lat, map_area['max']['lat'])
            max_lon = max(max_lon, map_area['max']['lon'])
            min_lat = min(min_lat, map_area['min']['lat'])
            min_lon = min(min_lon, map_area['min']['lon'])
        mid_lat = (max_lat + min_lat) / 2
        mid_lon = (max_lon + min_lon) / 2
        self.map_area['min'] = {'lat': min_lat, 'lon': min_lon}
        self.map_area['max'] = {'lat': max_lat, 'lon': max_lon}
        self.map_area['mid'] = {'lat': mid_lat, 'lon': mid_lon}

    def _calc_values(self):
        for track_dict in self.tracks:
            order = self.parameters
            activity_id = self._guess_activity(track_dict)
            activity = _activities[activity_id]
            activity_order = 'Z' if activity is "" else activity.order
            a_dist = track_dict['a_dist']
            track_dict['timezone'] = self._guess_timezone(track_dict)
            track_dict['activity_id'] = activity_id
            track_dict['activity_order'] = activity_order
            track_dict['name'] = self._guess_name(track_dict)
            track_dict['distance'] = "{:.1f}".format(
                                track_dict['a_dist'])
            track_dict['a_dist_fmt'] = fmt.km(track_dict['a_dist'])
            track_dict['comment'] = (track_dict['area'] + ' ' +
                                     track_dict['sub_area'])
            year = track_dict['date'].strftime('%Y')
            month = track_dict['date'].strftime('%Y-%m')
            activity_hdr = (activity_id if activity == "" else
                            activity.order + " " + activity.name)
            a_3 = '1. > 10 km' if a_dist > 10 else '2. < 10 km'
            a_4 = ('1. > 100 km' if a_dist > 100 else
                   '2. > 20 km' if a_dist > 20 else
                   '3. > 10 km' if a_dist > 10 else str(int(a_dist)) + " km")
            lat_3 = lat_4 = track_dict['lat'].split(".")[0]
            lon_3 = lon_4 = track_dict['lon'].split(".")[0]
            lat_3 = "lat " + lat_3[:-1] + "x"
            lon_3 = "lon " + lon_3[:-1] + "x"
            lat_4 = "lat " + lat_4
            lon_4 = "lon " + lon_4
            h3 = (year if order == 'year' else
                  activity_hdr if order == 'activity' else
                  a_3 if order == 'a_dist' else
                  lat_3 if order == 'lat' else
                  lon_3 if order == 'lon' else None)
            h4 = (month if order == 'year' else
                  year if order == 'activity' else
                  a_4 if order == 'a_dist' else
                  lat_4 if order == 'lat' else
                  lon_4 if order == 'lon' else None)
            track_dict['h3'] = h3
            track_dict['h4'] = h4

    def _sort_tracks(self, parameters):
        if parameters == "year":
            self.tracks.sort(key=lambda x: x['date'])
        elif parameters == "activity":
            self.tracks.sort(key=lambda x: x['activity_order'] +
                                           str(x['date']))
        elif parameters == "a_dist":
            self.tracks.sort(key=lambda x: -float(x['a_dist']))
        elif parameters == "lat":
            self.tracks.sort(key=lambda x: float(x['lat']))
        elif parameters == "lon":
            self.tracks.sort(key=lambda x: float(x['lon']))
        else:
            userbug.add("sort_tracks: Unknown order %s" % parameters)

    @logged
    def _calc_activity_stats(self):
        activity_stats = {}
        for seg in self.segments:
            date = seg['date'].strftime('%Y-%m-%d')
            date_hdr = seg['date'].strftime('%d.%m.%Y')
            activity_id = seg['activity_id']
            if activity_stats.get(date) is None:
                activity_stats[date] = {'hdr': date_hdr}
            if activity_stats[date].get(activity_id) is None:
                activity_stats[date][activity_id] = {'count': 1,
                    'km': seg['distance'], 
                    'hm_up': seg['hm_up'], 'hm_down': seg['hm_down']}
            else:
                activity_dict = activity_stats[date][activity_id]
                activity_dict['count'] += 1
                activity_dict['km'] += seg['distance']
                activity_dict['hm_up'] += seg['hm_up']
                activity_dict['hm_down'] += seg['hm_down']
        self.activity_stats = activity_stats

    @logged
    def save_as(self, filename):
        file_format = filename.split(".")[-1]
        if file_format == 'csv':
            self.save_as_csv(filename)
            return
        if file_format == 'kml':
            a_str = self.as_kml()
        elif file_format == 'html':
            a_str = self.as_html()
        elif file_format == 'svg':
            a_str = self.as_svg()
        else:
            create_cache = self.mode == "cache"
            if create_cache:
                if not os.path.exists(filename):
                    os.makedirs(filename)
                self.save_as_trackcache(dir_=filename)
                return
            else:
                raise Exception("Tracklist.save_as unknown format %s" %
                            str(file_format))
        lib.save_as(filename, a_str, verbose=True)

    def save_as_trackcache(self, dir_):
        i = j = dirs = overwrites = 0
        for track_dict in self.tracks:
            track = track_dict['track']

            fieldnames = ['date', 'time', 'lat', 'lon', 'alt', 'text']
            for seg in track.compressed.segments:
                i += 1
                full_dir = os.path.join(dir_, seg.activity_id)
                if not os.path.exists(full_dir):
                    os.makedirs(full_dir)
                    dirs += 1
                filename = Segment.csv_filename(seg.as_dict())
                filename = os.path.join(full_dir, filename)
                if os.path.exists(filename):
                    print("- File %s exists, is being overwritten" % filename)
                    overwrites += 1
                with open(filename, 'w') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    seg_dict = {'date': seg.first['tp'].date_yymd(),
                                'time_start': seg.first['tp'].time_hms(),
                                'time_stop': seg.last['tp'].time_hms(),
                                'activity_id': seg.activity_id,
                                'distance': fmt.onedecimal(seg.distance),
                                'duration': seg.duration_hms(),
                                'speed': fmt.onedecimal(seg.speed()),
                                'hm_up': seg.hm_up,
                                'hm_down': seg.hm_down,
                                'start_dist': fmt.onedecimal(
                                    seg.first['dist']),
                                'name': seg.name(),
                                'infile': self.kwargs['infile'],
                                'max_lat': seg.map_area['max']['lat'],
                                'min_lat': seg.map_area['min']['lat'],
                                'max_lon': seg.map_area['max']['lon'],
                                'min_lon': seg.map_area['min']['lon'],
                                'count': fmt.i1000(len(seg)),
                                }
                    track.diary.seg_dicts.append(seg_dict)
                    h1, h2 = Segment.csv_header_instructions(filename,
                                                             seg_dict)
                    csvfile.write("\n%s\n%s\n" % (h1, h2))
                    for trackpoint in seg:
                        writer.writerow(trackpoint.as_dict())
        print("Saved %s points in %s csv files; %s overwritten, %s new dirs" %
              (j, i, overwrites, dirs))

        filename = os.path.join(dir_, 'ge_segments.csv')
        comment = self.track_base_dir
        Segment.save_as_csv(filename, self.seg_dicts, comment)

    @logged
    def save_as_csv(self, filename):
        skim_fields = 'date activity_id timezone name distance lat lon comment'
        diary_fields = ('hm_to_hm activity_id name area a_dist_fmt ' +
                       'dist_fmt duration_hm speed_fmt')
        placemark_fields = 'lat lon alt placetype_id prominence placemark'

        seg_fields = 'date hm_to_hm name distance duration speed'
        time_fields = 'date time activity_id comment'.split()
        fields = (skim_fields if self.mode == "skim" else
                  diary_fields if self.mode == "diary" else
                  placemark_fields if self.mode == "missing" else seg_fields)
        fields = fields.split()

        if self.mode in ['skim', 'diary', 'segments']:
            with open(filename, 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fields)
                writer.writeheader()
                min_hdr = ("- min %s" % self.min_km if self.min_km is not None
                           else "")
                h2 = "Tracklist dir %s mode %s (%s track files) %s" % (
                    self.track_base_dir, self.mode, len(self.tracks), min_hdr)
                csvfile.write("\n# %s\n\n# %s\n" % (self.header, h2))
                prev_h3 = prev_h4 = ""
                i = 0
                for track_dict in self.tracks:
                    if self.mode != 'skim':
                        dist = track_dict['distance']
                        if self.min_km is not None:
                            if dist < self.min_km:
                                continue
                    h3 = track_dict['h3']
                    h4 = track_dict['h4']
                    if h3 != prev_h3:
                        csvfile.write("\n# %s\n" % h3)
                    if h4 != prev_h4:
                        csvfile.write("\n#   %s\n" % h4)
                    track_dict = {pick: track_dict.get(pick)
                                  for pick in fields}
                    writer.writerow(track_dict)
                    i += 1
                    prev_h3 = h3
                    prev_h4 = h4

                print("%s rows saved into file %s" % (i, filename))
                csvfile.write("\n\n# Response time: " + lib.response_time())
                csvfile.write("\n\n# Log: " + lib.log_rpt())

        if self.mode in ['segments']:
            with open(filename, 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fields)
                writer.writeheader()
                min_hdr = ("- min %s" % self.min_km if self.min_km is not None
                           else "")
                h2 = "Tracklist dir %s mode %s (%s track files) %s" % (
                    self.track_base_dir, self.mode, len(self.tracks), min_hdr)
                csvfile.write("\n# %s\n\n# %s\n" % (self.header, h2))
                prev_date = ""
                i = 0
                for row in self.segments:
                    dist = row['distance']
                    # if self.min_km is not None:
                    #    if dist < self.min_km:
                    #        continue
                    date = row['date']
                    if date != prev_date:
                        csvfile.write("\n# %s\n" % date)
                    writer.writerow(row)
                    i += 1
                    prev_date = date

                print("%s rows saved into file %s" % (i, filename))
                csvfile.write("\n\n# Response time: " + lib.response_time())
                csvfile.write("\n\n# Log: " + lib.log_rpt())

        if self.mode in ['missing']:
            with open(filename, 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fields)
                writer.writeheader()
                h2 = "Dynamic placemarks dir %s (%s track files)" % (
                    self.track_base_dir, len(self.tracks))
                csvfile.write("\n# %s\n\n# %s\n" % (self.header, h2))
                i = 0
                for pm in self.missing_placemarks:
                    row = {'lat': pm.lat_5(), 'lon': pm.lon_5(),
                           'alt': int(pm.alt), 'placetype_id': pm.placetype_id,
                           'placemark': pm.text, 'prominence': pm.prominence}
                    writer.writerow(row)
                    i += 1
                print("%s rows saved into file %s" % (i, filename))
                csvfile.write("\n\n# Response time: " + lib.response_time())
                csvfile.write("\n\n# Log: " + lib.log_rpt())

    @staticmethod
    def _has_date_entry(date):
        if _day_metadata is not None:
            if not isinstance(_day_metadata[date], str):
                return True
        return False

    @staticmethod
    def _guess_name(track_dict):
        date = str(track_dict['date'])
        if Tracklist._has_date_entry(date):
            return _day_metadata[date].name
        filename = os.path.split(track_dict['filename'])[1]
        filename = fmt.no_0123456789(filename)
        for suffix in ['.gpx', '.csv', '.CSV']:
            filename = filename.replace(suffix, "")
        filename = filename.replace("-", " ").replace("_", " ").strip()
        return "? %s" % filename

    @staticmethod
    def _guess_activity(track_dict):
        date = str(track_dict['date'])
        if Tracklist._has_date_entry(date):
            return _day_metadata[date].activity_id
        dir_ = os.path.split(track_dict['filename'])[0]
        activity_id = dir_.split(os.path.sep)[-1]
        return "? %s" % activity_id

    @staticmethod
    def _guess_timezone(track_dict):
        date = str(track_dict['date'])
        if Tracklist._has_date_entry(date):
            return _day_metadata[date].timezone
        return "? 60"

    @logged
    def as_kml(self):
        hdr = self.header + " " + self.track_base_dir
        k = kml.doc_header(hdr)
        is_first_h3 = is_first_h4 = True

        prev_h3 = prev_h4 = ""
        for track in self.tracks:
            dist = track['a_dist']
            #if self.min_km is not None:
            #    if dist < self.min_km:
            #       continue
            activity_id = track['activity_id']
            h3 = track['h3'].replace("<", "&lt;")
            h4 = track['h4'].replace("<", "&lt;")
            if h3 != prev_h3:
                if not is_first_h3:
                    k += kml.end_section('h4 %s' % prev_h4)
                    k += kml.end_section('h3 %s' % prev_h3)
                k += kml.begin_section(h3, comment="h3")
                prev_h4 = ""
                is_first_h4 = True
                is_first_h3 = False
            if h4 != prev_h4:
                if not is_first_h4:
                    k += kml.end_section('h4 %s' % prev_h4)
                k += kml.begin_section(h4, comment="h4")
                is_first_h4 = False
            track_name = "{date} {name} "
            track_name = track_name.format(**track)
            k += kml.placemark_header(track_name)
            placetype = _placetypes[activity_id]
            if placetype == "":
                placetype = _placetypes['start']
            iconurl = placetype.url
            img_src = '<img src="%s" height=15 width=15>' % iconurl
            color = placetype.color
            coordinate_tag = "{lon},{lat}".format(**track)
            k += kml.point_header_footer(coordinate_tag, iconurl,
                                                     label_color=color)
            track_desc = "<p>{time} {activity_id} %s" % img_src
            track_desc += "<p>Closest point: {area} {a_dist_fmt}"
            track_desc += "<p>Filename: {filename}"
            track_desc = track_desc.format(**track)
            k += kml.placemark_description(track_desc)
            k += kml.placemark_footer()
            prev_h3 = h3
            prev_h4 = h4

        k += kml.end_section("h4 %s" % prev_h4)
        k += kml.end_section("h3 %s" % prev_h3)

        k += kml.doc_footer()
        return k

    @logged
    def as_kml_g(self):
        hdr = self.header + " " + self.track_base_dir
        k = kml.doc_header(hdr)
        is_first_header = True

        # Tracks
        prev_month = ""
        for track in self.tracks:
            dist = track['a_dist']
            if self.min_km is not None:
                if dist < self.min_km:
                    continue
            month = track['date'].strftime('%Y-%m')
            if month != prev_month:
                if not is_first_header:
                    k += kml.end_section(month)
                k += kml.begin_section(month, comment="month")
                is_first_header = False
            # Format track as KML
            track_name = "{parent} / {area} {a_dist_fmt} - {date} {time}"
            track_name = track_name.format(**track)
            k += kml.placemark_header(track_name) # todo var rk =
            placetype = _placetypes['startpunkt']
            iconurl = placetype.url
            color = placetype.color
            coordinate_tag = "{lon},{lat}".format(**track)
            k += kml.point_header_footer(coordinate_tag, iconurl,
                                                     label_color=color)
            k += kml.placemark_description(track['filename'])
            k += kml.placemark_footer()
            prev_month = month
        k += kml.end_section("last")

        # Segments
        is_first_header = True
        prev_day = ""
        for seg in self.segments:
            start_dist = seg['start_dist']
            if self.min_km is not None:
                if start_dist < self.min_km:
                    continue
            day = seg['date'].strftime('%d.%m.%Y')
            if day != prev_day:
                if not is_first_header:
                    k += kml.end_section(day)
                k += kml.begin_section(day, comment="day")
                is_first_header = False
            # Format row as KML
            seg_name = "{km} ({speed}) {distance} - {name} {date}"
            seg_name = seg_name.format(km=fmt.km(seg['start_dist']), **seg)
            rk = kml.placemark_header(seg_name)
            placetype = _placetypes['gepause']
            iconurl = placetype.url
            color = placetype.color
            coordinate_tag = "{lon},{lat}".format(**seg)
            k += kml.point_header_footer(coordinate_tag, iconurl,
                                                     label_color=color)
            # k += placemark_description(day)
            k += kml.placemark_footer()
            prev_day = day
        k += kml.end_section("last")

        k += kml.doc_footer()
        return k

    @logged
    def as_html(self):
        html.set_title_desc(self.header, self.track_base_dir)
        h = html.doc_header()

        skim_fields = 'activity_id timezone name a_dist_fmt lat lon comment'
        full_fields = ('hm_to_hm activity_id name area a_dist_fmt ' +
                       'dist_fmt duration_hm speed_fmt')
        fields = skim_fields if self.mode == "skim" else full_fields
        fields = fields.split()
        h += html.start_table(column_count=len(fields) + 1)
        space_row = '   <tr><td><span class="space">&nbsp;</span></td></tr>\n'

        row = kajhtml.th("date")
        for field in fields:
            if "_fmt" in field or field in ['lat', 'lon']:
                row += kajhtml.thr(field.replace("_fmt", ""))
            else:
                row += kajhtml.th(field)
        h += tr(row)

        prev_day = ""
        prev_h3 = prev_h4 = ""
        for track in self.tracks:
            dist = track['a_dist']
            #if self.min_km is not None:
            #    if dist < self.min_km:
            #        continue
            day = track['date'].strftime('%d.%m.%Y')
            day_blank = day if day != prev_day else ""
            h3 = track['h3']
            h4 = track['h4']
            if h3 != prev_h3:
                h += html.h3(h3)
            if h4 != prev_h4:
                h += html.h4(h4)
            row = td(day_blank)
            for field in fields:
                value = track.get(field)
                if value is None:
                    row += td(red('None'))
                    continue
                if "?" in value:
                    value = red(value)
                if "km" in value and dist > 10:
                    value = red(value)
                if field == "activity_id" and not "?" in value:
                    value = Placetypes.svg_img_with_text(value, size=15)
                if "_fmt" in field or field in ['lat', 'lon']:
                    row += tdr(value)
                else:
                    row += td(value)
            h += tr(row)

            prev_h3 = h3
            prev_h4 = h4
            prev_day = day
        h += html.end_table()

        h += "<p>Response time: %s</p>" % lib.response_time()
        h += "<p>Log: %s</p>" % lib.log_rpt_html()

        h += html.doc_footer()
        return h

    def as_svg(self):
        s = ""
        last_track = len(self.tracks) - 1
        title = self.header
        desc = fmt.dmyy(self.min_date) + "-" + fmt.dmyy(self.max_date)
        fixed = None
        if self.kwargs['lat'] != "":
            fixed = {'mid_lat': float(self.kwargs['lat']),
                 'mid_lon': float(self.kwargs['lon']),
                 'width_km': float(self.kwargs['km']),
                 'orientation': self.kwargs['mode']}
        for i, track_dict in enumerate(self.tracks):
            track = track_dict['track']
            append = i > 0
            final = i == last_track
            s += track.as_svg(self.map_area, fixed, title, desc, append, final)
        return s


class TrackCache(object):
    """Cache of Track summary data, as input for Tracklist"""
    def __init__(self, infile, **kwargs):
        self.dir_ = infile
        self.kwargs = kwargs
        self.mode = kwargs['mode']
        filename = ("ge_segments.csv" if self.mode == "edit" else
                    "ge_segments_new.csv")
        self.infile = os.path.join(self.dir_, filename)
        self.header = kwargs['header']
        self.cache = []
        self.fields = ("date time_start time_stop activity_id " +
                       "distance duration speed count " +
                       "hm_up hm_down start_dist name " +
                       "max_lat min_lat max_lon min_lon").split()

        self.activity_id = kwargs['activity_id']
        self.min_date = datetime.datetime.min
        self.max_date = datetime.datetime.min

        self._import_csv(self.infile)
        self._remove_duplicates()
        if self.mode == "edit":
            self.adjust_activity()
            self.save_as_csv()
            return

        self.load_all_tracks = self.kwargs['km'] == ""
        if not self.load_all_tracks:
            self.fixed = {'mid_lat': float(self.kwargs['lat']),
                          'mid_lon': float(self.kwargs['lon']),
                          'width_km': float(self.kwargs['km']),
                          'orientation': self.kwargs['mode']}
            self.svg_map = SVGMap(svg, fixed=self.fixed, icon=self.activity_id)
            self.canvas_area = self.svg_map.svg.canvas['inner']
        else:
            self.canvas_area = {}

        self._load_tracks(self.canvas_area)
        self._sort_tracks(self.mode)

    def _import_csv(self, infile):
        if not os.path.exists(infile):
            e = "File '%s' missing; create using Tracklist mode 'segments')"
            raise Exception(e % infile)
        with open(infile) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=";")
            for i, file_dict in enumerate(reader):
                first_field = file_dict.get('date')
                is_blank = len(first_field.strip()) == 0
                is_comment = (first_field + " ")[0] == "#"
                if not (is_blank or is_comment):
                    seg_dict = {}
                    for field in self.fields:
                        value = file_dict.get(field)
                        if value is None:
                            e = "Row %s missing field '%s'.\n" % (i, field)
                            e += "Fix file '%s'\n" % infile
                            e += "Mandatory fields: %s" % " ".join(self.fields)
                            raise Exception(e)
                        seg_dict[field] = value
                    Segment.make_numeric(seg_dict)
                    self.cache.append(seg_dict)

    @logged
    def save_as(self, filename):
        file_format = filename.split(".")[-1]
        if file_format == 'csv':
            self.save_as_csv()
            return
        if file_format == 'kml':
            a_str = self.as_kml()
        elif file_format == 'html':
            a_str = self.as_html()
        elif file_format == 'svg':
            a_str = self.as_svg()
        else:
            raise Exception("Unknown file format %s" % file_format)
        lib.save_as(filename, a_str, verbose=True)

    def _remove_duplicates(self):
        clean = []
        [clean.append(seg) for seg in self.cache if seg not in clean]
        self.cache = clean

    def adjust_activity(self):
        row = ("{date} {time_start:.5} {speed_fmt} km/h " +
               "{distance_fmt} km {name:.10}: " +
               "{activity_id} > {new_activity} as {reason}")
        i = 0
        for seg_dict in self.cache:
            Segment.guess_activity(seg_dict)
            old_activity = seg_dict['activity_id']
            new_activity = seg_dict['new_activity']
            row_changed = new_activity != old_activity
            if row_changed:
                i += 1
                filename = Segment.csv_filename(seg_dict)
                mv_from = os.path.join(self.dir_, old_activity, filename)
                delete_it = new_activity == "skip"
                if delete_it:
                    os.remove(mv_from)
                else:
                    to_dir = os.path.join(self.dir_, new_activity)
                    mv_to = os.path.join(to_dir, filename)
                    if not os.path.exists(to_dir):
                        os.makedirs(to_dir)
                    os.rename(mv_from, mv_to)
                print(row.format(**seg_dict))
            Segment.revert_numeric(seg_dict)
            Segment.clean_before_save(seg_dict)
        print("adjust_activity: A total of %s rows changed" % i)

    def save_as_csv(self):
        filename = os.path.join(self.dir_, 'ge_segments_new.csv')
        with open(filename, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fields,
                                    delimiter=";")
            writer.writeheader()
            date = fmt.current_date_yymd()
            time = fmt.current_time_hm()
            csvfile.write("\n# Edited as TrackCache %s %s\n\n" % (date, time))
            for seg_dict in self.cache:
                writer.writerow(seg_dict)
            print("Edited track cache metadata saved on file %s" % filename)

    def as_html(self):
        html.set_title_desc(self.header, "")
        h = html.doc_header()
        h += "<h1>%s</h1>\n" % self.header
        h += "<p>%s<br>\n%s</p>" % (fmt.current_timestamp(), "")

        # Tracks
        h += "\n\n<h2>Tracks</h2>\n"
        h += " <table>\n"
        track_row = '   <tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
        track_row += '<td>%s (%s)</td><td align="right">%s</td>'
        track_row += '<td>%s</td><td align="right">%s</td></tr>\n'
        space_row = '   <tr><td><span class="space">&nbsp;</span></td></tr>\n'

        prev_month = prev_day = ""
        x = """
        for track in self.tracks:
            dist = track['a_dist']
            if self.min_km is not None:
                if dist < self.min_km:
                    continue
            month = track['date'].strftime('%Y-%m')
            day = track['date'].strftime('%d.%m.%Y')
            day_blank = day if day != prev_day else ""
            if month != prev_month:
                h += '\n  <tr><td colspan="4"><h3>%s</h3></td></tr>\n' % month
            h += track_row % (day_blank, track.get('hm_to_hm'),
                              track.get('name'),
                              track.get('area'), track.get('sub_area'),
                              track.get('a_dist_fmt'), track.get('dist_fmt'),
                              track.get('duration_hm'), track.get('speed_fmt'))

            prev_month = month
            prev_day = day
        h += " </table>\n"

        # Days
        h += "\n\n<h2>Date stats</h2>\n"
        h += " <table>\n"
        date_row = '  <tr><td>%s</td><td>%s</td><td align="right">%s</td>'
        date_row += '<td align="right">%s</td><td align="right">%s</td>'
        date_row += '<td align="right">%s</td><td align="right">%s</td>'
        date_row += '<td align="right">%s</td><td align="right">%s</td>'
        date_row += '<td align="right">%s</td><td align="right">%s</td></tr>\n'

        dates = list(self.activity_stats)
        dates.sort()
        h += date_row % ('Day', 'Area', 'Ski', 'km', 'up', 'down', 'Lift',
                         'km', 'up', 'down', 'Road')
        name = ""
        for date in dates:
            day = self.activity_stats[date]['hdr']
            if _day_metadata is not None:
                if not isinstance(_day_metadata[date], str):
                    name = _day_metadata[date].name
            ski = self.activity_stats[date].get('downhill', {})
            snowboard = self.activity_stats[date].get('snowboard', {})
            lift = self.activity_stats[date].get('lift', {})
            road = self.activity_stats[date].get('road', {})
            ski_km = fmt.km(ski.get('km', 0) + snowboard.get('km', 0))
            ski_up = "%s m" % fmt.i1000(ski.get('hm_up', 0) +
                                        snowboard.get('hm_up', 0))
            ski_down = "%s m" % fmt.i1000(ski.get('hm_down', 0) +
                                          snowboard.get('hm_down', 0))
            ski_count = ski.get('count', 0) + snowboard.get('count', 0)
            lift_km = fmt.km(lift.get('km', 0))
            lift_up = "%s m" % fmt.i1000(lift.get('hm_up', 0))
            lift_down = "%s m" % fmt.i1000(lift.get('hm_down', 0))
            road_km = fmt.km(road.get('km', 0))
            h += date_row % (day, name, ski_count, ski_km, ski_up, ski_down,
                             lift.get('count'), lift_km, lift_up, lift_down,
                             road_km)
        h += " </table>\n"

        # Segments
        h += "\n\n<h2>Segments</h2>\n"
        h += " <table>\n"
        seg_row = '  <tr><td>%s</td><td>%s</td><td align="right">%s</td>'
        seg_row += '<td>%s</td><td align="right">%s</td>'
        seg_row += '<td align="right">%s</td><td align="right">%s</td>'
        seg_row += '<td align="right">%s</td><td>%s</td></tr>\n'

        prev_day = ""
        prev_direction = ""
        for seg in self.segments:
            start_dist = seg['start_dist']
            end_dist = seg['end_dist']
            if self.min_km is not None:
                if start_dist < self.min_km:
                    continue
            if seg['distance'] < 0.2:
                continue
            date = seg['date'].strftime('%Y-%m-%d')
            day = seg['date'].strftime('%d.%m.%Y')
            if day != prev_day:
                if _day_metadata is not None:
                    if not isinstance(_day_metadata[date], str):
                        name = _day_metadata[date].name
                empty_dict = {'count': 0, 'km': 0, 'hm_down': 0, 'hm_up': 0}
                ski = self.activity_stats[date].get('downhill', empty_dict)
                if ski == empty_dict:
                    ski = self.activity_stats[date].get('snowboard',
                                                        empty_dict)
                lift = self.activity_stats[date].get('lift', empty_dict)
                hdr1 = "%s %s (%s): %s %s m / %s m" % (day, name, ski['count'],
                                                       fmt.km(ski['km']),
                                                       fmt.i1000(
                                                           ski['hm_down']),
                                                       fmt.i1000(ski['hm_up']))
                hdr2 = "Lift (%s): %s %s m / %s m" % (lift['count'],
                                                      fmt.km(lift['km']),
                                                      fmt.i1000(
                                                          lift['hm_down']),
                                                      fmt.i1000(lift['hm_up']))
                h += ('\n <tr><td colspan="9"><h3>%s <span class="small">' +
                      '%s</span></h3></td></tr>\n\n') % (hdr1, hdr2)
            direction = seg['direction']  # up / down
            # h += "<tr><td>%s</td><td>%s</td></tr>\n" %
            # (direction, prev_direction)
            # todo if direction != prev_direction and prev_direction != "":
            # -- nja, istället då pausen är lång
            # todo    h += space_row
            diff_start = fmt.km(seg['start_dist']) if start_dist > 0.2 else ""
            diff_end = fmt.km(seg['end_dist']) if end_dist > 0.2 else ""
            if diff_start == "":
                if diff_end == "":
                    diff = ""
                else:
                    diff = "/ %s" % diff_end
            else:
                if diff_end == "":
                    diff = "%s /" % diff_start
                else:
                    diff = "%s / %s" % (diff_start, diff_end)
            name = seg['name'] if diff == "" else "%s (%s)" % (
                seg['name'], diff)
            if len(name) > 50:
                name = name[0:48] + "..."
            hm_up = "%sm" % seg['hm_up'] if seg['hm_up'] != 0 else ""
            hm_down = "%sm" % seg['hm_down'] if seg['hm_down'] != 0 else ""
            if abs(seg['hm_up']) > 10 and abs(seg['hm_down']) > 10:
                hm_up = '<span class="red">%s</span>' % hm_up
                hm_down = '<span class="red">%s</span>' % hm_down
            activity_id = seg['activity_id']
            hm_to_hm = seg['hm_to_hm']
            day_activity_id = ""
            if _day_metadata is not None:
                if not isinstance(_day_metadata[date], str):
                    day_activity_id = _day_metadata[date].day_activity_id

            name = ("&nbsp; %s" % name if activity_id != day_activity_id
                    else name)
            hm_to_hm = ("<b>%s</b>" % hm_to_hm if abs(seg['hm_down']) > 100
                        else hm_to_hm)
            hm_to_hm = ("&nbsp; %s" % hm_to_hm
                        if activity_id != day_activity_id else hm_to_hm)

            h += seg_row % (hm_to_hm, name, seg['distance_fmt'], "&nbsp; " +
                            seg['duration'], seg['speed_fmt'],
                            seg['alt_diff'], hm_up, hm_down, activity_id)

            prev_day = day
"""
        h += " </table>\n"

        h += "<p>Response time: %s</p>" % lib.response_time()
        h += "<p>Log: %s</p>" % lib.log_rpt_html()

        h += html.doc_footer()
        return h

    def as_html_g(self):
        html.set_title_desc(self.kwargs['header'], self.kwargs['infile'])
        h = html.doc_header()
        h += html.start_table(column_count=3)
        last_area = last_activity_id = last_date = ""
        for seg_dict in self.cache:
            area = "a"
            activity_id = "b description"
            date = "c with name"
            if area != last_area:
                h += html.h2(area)
            if activity_id != last_activity_id:
                h += html.h3(activity_id)
            if date != last_date:
                h += html.h4(date)
            h += self.seg_dict_as_html(with_date=False)
            last_area = area
            last_activity_id = activity_id
            last_date = date
        h += html.end_table()
        h += html.doc_footer()
        return h

    def seg_dict_as_html(self, with_date):
        return ""

    def as_svg(self):
        s = ""
        title = self.header
        desc = fmt.dmyy(self.min_date) + "-" + fmt.dmyy(self.max_date)
        for i, seg_dict in enumerate(self.cache):
            track = seg_dict.get('track')
            if track is not None:
                append = i > 0
                s += track.as_svg(self.canvas_area, self.fixed, title, desc,
                                  append, final=False)
        s += self.svg_map.draw_placemarks(_places)
        s += svg.doc_footer()
        return s

    def count(self):
        return len(self.cache)

    def _load_tracks(self, canvas_area):
        c = len(self.cache)
        j = 0
        for i, seg_dict in enumerate(self.cache):
            filename = Segment.csv_filename(seg_dict)
            activity_id = seg_dict['activity_id']
            filename = os.path.join(self.dir_, activity_id, filename)
            if self.load_all_tracks:
                within_map = True
            else:
                lat1_ok = (seg_dict['max_lat'] > canvas_area['lat']['bottom'])
                lat2_ok = (seg_dict['min_lat'] < canvas_area['lat']['top'])
                lon1_ok = (seg_dict['max_lon'] > canvas_area['lon']['left'])
                lon2_ok = (seg_dict['min_lon'] < canvas_area['lon']['right'])
                within_map = lat1_ok and lat2_ok and lon1_ok and lon2_ok
            if within_map:
                track = Track(filename, activity_id=activity_id, mode="read",
                              main_activity_id=self.activity_id,
                              comment="%s / %s (%s)" % (i + 1, c, j))
                seg_dict['track'] = track
                if j == 0:
                    self.min_date = track.date
                    self.max_date = track.date
                self.min_date = min(self.min_date, track.date)
                self.max_date = max(self.max_date, track.date)
                j += 1
                first_tp = track.trackpoints[0]
                date = first_tp.date_yymd()
                seg_dict['date_order'] = date
                meta = _day_metadata[date]
                if isinstance(meta, str):
                    seg_dict['date_header'] = "??"
                else:
                    seg_dict['date_header'] = _day_metadata[date].name
                first_placemark = _places.closest_placemark(first_tp)
                sub_area = first_placemark.sub_area
                area = first_placemark.area
                seg_dict['sub_area'] = sub_area
                seg_dict['area'] = area
                sub_area_dict = _areas.get(sub_area, {})
                seg_dict['order_area'] = sub_area_dict.get('order_area', 0)
                Segment.update_order(seg_dict)
            else:
                seg_dict.update({'area': 'a', 'order_area': 0, 'sub_area': 'a',
                                 'date_order': 'b', 'date_header': 'c'})

    def _sort_tracks(self, order):
        if order == "activity":
            self.cache.sort(key=lambda seg: seg['order_activity'] +
                ("%7d" % seg['order_area']) + seg['date_order'] +
                                              seg['time_start'])
        elif order == "area":
            self.cache.sort(key=lambda seg: ("%7d" % seg['order_area']) +
                seg['order_activity'] + seg['date_order'] + seg['time_start'])

    def as_kml(self):
        seg_fmt = "{time_start:.5}-{time_stop:.5} {distance_fmt} km "
        seg_fmt += "{duration} {speed_fmt} km/h %s"
        k = kml.doc_header(self.kwargs['header'])
        sort_order = self.mode
        last_h2 = last_h3 = last_h4 = ""
        first_h2 = True
        for seg_dict in self.cache:
            area = seg_dict['area']
            activity_id = seg_dict['activity_id']
            activity_name = _activities[activity_id].name
            color = _activities[activity_id].color1
            color = lib.rgb2aabbggrr(color)
            color2 = _activities[activity_id].color2
            date_name = seg_dict['date'] + " " + seg_dict['date_header']
            u_safe_name = seg_dict['name'].decode("utf-8")
            u_safe_name = u_safe_name[0:20].encode("utf-8")
            seg_name = seg_fmt.format(**seg_dict) % u_safe_name
            if sort_order == "area":
                h2 = area
                h2_name = h2
                h3 = activity_id
                h3_name = activity_name
                h4 = date_name
                h4_name = h4
            else:
                h2 = activity_id
                h2_name = activity_name
                h3 = area
                h3_name = h3
                h4 = date_name
                h4_name = h4

            new_h2 = h2 != last_h2
            new_h3 = h3 != last_h3
            new_h4 = h4 != last_h4
            if seg_dict.get('track') is None:
                break
            if new_h2:
                if not first_h2:
                    k += kml.end_section(last_h4)
                    k += kml.end_section(last_h3)
                    k += kml.end_section(last_h2)
                k += kml.begin_section(h2_name, comment=h2)
                k += kml.begin_section(h3_name, comment=h3)
                k += kml.begin_section(h4_name, comment=h4)
            elif new_h3:
                k += kml.end_section(last_h4)
                k += kml.end_section(last_h3)
                k += kml.begin_section(h3_name, comment=h3)
                k += kml.begin_section(h4)
            elif new_h4:
                k += kml.end_section(last_h4)
                k += kml.begin_section(h4)
            k += kml.placemark_header(seg_name)
            k += kml.linestyle_header_footer(color)
            k += kml.linestring_pure_header()
            for trackpoint in seg_dict['track'].trackpoints:
                k += trackpoint.as_coordinate_tag()
            k += kml.linestring_footer()
            k += kml.placemark_footer()
            last_h2 = h2
            last_h3 = h3
            last_h4 = h4
            first_h2 = False
        k += kml.end_section("final " + last_h4)
        k += kml.end_section("final " + last_h3)
        k += kml.end_section("final " + last_h2)
        k += kml.doc_footer()
        return k


class Segment(object):
    """Stretch of a track, separated by breaks"""

    def __init__(self, track, i_first_tp, i_last_tp, activity_id, type):
        self.track = track
        self.i_first_tp = i_first_tp
        self.i_last_tp = i_last_tp
        self.i_current_tp = i_first_tp
        self.previous_segment = None
        self.next_segment = None
        self.activity_id = activity_id
        self.order_activity = _activities[activity_id].order
        self.type = type
        self.map_area = geo.calc_nwse(self)
        self.first = self._calc_tp_pm(i_first_tp)
        self.last = self._calc_tp_pm(i_last_tp)
        self.stats = {}
        self.break_ = {}
        self.calc_distance_duration()
        self.parse_segment_for_peaks()

        if self.track.diary is not None:
            if self.track.diary.kwargs['parameters'] == "missing":
                if self.first['dist'] > 0.05:
                    # Over 50 metres from existing Placemark
                    self._create_missing_start_placemark()

    def __str__(self):
        break_dur = self.break_duration_hm()
        duration = (self.duration_hm() + "+" + break_dur if break_dur != "-"
                    else self.duration_hm())
        return "%s: %s / %s (%s) %s" % (self.first['name'],
                                        fmt.km(self.distance),
                                        duration, self.speed_kmh(),
                                        self.activity_id)

    def __repr__(self):
        return "tp[%s...%s] %s" % (self.i_first_tp, self.i_last_tp, str(self))

    def __len__(self):
        return self.i_last_tp - self.i_first_tp + 1

    def __iter__(self):
        self.i_current_tp = self.i_first_tp
        return self

    def next(self):
        if self.i_current_tp > self.i_last_tp:
            raise StopIteration
        else:
            self.i_current_tp += 1
            return self.track.trackpoints[self.i_current_tp - 1]

    def as_dict(self):
        alt_diff = int(self.last['tp'].alt - self.first['tp'].alt)
        direction = "up" if alt_diff > 0 else "down"
        alt_diff = ("v %s m" % abs(alt_diff) if direction == "down" else
                    "^ %s m" % alt_diff)
        return {'date': self.first['tp'].date_yymd(),
                'time_start': self.first['tp'].time_hms(),
                'time_stop': self.last['tp'].time_hms(),
                'hm_to_hm': self.hm_to_hm(), 'name': self.name(),
                'speed': self.speed(),
                'distance_fmt': fmt.km(self.distance),
                'duration': self.duration_hms(), 'speed_fmt': self.speed_kmh(),
                'distance': self.distance, 'start_dist': self.first['dist'],
                'end_dist': self.last['dist'],
                'short_name': self.first['pm'].text,
                'lat': self.first['tp'].lat_5(),
                'lon': self.first['tp'].lon_5(),
                'direction': direction, 'alt_diff': alt_diff,
                'hm_up': self.hm_up, 'hm_down': self.hm_down,
                'activity_id': self.activity_id,
                'start_datetime': self.first['tp'].datetime,
                'end_datetime': self.last['tp'].datetime}

    @staticmethod
    def save_as_csv(filename, seg_dicts, comment):
        clean = []
        [clean.append(seg) for seg in seg_dicts if seg not in clean]
        seg_dicts = clean

        fields = ('date time_start time_stop activity_id distance duration ' +
                  'speed count hm_up hm_down start_dist name ' +
                  'max_lat min_lat max_lon min_lon').split()
        with open(filename, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fields, delimiter=";")
            writer.writeheader()
            date = fmt.current_date_yymd()
            time = fmt.current_time_hm()
            csvfile.write("\n# %s %s\n" % (date, time))
            csvfile.write("\n# %s\n\n" % comment)
            for seg_dict in seg_dicts:
                for field in ['max_lat', 'min_lat', 'max_lon', 'min_lon']:
                    seg_dict[field] = "{:.5f}".format(seg_dict[field])
                seg_dict = {pick: seg_dict[pick] for pick in fields}
                writer.writerow(seg_dict)
            print("Segment metadata saved on file %s" % filename)

    def name(self):
        if self.first['name'] == self.last['name']:
            return self.first['name']
        else:
            return "%s-%s" % (self.first['name'], self.last['name'])

    def set_previous(self, previous_segment):
        self.previous_segment = previous_segment

    def set_next(self, next_segment):
        self.next_segment = next_segment

    def recalc(self):
        self.first = self._calc_tp_pm(self.i_first_tp)
        self.last = self._calc_tp_pm(self.i_last_tp)
        self.type = "recalc"
        self.calc_distance_duration()

    def _calc_tp_pm(self, i_tp):
        tp = self.track.trackpoints[i_tp]
        pm = _places.closest_placemark(tp)
        # todo self.track.relevant_places is faster
        return {'tp': tp, 'pm': pm, 'dist': pm.distance(tp),
                'date_fmt': tp.date_dmyy(), 'time': tp.time_hm(),
                'name': pm.text}

    def calc_distance_duration(self):
        self.distance = self.track.distance_along_path(self.i_first_tp,
                                                       self.i_last_tp)
        self.duration_s = self.first['tp'].seconds(self.last['tp'])
        #print "distance %s duration %s" % (self.distance, self.duration_s)

    @staticmethod
    def csv_filename(seg_dict):
        d = seg_dict['date']
        h1 = seg_dict['time_start']
        h2 = seg_dict['time_stop']
        return ("%s_%s-%s.csv" % (d, h1, h2)).replace(":", "")

    @staticmethod
    def make_numeric(seg_dict):
        # lots of trouble because no pythonic way for decimal commas
        seg_dict['speed_fmt'] = seg_dict['speed']
        seg_dict['distance_fmt'] = seg_dict['distance']
        seg_dict['speed'] = float(seg_dict['speed'].replace(",", "."))
        seg_dict['distance'] = float(seg_dict['distance'].replace(",", "."))
        seg_dict['hm_up'] = int(seg_dict['hm_up'])
        seg_dict['hm_down'] = int(seg_dict['hm_down'])
        seg_dict['count'] = int(seg_dict['count'].replace(".", ""))
        seg_dict['min_lat'] = float(seg_dict['min_lat'])
        seg_dict['max_lat'] = float(seg_dict['max_lat'])
        seg_dict['min_lon'] = float(seg_dict['min_lon'])
        seg_dict['max_lon'] = float(seg_dict['max_lon'])

    @staticmethod
    def revert_numeric(seg_dict):
        seg_dict['speed'] = seg_dict['speed_fmt']
        seg_dict['distance'] = seg_dict['distance_fmt']
        seg_dict.pop('speed_fmt', None)
        seg_dict.pop('distance_fmt', None)

    @staticmethod
    def update_order(seg_dict):
        seg_dict['order_activity'] = _activities[seg_dict['activity_id']].order

    @staticmethod
    def clean_before_save(seg_dict):
        seg_dict['activity_id'] = seg_dict['new_activity']
        seg_dict.pop('new_activity', None)
        seg_dict.pop('reason', None)

    @staticmethod
    def csv_header_instructions(filename, seg_dict):
        s1 = """\
# %s -- saved %s at %s

#   Segment object with %s Trackpoint objects (from Green Elk)
"""
        s2 = """\
# Activity: {activity_id}
# Track name: {name}
# Source file: {infile}
# Segment area: N-S {max_lat:.5f}-{min_lat:.5f} W-E {min_lon:.5f}-{max_lon:.5f}
# Segment distance: {distance}
# Timing: {date} {time_start}-{time_stop} (duration {duration})
# Speed: {speed}
"""
        count = seg_dict['count']
        date = fmt.current_date_yymd()
        time = fmt.current_time_hm()
        return s1 % (filename, date, time, count), \
               s2.format(**seg_dict)

    @staticmethod
    def guess_activity(seg_dict):
        activity_id = seg_dict['activity_id']
        speed = seg_dict['speed']
        distance = seg_dict['distance']
        new_activity = activity_id
        reason = ""
        min_speed = int("0"+_activities[activity_id].min_speed)
        alt_slow = _activities[activity_id].alt_slow
        max_speed = int("0"+_activities[activity_id].max_speed)
        alt_fast = _activities[activity_id].alt_fast
        if speed > 200:
            new_activity = "fly"
            reason = ">200 km/h"
        elif speed > 90:
            new_activity = "car"
            reason = ">90 km/h"
        elif speed > 50 and distance > 2:
            new_activity = "car"
            reason = ">50 km/h & >2 km"
        elif speed < min_speed:
            new_activity = alt_slow
            reason = "<%s km/h (%s)" % (min_speed, activity_id)
        elif speed > max_speed and distance > 3:
            new_activity = alt_fast
            reason = ">%s km/h & >3 km (%s)" % (max_speed, activity_id)
        if new_activity != activity_id:
            if new_activity == "cycle" and speed > 20:
                new_activity = "car"
                reason += " / >20 km/h"
        seg_dict['new_activity'] = new_activity
        seg_dict['reason'] = reason

    def adjust_activity(self):
        seg_dict = self.as_dict()
        self.guess_activity(seg_dict)
        self.activity_id = seg_dict['new_activity']
        self.order_activity = _activities[self.activity_id].order

        # After heuristics, apply forced user input
        for time_row in _time_metadata:
            seg_date = self.first['tp'].date_yymd()
            seg_time_from = self.first['tp'].time_hms()
            seg_time_to = self.last['tp'].time_hms()
            if seg_date != time_row.date:
                continue
            if len(time_row.time) == 5:  # Exact time, such as 15:22
                if seg_time_from < time_row.time < seg_time_to:
                    self.activity_id = time_row.activity_id
                    self.order_activity = _activities[self.activity_id].order
                    # print "adjusted activity to %s based on individual time"
                    #  % time_row.activity_id
                continue
            row_split = time_row.time.split("-")
            if len(row_split) != 2:
                continue
                # Todo log Userbug = malformed row - should have one "-"
            row_time_from, row_time_to = row_split
            if row_time_from == '':
                row_time_from = "00:00:00"
            if row_time_to == '':
                row_time_to = "23:59:59"
            if row_time_from > seg_time_to or seg_time_from > row_time_to:
                continue
            self.activity_id = time_row.activity_id
            self.order_activity = _activities[self.activity_id].order
            print("adjusted activity to %s - based on time interval"
             % time_row.activity_id)

    def _create_missing_start_placemark(self):
        name = self.first['name']
        name = name if not "->" in name else name.split("->")[1]
        text = ("Start %s %s (%s / %s = %s) %s -> %s" %
                (self.first['date'], self.first['time'],
                 fmt.km(self.distance), self.duration_hm(), self.speed_kmh(), 
                 fmt.m(self.first['dist']), name))
        placetype_id = "gestart"
        tp = self.first['tp']
        pm = Placemark(placemark=text, placetype_id=placetype_id,
                       lat=tp.lat, lon=tp.lon, alt=tp.alt,
                       prominence=9, dynamic=True)
        if self.track.diary is not None:
            self.track.diary.missing_placemarks.append(pm)
            _places.add(pm)

    def parse_segment_for_peaks(self):
        extremes = []
        hm_up = 0
        hm_down = 0
        prev_alt = self.first['tp'].alt
        going_up_counter = 0
        going_down_counter = 0
        prev_going_up = prev_going_down = False
        prev_tp = self.track.trackpoints[self.i_first_tp]
        for i_tp in range(self.i_first_tp + 1, self.i_last_tp + 1):
            tp = self.track.trackpoints[i_tp]
            seconds = int(tp.seconds(prev_tp))
            alt = tp.alt
            alt_diff = alt - prev_alt
            going_up = alt_diff >= 0
            going_down = alt_diff <= 0
            if going_up:
                if prev_going_up:
                    going_up_counter += seconds
                else:
                    if going_down_counter > 60:
                        d = {'type': 'bottom', 'i_tp': i_tp,
                             'hm_up': hm_up, 'hm_down': hm_down,
                             'going_down_counter': going_down_counter}
                        extremes.append(d)
                    going_up_counter = seconds
            else:
                if prev_going_down:
                    going_down_counter += seconds
                else:
                    if going_up_counter > 60:
                        d = {'type': 'peak', 'i_tp': i_tp,
                             'hm_up': hm_up, 'hm_down': hm_down,
                             'going_up_counter': going_up_counter}
                        extremes.append(d)
                    going_down_counter = seconds

            prev_tp = tp
            prev_alt = alt
            prev_going_up = going_up
            prev_going_down = going_down
            if alt_diff > 0:
                hm_up += alt_diff
            else:
                hm_down += alt_diff
        # Delete extremes followed by another extreme of the same type;
        # only last of consecutive peaks or consecutive bottoms is relevant
        for i in range(len(extremes) - 1, 0, -1):
            type_ = extremes[i]['type']
            prev_type = extremes[i - 1]['type']
            if prev_type == type_:
                del extremes[i - 1]
        self.extremes = extremes

        text = self.first['pm'].text
        self.hm_up = int(hm_up)
        self.hm_down = int(hm_down)
        if self.track.diary is not None:
            if self.track.diary.kwargs['parameters'] == "missing":
                self._create_missing_extreme_placemarks()

    def parse_segment_for_transits(self):
        self.transits = []
        seg_area = geo.calc_nwse(self)
        p1 = Point(seg_area['min']['lat'], seg_area['min']['lon'])
        p2 = Point(seg_area['max']['lat'], seg_area['max']['lon'])
        self.relevant_breaks = Places("copy", forced_breaks=_forced_breaks,
                                      p1=p1, p2=p2)
        limit_dist = 0.02
        for br in self.relevant_breaks:
            point = Point(br.lat, br.lon)
            #print "Relevant break %s (%s, %s)" % (br.text, br.lat, br.lon)
            direction = br.direction
            min_dist = 9999
            min_i_tp = 0
            for i_tp in range(self.i_first_tp, self.i_last_tp):
                tp = self.track.trackpoints[i_tp]
                dist = point.distance(tp)
                if dist < min_dist:
                    #min_tp = tp
                    min_i_tp = i_tp
                    min_dist = dist
            #print "min_dist %s %s" % (min_dist, min_tp.time_hm())
            if min_dist < limit_dist:
                self.transits.append(min_i_tp)
                #print "appended"

    def _create_missing_extreme_placemarks(self):
        for extreme in self.extremes:
            type_ = extreme['type']
            i_tp = extreme['i_tp']
            tp = self.track.trackpoints[i_tp]
            closest_pm = self.track.relevant_places.closest_placemark(tp)
            dist = closest_pm.distance(tp)
            if dist < 0.1:
                continue

            name = closest_pm.text
            name = name if not "->" in name else name.split("->")[1]
            name = "%s %s -> %s" % (type_, fmt.m(dist), name)
            placetype_id = "ge%s" % type_
            pm = Placemark(placemark=name, placetype_id=placetype_id,
                           lat=tp.lat, lon=tp.lon, alt=tp.alt,
                           prominence=9, dynamic=True)
            if self.track.diary is not None:
                self.track.diary.missing_placemarks.append(pm)
                _places.add(pm)

    def hm_to_hm(self):
        return "%s-%s" % (self.first['time'], self.last['time'])

    def duration_hm(self):
        return "%s" % fmt.sec_as_hm((self.last['tp'].datetime -
                                     self.first['tp'].datetime).seconds + 30)

    def duration_hms(self):
        return "%s" % fmt.sec_as_hms((self.last['tp'].datetime -
                                      self.first['tp'].datetime).seconds)

    def speed(self):  # in km/h, not in m/s
        if self.duration_s > 0:
            return geo.km_h(self.distance * 1000.0 / self.duration_s)
        else:
            return 0  # todo Make this appear on Userbugs

    def speed_kmh(self):
        return fmt.km(self.speed()) + "/h"

    def date(self):
        d = self.first['date']
        if self.previous_segment is not None:
            previous_date = self.previous_segment.start_date
            if previous_date == d:
                d = ""
        return d + " " if d != "" else d

    def break_hm_to_hm(self):
        if self.next_segment is not None:
            return "%s-%s" % (self.last['time'],
                              self.next_segment.first['time'])
        else:
            return "%s-?" % self.last['time']

    def break_duration_hm(self):
        if self.next_segment is not None:
            return "%s" % fmt.sec_as_hm((self.next_segment.first['tp'].datetime
                                - self.last['tp'].datetime).seconds + 30)
        else:
            return "-"

    def segment_label(self):
        return ("%s%s: %s (%s / %s = %s)" % 
                (self.date(), self.hm_to_hm(), self.name(),
                 fmt.km(self.distance), self.duration_hm(), self.speed_kmh()))

    def break_label(self):
        return "%s: %s (%s)" % (self.break_hm_to_hm(), self.last['name'],
                                self.break_duration_hm())

    def as_svg(self, color, dashes=None):
        style_1 = {'font-size': 2.5, 'text-anchor': 'middle'}
        style_2 = {'font-size': 2, 'text-anchor': 'middle'}
        dashes = "0.5 0.25" if self.activity_id == "lift" else None
        color_map = {'lift_gron': 'green', 'lift_orange': 'orange',
                     'lift_nere': 'brown', 'road': 'grey'}
        color = "red"
        if not self.activity_id in ['downhill', 'snowboard']:
            color = color_map.get(self.first['pm'].placetype_id, "red")
        s = svg.comment("Segment %s - %s" % (self.first['pm'].placetype_id,
                                             str(self)))
        split_lift_in_middle = (self.activity_id == "lift" and
                                self.i_last_tp - self.i_first_tp == 1)
        marker = "marker-mid='url(#mid)'" if split_lift_in_middle else ""
        svg.polyline_begin({'stroke': color, 'stroke-dasharray': dashes},
                           "", marker)
        s1 = s2 = ""
        for i in range(self.i_first_tp, self.i_last_tp + 1):
            lat = self.track.trackpoints[i].lat
            lon = self.track.trackpoints[i].lon
            x, y = svg.map.latlon2xy(lat, lon)
            svg.polyline_add_point(x, y)
            if split_lift_in_middle and i == self.i_first_tp:
                lat2 = self.track.trackpoints[i + 1].lat
                lon2 = self.track.trackpoints[i + 1].lon
                mid_lat = (lat + lat2) / 2
                mid_lon = (lon + lon2) / 2
                x2, y2 = svg.map.latlon2xy(mid_lat, mid_lon)
                angle = atan2(x2 - x, y - y2)
                angle = (degrees(angle) + 180) % 180 + 180
                svg.polyline_add_point(x2, y2)
                duration = self.first['time'] + "-" + self.last['time']
                s1 = svg.plot_text_mm(x2, y2, self.first['name'], style_1,
                                      angle=angle + 90, dy=-1.5)
                s2 = svg.plot_text_mm(x2, y2, duration, style_2,
                                      angle=angle + 90, dy=+2.5)
        s += svg.plot_polyline()
        s += s1 + s2
        return s

    def as_speed_svg(self):
        last_colour = svg.speed2colour(0)  # Colour of no movement
        s = ""
        last_tp = self.i_first_tp
        last_x = last_y = 0.0
        svg.polyline_begin({'stroke': last_colour})
        for i in range(self.i_first_tp, self.i_last_tp + 1):
            tp = self.track.trackpoints[i]
            x, y = svg.map.latlon2xy(tp.lat, tp.lon)
            if i > self.i_first_tp:
                speed = tp.speed(last_tp)
                colour = svg.speed2colour(speed)
                if colour != last_colour:
                    s += svg.plot_polyline()
                    s += svg.comment("Speed %s" % speed)
                    svg.polyline_begin({'stroke': colour})
                    svg.polyline_add_point(last_x, last_y)
                    last_colour = colour
            svg.polyline_add_point(x, y)
            last_x = x
            last_y = y
            last_tp = tp
        s += svg.plot_polyline()
        return s

    def as_slope_svg(self):
        last_colour = "#" + _activities[self.activity_id].color1
        s = ""
        last_x = last_y = 0.0
        svg.polyline_begin({'stroke': last_colour, 'stroke-width': 0.3})
        for i in range(self.i_first_tp, self.i_last_tp + 1):
            tp = self.track.trackpoints[i]
            colour = self.track.color(tp)
            x, y = svg.map.latlon2xy(tp.lat, tp.lon)
            is_first_point = (i == self.i_first_tp)
            if not is_first_point:
                slope_changed = (colour != last_colour)
                if slope_changed:
                    s += svg.plot_polyline()  # Plot what's in the "buffer"
                    s += svg.comment("Slope %s" % colour)
                    svg.polyline_begin({'stroke': colour, 'stroke-width': 0.3})
                    svg.polyline_add_point(last_x, last_y)
            lift_pen = svg.polyline_add_point(x, y)
            if lift_pen:
                s += svg.plot_polyline()
                s += svg.comment("Went outside map borders")
                svg.polyline_begin({'stroke': colour, 'stroke-width': 0.3})
            last_x = x
            last_y = y
            last_colour = colour
        s += svg.plot_polyline()
        svg.list_midpoints()
        return s


class Track(object):
    """Collection of Trackpoints, usually as recorded by GPS"""
    def __init__(self, infile, **kwargs):
        kwargs['infile'] = infile
        self.kwargs = kwargs
        self.filename = infile
        self.from_source = ("" if infile is None else
                            "/src/" in self.filename)
        self.mode = kwargs.get('mode', 'segment')
        self.name = kwargs.get('header', "")
        self.diary = kwargs.get('diary')
        self.activity_id = kwargs.get('activity_id', 'run')
        self.main_activity_id = kwargs.get('main_activity_id',
                                           self.activity_id)

        self.sub_format = "Normal"
        self.trackpoints = []
        self.segments = []
        self.breaks = []
        self.storypoints = []
        self.milestones = []
        self.tour = []
        self.activities = [self.main_activity_id]
        self.timepoints = {}
        self.date = datetime.datetime.min
        self.timezone_delta = None

        if self.mode == "empty":
            return
        if infile is None:
            return
        if self.mode != "plan" and self.mode != "tour":
            self._import_file(infile, mode="skim")
            self.map_area = geo.calc_nwse(self.trackpoints)
            if self.mode == "skim":
                return
            # mode "diary"
            if len(self.trackpoints) == 0:
                return
            date = self.trackpoints[0].date_yymd()
            have_day_metadata = _day_metadata[date] != ""
            seconds = 0
            if have_day_metadata:
                seconds = 60 * int(_day_metadata[date].timezone)
                seconds = 0 if not self.from_source else seconds
                # Don't apply time zone more than once
                self.activity_id = _day_metadata[date].activity_id
                if self.name == "":
                    self.name = _day_metadata[date].name
            self.timezone_delta = datetime.timedelta(seconds=seconds)
        self.trackpoints = []

        print_filename = os.path.split(infile)[1]
        comment = self.kwargs.get('comment', "")
        if not kwargs.get('server_level') == True:
            print("%s - %s: Track(%s) " % (comment, fmt.current_time_hm(),
                                     print_filename))

        # Start all over: read "skimmed" first trackpoint again from scratch
        self._import_file(infile, mode=self.mode,
                         timezone_delta=self.timezone_delta)
        self.map_area = geo.calc_nwse(self.trackpoints)
        p1 = Point(self.map_area['min']['lat'], self.map_area['min']['lon'])
        p2 = Point(self.map_area['max']['lat'], self.map_area['max']['lon'])
        self.relevant_places = Places("copy", original=_places, p1=p1, p2=p2)
        if self.mode == "diary":
            return
        #self.create_timepoints()
        #self._calc_timepoints()
        # self._list_timepoints()
        if self.mode == "read":
            segment = Segment(self, 0, self.count() -1, self.activity_id,
                              "cache")
            self.segments.append(segment)
            return
        if self.sub_format == "Plan":
            self.compressed = self
        else:
            self._suggest_segments()
            for seg in self.segments:
                seg.parse_segment_for_transits()
            self._split_track_at_transits()
            if self.activity_id in ['downhill', 'snowboard']:
                self._split_track_at_peaks()
            self.eliminate_too_short_segments()
            self.update_previous_next_pointers()
            self.calc_track_net()
            self._adjust_segment_activities()
            self._sort_by_activity()
            self._calc_activities()
            self.compressed = self._compress_track()
            self.zipped = self._compress_track(0.05)
        if self.mode == "tour":
            tick = 0.1  # 0.1 = 100 m
            self.equi = self.equidistant_points(self.trackpoints, tick,
                                                type_="Point")
            self.running = self.running_average(self.equi, window_points=21)
            self.trackpoints = self.running
            self._create_tour()
        # todo faster directly from .compressed?

    def __str__(self):
        s = "Track (%s trackpoints) " % len(self.trackpoints)
        s += "mode %s activity_id %s " % (self.mode, self.activity_id)
        s += self.filename
        return s

    def __repr__(self):
        return str(self)

    def __format__(self, fmt):
        if fmt == 'kml':
            return self.as_kml()
        elif fmt == 'svg':
            return self.as_svg()
        elif fmt == 'json':
            return self.as_json()

    def __getitem__(self, index):
        if isinstance(index, int):
            return self.trackpoints[index]

    def append(self, other_track):
        other_start = other_track.trackpoints[0].datetime
        this_start = self.trackpoints[0].datetime
        other_is_later = other_start > this_start
        if other_is_later:
            for other_tp in other_track.trackpoints:
                self.trackpoints.append(other_tp)
            self.map_area = geo.calc_nwse(self.trackpoints)
            self.calc_track_net()
            self._suggest_segments()
            self.compressed_track = self._compress_track()
            self.zipped_track = self._compress_track(0.05)
        else:
            e = "Track.append(): To be appended track %s (%s) starts "
            e += "before base track %s (%s)"
            e %= (other_track.name, other_start, self.name, this_start)
            raise Exception(e)

    @logged
    def save_as(self, filename):
        file_format = filename.split(".")[-1]
        if file_format == 'svg':
            a_str = self.as_svg()
        elif file_format == 'kml':
            a_str = self.as_kml()
        elif file_format == 'csv':
            self.save_as_csv(filename)
            return
        else:
            a_str = "unknown format %s" % str(file_format)
        lib.save_as(filename, a_str, verbose=True)

    def save_as_csv(self, filename, compressed=False):
        with open(filename, 'w') as csvfile:
            fieldnames = ['date', 'time', 'lat', 'lon', 'alt', 'text']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            trackpoint_list = (self.compressed.trackpoints if compressed
                               else self.trackpoints)
            count = len(trackpoint_list)
            item = 'trackpoint'
            if compressed:
                item = "compressed " + item
            h1, h2 = lib.csv_header_instructions(count, item, filename)
            csvfile.write("\n%s\n%s\n" % (h1, h2))
            for trackpoint in trackpoint_list:
                writer.writerow(trackpoint.as_dict())

    @logged
    def as_dict(self):
        cnt = self.count()
        not_loaded = cnt == 0
        if not_loaded:
            userbug.add('Track.as_dict - 0 trackpoints for file %s' %
                        self.filename)
            return
        has_diary = cnt > 1  # 1 = just skimmed first point; distance not known
        has_segments = len(self.segments) > 0
        first_trackpoint = self[0]
        last_trackpoint = self[cnt - 1]

        first_placemark = _places.closest_placemark(first_trackpoint)
        sub_area = first_placemark.text
        area = _areas[sub_area]['area']
        area_distance = first_placemark.distance(first_trackpoint)
        a_dist_fmt = fmt.km(area_distance)
        filesize = fmt.i1000(os.path.getsize(self.filename))
        d = {'date': first_trackpoint.datetime.date(),
             'time': first_trackpoint.datetime.time(),
             'lat': first_trackpoint.lat_5(), 'lon': first_trackpoint.lon_5(),
             'area': area, 'a_dist': area_distance, 'a_dist_fmt': a_dist_fmt,
             'sub_area': sub_area, 'filename': self.filename,
             'filesize': filesize, 'name': self.name}
        if not has_diary:
            return d
        d.update({'stop_date': last_trackpoint.datetime.date(),
                  'stop_time': last_trackpoint.datetime.time()})
        # if not has_segments:
        if True:
            distance = self.distance_along_path(0, self.count() - 1)
            dist_fmt = fmt.km(distance)

            first_trackpoint = self.trackpoints[0]
            last_trackpoint = self.trackpoints[self.count() - 1]
            duration_s = (last_trackpoint.datetime -
                          first_trackpoint.datetime).total_seconds()
            duration_hm = fmt.sec_as_hm((last_trackpoint.datetime -
                                    first_trackpoint.datetime).seconds + 30)
            hm_to_hm = (first_trackpoint.time_hm() + "-" +
                        last_trackpoint.time_hm())

            speed = distance / duration_s * 3600
            speed_fmt = fmt.km(speed) + "/h"
            d.update({'distance': distance, 'dist_fmt': dist_fmt,
                      'duration_s': duration_s, 'duration_hm': duration_hm,
                      'speed': speed, 'speed_fmt': speed_fmt,
                      'hm_to_hm': hm_to_hm})
            return d

    def count(self):
        return len(self.trackpoints)

    def duration(self):
        first_trackpoint = self[0]
        last_trackpoint = self[self.count() - 1]

        date = fmt.dmyy(first_trackpoint.datetime.date())
        hm_to_hm = "%s-%s" % (fmt.hm(first_trackpoint.datetime.time()),
                              fmt.hm(last_trackpoint.datetime.time()))
        return "%s %s" % (date, hm_to_hm)

    @logged
    def _import_file(self, filename, mode="segment", timezone_delta=None):
        filetype = filename.split(".")[-1]
        timezone_delta = (datetime.timedelta(seconds=0)
                          if timezone_delta is None else timezone_delta)
        if filetype == "gpx":
            self._import_gpx(filename, timezone_delta, mode)
        elif filetype == "csv":
            self._import_csv(filename, timezone_delta, mode)
        elif filetype == "CSV":
            self._import_columbus(filename, timezone_delta, mode)
        elif filetype == "kml":
            self._import_kml_plan(filename)
        elif filetype == "json":
            self._import_json(filename)
        if self.count() == 0:
            msg = "import_file: Cannot import file %s - zero trackpoints."
            userbug.add(msg % filename)
            return 0
        self.date = self.trackpoints[0].datetime.date()
        self._eliminate_still_points()

    @logged
    def _import_gpx(self, filename, timezone_delta, mode="segment"):
        """Import from a GPX file between start and stop (times)"""
        # self.logger.lib.log_event("._import_gpx start", self.count())
        f_lat = f_lon = f_alt = f_time = ""
        # <trkpt lat="47.544738333333335" lon="9.680618333333333">
        # <ele>399.1</ele>
        # <time>2014-04-19T10:06:20.45</time>
        # </trkpt>
        a_datetime = datetime.datetime.min
        with open(filename) as gpxfile:
            i = 0
            f_hr = f_temp = ""
            for line in gpxfile:
                lat_pos = line.find('lat="')
                lon_pos = line.find('lon="')
                has_ele = '<ele>' in line
                has_time = '<time>' in line
                has_hr = ':hr>' in line
                has_temp = ':atemp>' in line
                eof_trkpt = '</trkpt>' in line
                if lat_pos > -1:
                    f_lat = float(line[lat_pos:].split('"')[1])
                if lon_pos > -1:
                    f_lon = float(line[lon_pos:].split('"')[1])
                    continue
                if has_ele:
                    f_alt = float(line.replace(">", "<").split('<')[2])
                    continue
                if has_hr:
                    f_hr = int(line.replace(">", "<").split('<')[2])
                    continue
                if has_temp:
                    f_temp = int(line.replace(">", "<").split('<')[2])
                    continue
                if has_time:
                    line = line.replace(">", "<").split('<')[2].split('T')
                    irrelevant_gpx_line = len(line) < 2
                    if irrelevant_gpx_line:
                        continue
                    f_date, f_time = line
                    f_time = f_time.split(".")[0]
                    # todo At most one point per second
                    f_time = f_time.replace("Z", "")
                    a_datetime = datetime.datetime.combine(
                        fmt.datetime_from_ymd(f_date),
                        fmt.time_from_hms(f_time))
                    a_datetime = a_datetime + timezone_delta
                if eof_trkpt:
                    i += 1
                    f_text = ""
                    if f_hr != "":
                        f_text = "hr %s " % f_hr
                    if (f_temp != ""):
                        f_text += "temp %s" % f_temp
                    tp = Trackpoint(f_lat, f_lon, a_datetime, f_alt, f_text)
                    self.trackpoints.append(tp)
                    f_hr = f_temp = ""
                    if mode == "skim":
                        break

    @logged
    def _import_columbus(self, filename, timezone_delta, mode="segment"):
        """Import from a CSV file between start and stop (times)"""
        with open(filename) as columbusfile:
            i = 0
            for line in columbusfile:
                is_header = not line[0].isdigit()
                if not is_header:
                    fields = line.split(",")
                    f_date, f_time, f_lat, f_lon, f_alt = fields[2:7]
                    i += 1
                    ns = f_lat[-1]
                    if ns in "NS":
                        f_lat = float(f_lat[:-1])
                    else:
                        f_lat = float(f_lat)
                    if ns == "S":
                        f_lat *= -1
                    we = f_lon[-1]
                    if we in "WE":
                        f_lon = float(f_lon[:-1])
                    else:
                        f_lon = float(f_lon)
                    if we == "W":
                        f_lon *= -1
                    f_alt = f_alt.strip('\x00')
                    a_datetime = datetime.datetime.combine(
                        fmt.datetime_from_ymd(f_date),
                        fmt.time_from_hms(f_time))
                    a_datetime = a_datetime + timezone_delta
                    tp = Trackpoint(f_lat, f_lon, a_datetime, f_alt)
                    self.trackpoints.append(tp)
                    if mode == "skim":
                        break

    @logged
    def _import_csv(self, filename, timezone_delta, mode="segment"):
        """Import from a csv file"""
        with open(filename) as csvfile:
            reader = csv.DictReader(csvfile)
            sub_format = 'Normal'
            for row in reader:
                sub_format = ('Tour' if 'look_at' in row else
                              'Plan' if 'placemark' in row else 'Normal')
                self.sub_format = sub_format
                break
        if sub_format == "Plan":
            self._import_csv_plan(filename)
            return
        if sub_format == "Tour":
            self._import_csv_tour(filename)
            return
        with open(filename) as csvfile:
            for i, line in enumerate(csvfile):
                is_header = not line[0].isdigit()
                if not is_header:
                    fields = line.split(",")
                    try:
                        f_date, f_time, f_lat, f_lon, f_alt = fields[0:5]
                    except ValueError:
                        msg = "import_csv: Bad format on row %s in file %s"
                        msg %= (i, filename)
                        msg += " - expected date,time,lat,lon,alt, got %s"
                        msg %= line
                        userbug.add(msg)
                        return
                    f_lat = float(f_lat)
                    f_lon = float(f_lon)
                    f_datetime = f_date + " " + f_time
                    tp = Trackpoint(f_lat, f_lon, f_datetime, f_alt)
                    self.trackpoints.append(tp)
                    if mode == "skim":
                        break

    @logged
    def _import_json(self, filename):
        with open(filename) as f:
            content = f.read()
            j = json.loads(content)

        start_time = fmt.datetime_from_ymd_hms(str(j[u'start_time']))
        for pt in j[u'data']:
            lat, lon, sec = pt
            dateandtime = start_time + datetime.timedelta(0, sec)
            tp = Trackpoint(lat, lon, dateandtime)
            self.trackpoints.append(tp)

    def _import_csv_plan(self, filename):
        f_date = ""
        with open(filename) as csvfile:
            reader = csv.DictReader(csvfile)
            last_date = last_time = ""
            speed = 0
            tp = Trackpoint(0, 0, "2015-01-01 00:00:00")  # To shut up PyCharm
            is_first_row = True
            i_first_tp = i_tp = 0
            for row in reader:
                f_lat = float(row['lat'])
                f_lon = float(row['lon'])
                f_text = row['placemark']
                f_date = row['date']
                f_time = row['time']
                f_break = row['break']
                f_speed = row['speed']
                is_comment = (f_text + " ")[0] == "#"
                if is_comment:
                    continue
                if f_date != "":
                    last_date = f_date
                if last_date == "":
                    userbug.add("No initial date supplied in %s" % filename)
                    return
                if f_time != "":
                    last_time = f_time
                    f_datetime = last_date + " " + last_time
                    a_datetime = fmt.datetime_from_ymd_hms(f_datetime)
                if last_time == "":
                    userbug.add("No initial time supplied in %s" % filename)
                    return
                if f_speed != "":
                    speed = float(f_speed)
                if speed == 0:
                    userbug.add("No initial speed supplied in %s" % filename)
                    return
                if is_first_row:
                    tp = Trackpoint(f_lat, f_lon, a_datetime, text=f_text)
                    self.trackpoints.append(tp)
                    self.fake_relevant_places(tp)
                else:
                    pt = Point(f_lat, f_lon)
                    dist = tp.distance(pt)
                    duration_s = 3600 * dist / speed
                    time_not_given = f_time == ""
                    if time_not_given:
                        a_datetime += datetime.timedelta(seconds=duration_s)
                    tp = Trackpoint(f_lat, f_lon, a_datetime, text=f_text)
                    self.trackpoints.append(tp)

                    we_take_a_break = f_break != ""
                    if we_take_a_break:
                        seg = Segment(self, i_first_tp, i_tp,
                                      self.activity_id, "plan")
                        self.segments.append(seg)
                        i_first_tp = i_tp + 1
                        i_tp += 1
                        hh, mm, ss = f_break.split(":")
                        break_s = int(hh) * 3600 + int(mm) * 60 + int(ss)
                        a_datetime += datetime.timedelta(seconds=break_s)
                        b_text = "+ %s" % f_break
                        tp = Trackpoint(f_lat, f_lon, a_datetime, text=b_text)
                        self.trackpoints.append(tp)

                i_tp += 1
                is_first_row = False
            seg = Segment(self, i_first_tp, i_tp - 1,
                          self.activity_id, "plan end")
            self.segments.append(seg)
            for seg in self.segments:
                print "%s-%s %s %s " % (seg.i_first_tp, seg.i_last_tp, seg.hm_to_hm(), seg.name())
            self.name = f_date + " " + self.name

    def _import_csv_tour(self, filename):
        with open(filename) as csvfile:
            reader = csv.DictReader(csvfile)
            i_tp = 0
            look_pm  = Placemark("Equator", 0, 0)
            last_run_pt = Point(0, 0)

            speed = 60  # km/h along path
            height = 100.0  # m above ground
            rel_dist = 1  # 1 = exactly on top of track, 0.5 = halfway closer
            transition = 1  # seconds to swing camera to new "look_at" point
            tot_dist = 0
            for i, row in enumerate(reader):
                f_lat = row['lat']
                f_lon = row['lon']
                is_comment = (f_lat + " ")[0] == "#"
                if is_comment:
                    continue
                f_look_at = row['look_at']
                f_speed = row['speed']
                f_height = row['height']
                f_rel_dist = row['rel_dist']
                f_transition = row['transition']
                f_comment = row['comment']
                if f_look_at != "":
                    look_pm = _places[f_look_at]
                if f_speed != "":
                    speed = float(f_speed)
                if f_height != "":
                    height = float(f_height)
                if f_rel_dist != "":
                    rel_dist = float(f_rel_dist)
                if f_transition != "":
                    transition = int(f_transition)
                run_pt = Point(f_lat, f_lon)
                heading = run_pt.dir_int(look_pm)
                distance_for_eye = run_pt.distance(look_pm)
                distance_for_foot = run_pt.distance(last_run_pt)
                tot_dist += distance_for_foot
                text = "%s from %s (%s, %s)" % (look_pm.text, f_comment,
                                                run_pt.lat, run_pt.lon)
                eye_pt = Point(look_pm.lat, look_pm.lon, 0, text)
                eye_pt.duration = distance_for_foot / speed * 3600
                if i == 0:
                    eye_pt.lat = run_pt.lat
                    eye_pt.lon = run_pt.lon
                    eye_pt.text = "start"
                    tot_dist = 0
                    heading = 0.01
                    distance_for_eye = 200
                    eye_pt.duration = 5
                eye_pt.heading = heading
                eye_pt.tilt = 90 - degrees(atan(height / 1000 /
                                                distance_for_eye))
                dist = 1000 * rel_dist * distance_for_eye
                range_ = sqrt(dist*dist + height*height)
                eye_pt.range = range_
                print "Ack %.1f eye %.1f heading %.0f duration %.1f range %.0f tilt %.0f" % (
                    tot_dist, distance_for_eye, heading,
                    eye_pt.duration, eye_pt.range, eye_pt.tilt)
                self.tour.append(eye_pt)
                i_tp += 1
                last_run_pt = run_pt

    def _create_tour(self):
        # Create tour from existing trackpoints; assume they're equidistant
        count = len(self.trackpoints)
        tot_distance = self.distance_along_path(0, count - 1)
        look_ahead_km = self.kwargs.get('km', '')
        look_ahead_km = (2.0 if look_ahead_km == "" else float(look_ahead_km))
        height_km = look_ahead_km * 2 / 3
        film_duration_s = self.kwargs.get('parameters', '')
        film_duration_s = (120 if film_duration_s == "" else
                           int(film_duration_s))
        acc_distance = 0
        rel_dist = 0.8  # > 1 means looking from a larger distance
        prev_tp = self.trackpoints[0]
        # assume the trackpoints are equidistant, and
        # find out the delta in number of Trackpoints from
        # the vantage point to the look-at point
        i = 0
        for i, tp in enumerate(self.trackpoints):
            if i == 0:
                continue
            acc_distance += tp.distance(prev_tp)
            if acc_distance > look_ahead_km:
                break
            prev_tp = tp
        look_ahead_index = i
        if look_ahead_index > count:
            bug = "Too large look-ahead horizon %s km (%s pt) "
            bug += "> track distance %s km (%s pt)"
            bug %= (look_ahead_km, look_ahead_index,
                    fmt.km(self.net_dist), count)
            userbug.add(bug)
            return
        i_last_pt = count - look_ahead_index
        film_distance_km = tot_distance - look_ahead_km
        distance_step_km = look_ahead_km / look_ahead_index
        duration_step = (distance_step_km / film_distance_km *
                         film_duration_s)
        pt_look_at = self.trackpoints[0]
        range_ = height_km
        for i_pt in range(0, i_last_pt):
            i_look_at = i_pt + look_ahead_index
            pt_look_at = self.trackpoints[i_look_at]
            pt_look_from = self.trackpoints[i_pt]
            heading = pt_look_from.dir_int(pt_look_at)
            distance_for_eye = pt_look_from.distance(pt_look_at)
            pt_look_at.duration = duration_step
            if i_pt == 0:
                pt_look_at.text = "start"
            pt_look_at.heading = heading
            pt_look_at.tilt = 90 - degrees(atan(height_km /
                                                distance_for_eye))
            dist = 1000 * rel_dist * distance_for_eye
            range_ = sqrt(dist*dist + height_km*height_km)
            range_ = max(range_, height_km * 1000 / 5)
            pt_look_at.range = range_
            print "heading %s tilt %s range %s" % (heading,
                                    pt_look_at.tilt, range_)
            if i_pt == 0:
                pt_look_from.duration = duration_step
                pt_look_from.heading = heading
                pt_look_from.tilt = pt_look_at.tilt
                pt_look_from.range = height_km * 1000 / 5
                pt_look_at.duration = 5
                self.tour.append(pt_look_from)
            self.tour.append(pt_look_at)
        pt_look_at.range = range_ / 8
        pt_look_at.duration = 4
        self.tour.append(pt_look_at)

    def _import_csv_tour_g(self, filename):
        with open(filename) as csvfile:
            reader = csv.DictReader(csvfile)
            i_tp = 0
            last_pt = Point(0, 0)
            duration = 3
            tilt = 65
            range = 500
            for row in reader:
                f_lat = float(row['lat'])
                f_lon = float(row['lon'])
                f_duration = row['duration']
                f_heading = row['heading']
                f_tilt = row['tilt']
                f_range = row['range']
                pt = Point(f_lat, f_lon)
                heading = last_pt.dir_int(pt)
                if f_duration != "":
                    duration = float(f_duration)
                if f_heading != "":
                    heading = float(f_heading)
                if f_tilt != "":
                    tilt = float(f_tilt)
                if f_range != "":
                    range = int(f_range)
                pt.duration = duration
                pt.heading = heading
                pt.tilt = tilt
                pt.range = range
                self.tour.append(pt)
                last_pt = pt
                i_tp += 1

    def _import_kml_plan(self, filename):
        f = codecs.open(filename, 'r')
        last_date = last_time = ""
        speed = 0
        tp = Trackpoint(0, 0, "2015-01-01 00:00:00")  # To shut up PyCharm
        is_first_row = True
        i_first_tp = i_tp = 0
        is_line_string = False
        f_lat = f_lon = f_text = f_break = f_folder = f_date = ""
        folder_level = 0
        folder_or_placemark = ""
        for line in f:
            has_folder = '<Folder>' in line
            eof_folder = '</Folder>' in line
            has_placemark = 'Placemark>' in line
            eof_placemark = '</Placemark>' in line
            has_name = '<name>' in line
            has_coordinates = '<coordinates>' in line
            if has_folder:
                folder_level += 1
                if folder_level > 1:
                    e = "Filename %s has %s folder levels"
                    e %= (filename, folder_level)
                    e %= "\nbut in planning only one level is allowed"
                    userbug.add(e)
                folder_or_placemark = "folder"
            if eof_folder:
                folder_level -= 1
            if has_placemark:
                folder_or_placemark = "placemark"
            if has_name:
                tag_value = line.replace(">", "<").split('<')[2]
                tag_value = tag_value.replace('&apos;', "'")
                if folder_or_placemark == 'folder':
                    f_folder = tag_value
                else:  # placemark
                    f_text = tag_value.replace('&apos;', "'")
            if has_coordinates:
                is_line_string = False
                has_comma = ',' in line
                if not has_comma:
                    is_line_string = True
                else:
                    line = line.replace(">", "<").split('<')[2].split(',')
                    f_lon, f_lat, f_alt = line
            if eof_placemark:
                if not is_line_string:
                    if "D=" in f_text:
                        f_date = f_text.split("D=")[1].split()[0]
                    else:
                        f_date = ""
                    if "T=" in f_text:
                        f_time = f_text.split("T=")[1].split()[0]
                        f_time = lib.append_to_hh_mm_ss(f_time)
                    else:
                        f_time = ""
                    if "P=" in f_text:
                        f_break = f_text.split("P=")[1].split()[0]
                        f_break = lib.append_to_hh_mm_ss(f_break)
                    else:
                        f_break = ""
                    if "S=" in f_text:
                        f_speed = f_text.split("S=")[1].split()[0]
                        f_speed = f_speed.replace(",", ".")
                        speed = float(f_speed)
                    if f_date != "":
                        last_date = f_date
                    if last_date == "":
                        userbug.add("No initial date supplied in %s" %
                                    filename)
                        last_date = "2020-01-01"
                    if f_time != "":
                        last_time = f_time
                        f_datetime = last_date + " " + last_time
                        a_datetime = fmt.datetime_from_ymd_hms(f_datetime)
                    if last_time == "":
                        userbug.add("No initial time supplied in %s" %
                                    filename)
                        last_time = "08:00"
                    if f_speed != "":
                        speed = float(f_speed)
                    if speed == 0:
                        userbug.add("No initial speed supplied in %s" %
                                    filename)
                        speed = 5
                    if is_first_row:
                        tp = Trackpoint(f_lat, f_lon, a_datetime, text=f_text)
                        self.trackpoints.append(tp)
                        self.fake_relevant_places(tp)
                    else:
                        pt = Point(f_lat, f_lon)
                        dist = tp.distance(pt)
                        duration = 3600 * dist / speed
                        #print "dist %s duration %s" % (dist, duration)
                        time_not_given = f_time == ""
                        if time_not_given:
                            a_datetime += datetime.timedelta(seconds=duration)
                        #print "i_tp %s f_time %s time %s text %s" % (i_tp, f_time, a_datetime, f_text)
                        tp = Trackpoint(f_lat, f_lon, a_datetime, text=f_text)
                        self.trackpoints.append(tp)

                        we_take_a_break = f_break != ""
                        if we_take_a_break:
                            seg = Segment(self, i_first_tp, i_tp,
                                          self.activity_id, "plan")
                            self.segments.append(seg)
                            i_first_tp = i_tp + 1
                            i_tp += 1
                            hh, mm, ss = f_break.split(":")
                            break_s = int(hh) * 3600 + int(mm) * 60 + int(ss)
                            a_datetime += datetime.timedelta(seconds=break_s)
                            b_text = "+ %s" % f_break
                            tp = Trackpoint(f_lat, f_lon, a_datetime,
                                            text=b_text)
                            self.trackpoints.append(tp)

                    i_tp += 1
                    is_first_row = False
        seg = Segment(self, i_first_tp, i_tp - 1, self.activity_id, "plan end")
        self.segments.append(seg)
        for seg in self.segments:
            print "%s-%s %s %s " % (seg.i_first_tp, seg.i_last_tp, seg.hm_to_hm(), seg.name())
        self.name = f_date + " " + f_folder

    def fake_relevant_places(self, tp):
        p1 = Point(int(tp.lat) - 1, int(tp.lon) - 1)
        p2 = Point(int(tp.lat) + 1, int(tp.lon) + 1)
        self.relevant_places = Places("copy", original=_places, p1=p1, p2=p2)

    def create_timepoints(self):
        def reset_values():
            for field in fields:
                values[field] = 0

        def accumulate_values():
            values['count'] += 1
            values['distance'] += distance
            values['hm_up'] += hm_up
            values['hm_down'] += hm_down
            values['max_slope_up'] = max(slope, values['max_slope_up'])
            values['max_slope_down'] = min(slope, values['max_slope_down'])
            values['max_speed'] = max(speed, values['max_speed'])
            values['dist_n'] += dist_n
            values['dist_e'] += dist_e
            values['dist_s'] += dist_s
            values['dist_w'] += dist_w

        def cap_values():
            movement_m = values['distance'] * 1000
            if movement_m < 50:  # Movement < 50 m, i.e. speed < 3 km/h
                values['max_slope_down'] = 0
                # Any other value is likely a measurement error
                values['max_slope_up'] = 0
                values['max_speed'] = 0
            if movement_m < 100:  # Movement < 100 m, i.e. speed < 6 km/h
                going_downhill = (abs(values['max_slope_down']) >
                                  values['max_slope_up'])
                if going_downhill:  # Downhill the limits can be set higher
                    values['max_slope_down'] = 0
                    values['max_slope_up'] = 0
                    values['max_speed'] = 0

        fields = ['count', 'distance', 'dist_n', 'dist_e', 'dist_s', 'dist_w',
                  'hm_up', 'hm_down', 'max_slope_up', 'max_slope_down',
                  'max_speed']
        values = {}
        reset_values()
        last_tp = self.trackpoints[0]
        last_minute = ""
        last_dateandtime = datetime.datetime.min
        # Just to indicate the right type of last_dateandtime
        for tp in self.trackpoints:
            lat, lon, alt = tp.lat, tp.lon, tp.alt
            dateandtime = tp.datetime
            second = dateandtime.strftime('%S')
            distance = tp.distance(last_tp)
            alt_diff = tp.alt - last_tp.alt
            alt_diff = 0 if alt_diff is None else alt_diff
            hm_up = alt_diff if alt_diff > 0 else 0
            hm_down = alt_diff if alt_diff < 0 else 0
            slope = (degrees(atan(0.001 * alt_diff / distance))
                     if distance != 0 else 0)
            dist_ns = geo.lat_diff2km(tp.lat - last_tp.lat)
            dist_ew = geo.lon_diff2km(tp.lon - last_tp.lon, tp.lat)
            dist_n = dist_ns if dist_ns > 0 else 0
            dist_s = dist_ns if dist_ns < 0 else 0
            dist_e = dist_ew if dist_ew > 0 else 0
            dist_w = dist_ew if dist_ew < 0 else 0
            duration = tp.seconds(last_tp)
            speed = distance * 3600 / duration if duration != 0 else 0
            minute = tp.time_hm()
            if minute != last_minute:
                if last_minute != "":
                    if second == "00" and duration <= 60:
                        accumulate_values()
                    time_just_minute = last_dateandtime.replace(second=0,
                                                                microsecond=0)
                    closest_pm = self.relevant_places.closest_placemark(tp)
                    text = closest_pm.text
                    cap_values()
                    time_pt = Timepoint(lat, lon, time_just_minute, alt,
                                        text, **values)
                    minute = time_pt.minute
                    self.timepoints[minute] = time_pt
                    reset_values()
            accumulate_values()
            last_tp = tp
            last_minute = minute
            last_dateandtime = dateandtime

    def _calc_timepoints(self):
        timepoint_list = list(self.timepoints)
        timepoint_list.sort()
        for minute in timepoint_list:
            timepoint = self.timepoints[minute].as_dict()

    def _list_timepoints(self):
        time_start_minute = self.trackpoints[0].datetime.replace(second=0)
        time_end_minute = self.trackpoints[len(self.trackpoints) -
                                           1].datetime.replace(second=0)
        time_minute = time_start_minute
        one_minute = datetime.timedelta(minutes=1)
        while time_minute <= time_end_minute:
            minute = fmt.hm(time_minute)
            timepoint = self.timepoints.get(minute)
            if timepoint is None:
                print("%s -" % minute)
            else:
                print(str(timepoint))
            time_minute += one_minute

    def calc_milestones(self):
        tick_long = _activities[self.activity_id].tick_long.replace("km", "")
        tick_long = float(tick_long)
        trackpoints = self.compressed.trackpoints
        self.milestones = self.equidistant_points(trackpoints, tick_long)

    def equidistant_points(self, trackpoints, equidistance, type_="Placemark"):
        result_points = []
        acc_dist = 0
        last_tp = trackpoints[0]
        prev_datetime = last_tp.datetime
        for i, tp in enumerate(trackpoints):
            if i > 0:
                prev_tick = int(acc_dist / equidistance)
                dist = tp.distance(last_tp)
                new_tick = int((acc_dist + dist) / equidistance)
                if prev_tick != new_tick:
                    for tick in range(prev_tick + 1, new_tick + 1):
                        xtra_dist = tick*equidistance - acc_dist
                        lat_diff = tp.lat - last_tp.lat
                        lon_diff = tp.lon - last_tp.lon
                        seconds_diff = tp.seconds(last_tp)
                        mid_lat = last_tp.lat + xtra_dist / dist * lat_diff
                        mid_lon = last_tp.lon + xtra_dist / dist * lon_diff
                        mid_seconds = int(xtra_dist / dist * seconds_diff)
                        mid_delta = datetime.timedelta(seconds=mid_seconds)
                        mid_datetime = last_tp.datetime + mid_delta
                        text = fmt.hm(mid_datetime)
                        diff = mid_datetime - prev_datetime
                        km_seconds = abs(diff).total_seconds()
                        duration = fmt.sec_as_hm(km_seconds)
                        text += " (%s)" % duration
                        placetype_id = tick % 10
                        if placetype_id == 0:
                            placetype_id = 10
                        descr = "%s km" % int(tick * equidistance)
                        placetype_id = str(placetype_id)
                        if type_ == "Placemark":
                            pm = Placemark(text, mid_lat, mid_lon, descr=descr,
                                           placetype_id=placetype_id)
                            result_points.append(pm)
                        else:
                            e_tp = Trackpoint(mid_lat, mid_lon, mid_datetime)
                            result_points.append(e_tp)
                        prev_datetime = mid_datetime
                acc_dist += dist
                last_tp = tp
        return result_points

    def running_average(self, points, window_points=21):
        window = []
        running = []
        look_ahead = (window_points - 1) / 2
        count = len(points)
        window_size = 0
        tot_lat = 0  # first_pt.lat * window_points
        tot_lon = 0  # first_pt.lon * window_points
        for i, pt in enumerate(points):
            window.append(pt)
            window_size += 1
            tot_lat += pt.lat
            tot_lon += pt.lon
            past_start = i >= window_points
            if past_start:
                drop_pt = window.pop(0)
                window_size -= 1
                tot_lat -= drop_pt.lat
                tot_lon -= drop_pt.lon
                mid_pt = window[look_ahead]
                avg_pt = Trackpoint(tot_lat / window_size,
                                    tot_lon / window_size,
                                    mid_pt.datetime)
                running.append(avg_pt)
                at_end = i == count - 1
                if at_end:
                    for j in range(0, look_ahead):
                        for k in range(0, 2):
                            drop_pt = window.pop(0)
                            window_size -= 1
                            tot_lat -= drop_pt.lat
                            tot_lon -= drop_pt.lon
                        mid_pt = window[(window_size - 1)/2]
                        avg_pt = Trackpoint(tot_lat / window_size,
                                            tot_lon / window_size,
                                            mid_pt.datetime)
                        running.append(avg_pt)
            else:
                just_grow_window = i % 2 == 0
                if not just_grow_window:
                    mid_pt = window[(i - 1)/2]
                    avg_pt = Trackpoint(tot_lat / window_size,
                                        tot_lon / window_size,
                                        mid_pt.datetime)
                    running.append(avg_pt)
        return running

    def color(self, tp):
        if self.activity_id in ['downhill', 'snowboard']:
            return self.timepoint_color(tp)
        color1 = _activities[self.activity_id].color1
        color2 = _activities[self.activity_id].color2
        # todo color2 is for up/downhill, once implemented
        return "#" + color1

    def timepoint_color(self, tp):
        time = tp.time_hm()
        timepoint = self.timepoints.get(time)
        if timepoint is None:
            return "Grey"
        max_slope_down = abs(timepoint.max_slope_down)
        color = ("black" if max_slope_down > 24 else
            "Red" if max_slope_down > 16 else
            "Blue" if max_slope_down > 8 else
            "Green" if max_slope_down > 1 else "Grey")
        return color

    def distance_along_path(self, i_from, i_to):
        """Distance from index point i_from to i_to (both points included)"""
        s = float(0)
        cnt = self.count()
        if i_from > cnt - 1:
            userbug.add("Track.distance_along_path: i_from " +
                        "%s > cnt %s - 1 in filename %s" % (i_from, cnt,
                                                            self.filename))
            return 0
        if i_to > cnt - 1:
            userbug.add("Track.distance_along_path: i_to " +
                        "%s > cnt %s - 1 in filename %s" % (i_to, cnt,
                                                            self.filename))
            return 0
        if cnt == 0:
            userbug.add("Track.distance_along_path: cnt = 0 (zero) " +
                        "in filename %s" % self.filename)
            return 0
        prev_tp = self.trackpoints[i_from]
        for i_tp in range(i_from + 1, i_to + 1):
            tp = self.trackpoints[i_tp]
            s += tp.distance(prev_tp)
            prev_tp = tp
        return s

    @logged
    def _eliminate_still_points(self):
        """Skip still points at beginning and end, and middle points
        surrounded by points at exact same location"""
        recent_movement = False
        element_count = len(self.trackpoints)
        if element_count < 2:
            return
        for i in range(element_count - 1, -1, -1):
            tp = self.trackpoints[i]
            if i == element_count - 1:
                prev_tp = self.trackpoints[i - 1]
                same_as_prev = tp.is_same_lat_lon(prev_tp)
                if same_as_prev:
                    del self.trackpoints[i]
                else:
                    recent_movement = True
            elif i == 0:
                if len(self.trackpoints) > 1:
                    same_as_next = tp.is_same_lat_lon(self.trackpoints[1])
                    if same_as_next:
                        del self.trackpoints[i]
            else:
                prev_tp = self.trackpoints[i - 1]
                same_as_prev = tp.is_same_lat_lon(prev_tp)
                if same_as_prev:
                    if not recent_movement:
                        del self.trackpoints[i]
                    recent_movement = False
                else:
                    recent_movement = True

    @logged
    def _suggest_segments(self):
        # First segment start: mode 'before_first_start'
        # - "If in the last 60 seconds movement is more than 20 metres, find
        # the first point where movement was more than 1 metre;
        # mark that trackpoint as the start position"
        #
        # Segment end == break start: mode 'movement_happens'
        # - "If in the last 60 seconds movement is less than 20 metres,
        # find the last point where movement was more than 1 metre;
        # mark that trackpoint as the break position"
        #
        # New segment start == break end: mode 'break_time'
        # - "If the distance from the break position is more than 20 metres,
        # find the first point during the last 60 seconds where movement
        # was more than 1 metre"
        #
        # Last segment end: mode 'break_time'
        # - "If no more measurements exist and we're still looking for
        # a new segment, remove the last break position as it wasn't a break"
        #
        # When all is said and done, delete all 'breaks' that are shorter than
        # 120 seconds, by merging them with their surrounding segments
        #
        # Deliverables:
        # - self.segments [date, time_from, time_to, activity, suggested_name]
        # - self.breaks (indirectly, derived from segments)
        #    [date, from_and_to, suggested_name]

        if self.count() == 0:
            userbug.add("No point to suggest segments without trackpoints")
            return

        # Settings by user:
        # - time_window_s = 60 - todo ngt med limit
        # - window_dist_m = 20
        # - final_hop_m = 1
        # - minimum_break_s = 120
        activity_id = self.activity_id
        activity = _activities[activity_id]
        invalid_activity = isinstance(activity, str)
        if invalid_activity:
            activity = _activities['run']
        time_window_s = float(activity.time_window_s.replace("s", ""))
        window_dist_m = float(activity.window_dist_m.replace("m", ""))
        final_hop_m = float(activity.final_hop_m.replace("m", ""))
        minimum_break_s = float(activity.minimum_break_s.replace("s", ""))

        # minimum_segment_m = float(activity.minimum_segment_m.replace("s",
        # ""))
        # Key variables:
        # - distance_list: list with max 60 pairs of
        # [duration s since start, distance m since start]
        # where start = first trackpoint time (seconds are needed
        # since trackpoints don't necessarily come at 1 Hz rate)
        distance_list = []
        distance_list_length = 0
        i_segment_first_tp = i_segment_last_tp = 0

        window_dist_km = window_dist_m / 1000
        final_hop_km = final_hop_m / 1000
        mode = "before_first_start"
        dist_from_start = 0
        first_tp = self.trackpoints[0]
        break_tp = prev_tp = first_tp
        i_segment = 0
        for i_tp, tp in enumerate(self.trackpoints):
            seconds_from_start = tp.seconds(first_tp)
            delta_dist = tp.distance(prev_tp)
            prev_tp = tp
            dist_from_start += delta_dist
            distance_list.append({'s': seconds_from_start,
                                  'd': dist_from_start, 'i': i_tp})
            distance_list_length += 1
            # remove unnecessary points from beginning of list,
            # so the window conforms to time_window_s
            i_entries_to_delete = -1
            for entry in distance_list:
                old_s = entry['s']
                time_window_too_large = (seconds_from_start - old_s >
                                         time_window_s)
                if time_window_too_large:
                    i_entries_to_delete += 1
                else:
                    break
            for i in range(0, i_entries_to_delete):
                del distance_list[0]
                distance_list_length -= 1
            to_window_start_d = distance_list[0]['d']
            distance_within_time_window = dist_from_start - to_window_start_d
            window_size_s = (distance_list[distance_list_length - 1]['s'] -
                             distance_list[0]['s'])
            if window_size_s < time_window_s:
                continue
                # Don't start looking until minimum window is built up (again)
            #print "%s: %.3f km %s s" % (mode, distance_within_time_window,
            #                            window_size_s)
            if mode == "before_first_start":
                has_started = distance_within_time_window > window_dist_km
                if has_started:
                    # find the first point where movement was more than 1 metre
                    for i in range(1, distance_list_length):
                        hop_km = (distance_list[i]['d'] -
                                  distance_list[i - 1]['d'])
                        hop_big_enough = hop_km > final_hop_km
                        if hop_big_enough:
                            break
                    # mark that trackpoint as the start position
                    i_segment_first_tp = distance_list[i]['i']
                    segment_start_time = self.trackpoints[
                        i_segment_first_tp].time_hms()
                    mode = "movement_happens"
                    distance_list = []
                    distance_list_length = 0

            if mode == "movement_happens":
                has_stopped = distance_within_time_window < window_dist_km
                if has_stopped:
                    stop_msg = "%s m" % int(distance_within_time_window * 1000)
                    stop_msg += " < %s m" % int(window_dist_m)
                    stop_msg += " within %s s" % int(window_size_s)
                    # find the last point where movement was more than 1 metre
                    for i in range(distance_list_length - 2, -1, -1):
                        hop_km = (distance_list[i + 1]['d'] -
                                  distance_list[i]['d'])
                        hop_big_enough = hop_km > final_hop_km
                        if hop_big_enough:
                            break
                    # mark that trackpoint as the break position
                    i_segment_last_tp = distance_list[i]['i']
                    break_tp = self.trackpoints[i_segment_last_tp]
                    i_segment += 1
                    segment = Segment(self, i_segment_first_tp,
                                      i_segment_last_tp, activity_id,
                                      "has_stopped %s" % stop_msg)
                    self.segments.append(segment)
                    mode = "break_time"
                    distance_list = []
                    distance_list_length = 0

            if mode == "break_time":
                distance_from_break_tp = tp.distance(break_tp)
                has_started = distance_from_break_tp > window_dist_km
                if has_started:
                    # find the first point where movement was more than 1 metre
                    for i in range(1, distance_list_length):
                        hop_km = (distance_list[i]['d'] -
                                  distance_list[i - 1]['d'])
                        hop_big_enough = hop_km > final_hop_km
                        if hop_big_enough:
                            break
                    # mark that trackpoint as the start position
                    i_segment_first_tp = distance_list[i]['i']
                    mode = "movement_happens"
                    distance_list = []
                    distance_list_length = 0
        if mode == "movement_happens":
            # Last segment ended abruptly (it's not yet noted)
            i_segment_last_tp = self.count() - 1
            i_segment += 1
            segment = Segment(self, i_segment_first_tp, i_segment_last_tp,
                              activity_id, "abrupt_end")
            self.segments.append(segment)

        elif mode == "break_time":
            # Last segment ended softly (it's already noted)
            pass

        # Eliminate too short breaks by merging the adjacent segments
        segment_count = len(self.segments)
        for i_segment in range(segment_count - 2, -1, -1):
            i_this_segment_last_tp = self.segments[i_segment].i_last_tp
            i_next_segment_first_tp = self.segments[i_segment + 1].i_first_tp
            this_segment_last_tp = self.trackpoints[i_this_segment_last_tp]
            next_segment_first_tp = self.trackpoints[i_next_segment_first_tp]
            break_length = this_segment_last_tp.seconds(next_segment_first_tp)
            can_be_merged = break_length < minimum_break_s
            if can_be_merged:
                self.segments[i_segment].i_last_tp = self.segments[
                    i_segment + 1].i_last_tp
                self.segments[i_segment].last['time'] = self.segments[
                    i_segment + 1].last['time']
                self.segments[i_segment].recalc()
                del self.segments[i_segment + 1]

    def eliminate_too_short_segments(self):
        activity_id = self.activity_id
        activity = _activities[activity_id]
        time_window_s = float(activity.time_window_s.replace("s", ""))
        segment_count = len(self.segments)
        for i_segment in range(segment_count - 1, -1, -1):
            segment = self.segments[i_segment]
            #segment.calc()
            i_this_segment_last_tp = self.segments[i_segment].i_last_tp
            i_this_segment_first_tp = self.segments[i_segment].i_first_tp
            this_segment_last_tp = self.trackpoints[i_this_segment_last_tp]
            this_segment_first_tp = self.trackpoints[i_this_segment_first_tp]
            segment_length = this_segment_last_tp.seconds(
                                        this_segment_first_tp)
            can_be_deleted = segment_length < time_window_s
            can_be_deleted = can_be_deleted or segment.distance < 0.1
            if can_be_deleted:
                del self.segments[i_segment]

    def update_previous_next_pointers(self):
        # Now that the segments are clean, enter chain pointers
        # to previous segments and next segments
        previous_segment = None  # Just to shut up warning
        first_segment = True
        for segment in self.segments:
            if not first_segment:
                segment.set_previous(previous_segment)
                previous_segment.set_next(segment)
            first_segment = False
            previous_segment = segment

    def calc_track_net(self):
        net_dist = 0
        net_duration_s = 0
        for i, segment in enumerate(self.segments):
            segment.calc_distance_duration()
            net_dist += segment.distance
            net_duration_s += segment.duration_s

        self.net_dist = net_dist
        self.net_duration_s = net_duration_s
        self.net_duration = fmt.sec_as_hms(net_duration_s)
        net_duration_s = 999 if net_duration_s == 0 else net_duration_s
        self.net_speed_kmh = fmt.km(geo.km_h(
            1000.0 * net_dist / net_duration_s)) + "/h"

    def _adjust_segment_activities(self):
        for i, segment in enumerate(self.segments):
            segment.adjust_activity()

    def _sort_by_activity(self):
        self.segments.sort(key=lambda x: x.order_activity)

    def _calc_activities(self):
        for seg in self.segments:
            activity_id = seg.activity_id
            if activity_id not in self.activities:
                self.activities.append(activity_id)

    @logged
    def _split_track_at_peaks(self):
        seg_count = len(self.segments)
        for i_seg in range(seg_count - 1, -1, -1):
            segment = self.segments[i_seg]
            extreme_count = len(segment.extremes)
            was_split = False
            for i_extreme in range(extreme_count - 1, -1, -1):
                was_split = True
                extreme = segment.extremes[i_extreme]
                i_old_seg = i_seg
                self._split_segment_at(i_old_seg, extreme['i_tp'])
            #if was_split:
            #    self.segments[i_seg].recalc()
            #    self.segments[i_seg + 1].recalc()
        for i, segment in enumerate(self.segments):
            if segment.activity_id in ["downhill", "snowboard"]:
                if abs(segment.hm_up) > abs(segment.hm_down):
                    segment.activity_id = "lift"  # Todo Borest bör fixas

    def _split_track_at_transits(self):
        seg_count = len(self.segments)
        for i_seg in range(seg_count - 1, -1, -1):
            segment = self.segments[i_seg]
            transit_count = len(segment.transits)
            segment.transits.sort()
            #if transit_count > 0:
            #    print "splitting segment %s %s" % (i_seg, segment.hm_to_hm())
            for i_transit in range(transit_count - 1, -1, -1):
                transit = segment.transits[i_transit]
                #print "i_transit %s i_tp %s" % (i_transit, transit)
                i_old_seg = i_seg
                self._split_segment_at(i_old_seg, transit)

    def _split_segment_at(self, i_seg, i_tp):
        segment = self.segments[i_seg]
        i_old_first = segment.i_first_tp
        i_old_last = segment.i_last_tp
        time = segment.track.trackpoints[i_tp].time_hms()
        new_segment = Segment(self, i_tp, i_old_last, segment.activity_id,
                              "split")
        #print "split %s (%s-%s) at %s = %s" % (i_seg, i_old_first,
        #                                  i_old_last, i_tp, time)
        segment.i_last_tp = i_tp
        segment.recalc()
        self.segments.insert(i_seg + 1, new_segment)

    @logged
    def _compress_track(self, c_t_ratio=None):
        if c_t_ratio is None:
            c_t_ratio = 0.00001
            # such as 0.005 = 0,5 % of the length
        c_t = self.net_dist * c_t_ratio
        new_track = Track(None, mode="empty", diary=self.diary)
        new_track.segments = []
        new_track.relevant_places = self.relevant_places
        i_new_track = 0
        i_segment = 0

        # Assume the track is split into segments
        for segment in self.segments:
            c_l = []
            i_p1 = segment.i_first_tp
            i_p2 = segment.i_last_tp
            c_l.append(i_p1)
            c_l.append(i_p2)
            i_p1_new_track = i_new_track
            c_t_rough = 0.02 if "lift" in segment.activity_id else c_t
            self._compress_section(i_p1, i_p2, c_t_rough, c_l)
            c_l.sort()
            # Make a new compressed track (including segments) based on
            # the points on the compression list
            for i in c_l:
                tp = self.trackpoints[i]
                new_track.trackpoints.append(tp)
                i_new_track += 1
            i_p2_new_track = i_new_track - 1
            i_segment += 1
            new_segment = Segment(new_track, i_p1_new_track, i_p2_new_track,
                                  segment.activity_id, "compress")
            new_track.segments.append(new_segment)

        previous_segment = None  # Just to shut up warnings
        first_segment = True
        for segment in new_track.segments:
            if not first_segment:
                segment.set_previous(previous_segment)
                previous_segment.set_next(segment)
            first_segment = False
            previous_segment = segment

        new_track.calc_track_net()

        #print("Track compressed from %s to %s points at %s %%" % (
        #    len(self.trackpoints), len(new_track.trackpoints), c_t))
        #print("old length: %s new: %s" % (self.net_dist, new_track.net_dist))
        return new_track

    def _compress_section(self, i_p1, i_p2, c_t, c_l):
        # Compress the section from i_p1 to i_p2, with a tolerance distance of
        # c_t, updating the results into compression list c_l

        # Make d_s = distance as a straight line from i_p1 to i_p2
        tp1 = self.trackpoints[i_p1]
        tp2 = self.trackpoints[i_p2]
        d_s = tp1.distance(tp2)

        i_pga = i_pgb = d1a2 = d1b2 = 0  # Just to shut up warnings
        a_is_better_guess = False  # Just to shut up warnings
        i_pg1 = i_p1
        i_pg2 = i_p2

        borders_have_converged = False

        # find the intermediate index i_p1 < i_pi < i_p2 with the maximal
        # distance from i_p1 via i_pi to i_p2
        while not borders_have_converged:
            # split the distance into thirds, and skip first or last third
            i_diff = i_pg2 - i_pg1
            i_third = int((i_diff + 1) / 3)
            i_pga = i_pg1 + i_third
            i_pgb = i_pg2 - i_third
            tpga = self.trackpoints[i_pga]
            tpgb = self.trackpoints[i_pgb]
            d1a2 = tp1.distance(tpga) + tpga.distance(tp2)
            d1b2 = tp1.distance(tpgb) + tpgb.distance(tp2)
            a_is_better_guess = d1a2 > d1b2
            if a_is_better_guess:
                i_pg2 = i_pgb  # Cut off the last third
            else:
                i_pg1 = i_pga  # Cut off the first third
            borders_have_converged = (abs(i_pg1 - i_pg2) <= 1)

        if a_is_better_guess:
            i_pi = i_pga
            d_n = d1a2
        else:
            i_pi = i_pgb
            d_n = d1b2

        significant_improvement = (d_n - d_s) > c_t
        if significant_improvement:
            c_l.append(i_pi)  # Found new point of the compressed track
            self._compress_section(i_p1, i_pi, c_t, c_l)
            # Before the chosen intermediate point
            self._compress_section(i_pi, i_p2, c_t, c_l)
            # After the chosen intermediate point

    def as_json(self):
        tp_date = self.trackpoints[0].date_dmyy()
        try:
            activity_name = _activities[self.activity_id].name
        except TypeError:
            activity_name = ""
        header = "%s %s %s" % (tp_date, activity_name, self.name)

        k = '''\
{"map_defaults": {
    "center": {"lat": %s, "lon": %s},
    "bounds": {
        "southWest": {"lat": %s, "lon": %s},
        "northEast": {"lat": %s, "lon": %s}
        }
    },\n'''
        start_point = self.compressed.trackpoints[0]
        end_point = self.compressed.trackpoints[-1]
        start_time = start_point.datetime
        end_time = end_point.datetime
        label = "= %s / %s (%s)" % (fmt.km(self.net_dist), self.net_duration,
                                    self.net_speed_kmh )
        lats_lons = [self.map_area['mid']['lat'], self.map_area['mid']['lon'],
                     self.map_area['min']['lat'], self.map_area['min']['lon'],
                     self.map_area['max']['lat'], self.map_area['max']['lon']]
        lats_lons = map(geo.lat_lon_5, lats_lons)
        k = k % tuple(lats_lons)
        k += '''\
    "layers": {
        "segments": {
            "layer_type": "track",
            "layer_title": "%s",
            "points": ['''
        route_is_a_loop = start_point.distance(end_point) < 0.1
        # 100 m, hard coded
        if route_is_a_loop:
            k += '''
                [{ "lat": %s, "lon": %s, "point_type": "marker-loop",
                    "point_label": "%s", "point_datetime": "%s"}]'''
            k = k % (label, start_point.lat_5(), start_point.lon_5(), label,
                     end_time)
        else:
            k += '''
                [{ "lat": %s, "lon": %s, "point_type": "marker-start",
                    "point_label": "%s", "point_datetime": "%s"}],
                [{ "lat": %s, "lon": %s, "point_type": "marker-end",
                    "point_label": "%s", "point_datetime": "%s"}]'''
            k = k % (label, start_point.lat_5(), start_point.lon_5(),
                     start_time, start_time,
                     end_point.lat, end_point.lon, label, end_time)
        c = len(self.compressed.segments)
        i = 0
        for segment in self.compressed.segments:
            i += 1
            if i == c:
                break  # Last segment does not end in a rest marker,
                # but in the stop (or loop) marker

            label = "%s. %s (%s UTC)" % (i, segment.break_duration_hm(),
                                         segment.break_hm_to_hm())
            s = ''',
                [{ "lat": %s, "lon": %s, "point_type": "marker-rest",
                    "point_label": "%s", "point_datetime": "%s"}]'''
            s = s % (segment.last['tp'].lat, segment.last['tp'].lon, label,
                     segment.last['tp'].datetime)
            k += s

        k += '''\
                ]
            }'''

        i_segment = 0
        for segment in self.compressed.segments:
            i_segment += 1
            k += ''',
            "track%s": {
                "layer_type": "track",
                "layer_title": "%s",
                "points": [\n''' % (i_segment, str(segment))

            i = 0
            c = len(self.compressed.trackpoints)
            for tp in self.compressed.trackpoints:
                i += 1
                if i < segment.i_first_tp:
                    continue
                is_last = (i > segment.i_last_tp) or (i == c)
                k += " " * 16 + tp.as_json_coordinate()
                if not is_last:
                    k += ",\n"
                else:
                    break

            k += '''
                ]
                }\n'''

        i_segment = 0
        for segment in self.zipped.segments:
            i_segment += 1
            k += ''',
            "trackzip%s": {
                "layer_type": "trackzip",
                "layer_title": "zip%s",
                "points": [\n''' % (i_segment, str(segment))

            i = 0
            c = len(self.zipped.trackpoints)
            for tp in self.zipped.trackpoints:
                i += 1
                if i < segment.i_first_tp:
                    continue
                is_last = (i > segment.i_last_tp) or (i == c)
                k += " " * 16 + tp.as_json_coordinate()
                if not is_last:
                    k += ",\n"
                else:
                    break

            k += '''
                ]
                }\n'''
        k += '''\
        }
    }'''
        return k

    def as_kml(self):
        if self.mode == "tour":
            return self.as_kml_tour()
        seg_fmt = "{time_start:.5}-{time_stop:.5} {distance_fmt} "
        seg_fmt += "{duration} {speed_fmt} %s"
        header = self.kwargs['header']
        param_color = self.kwargs['parameters']
        doing_single_file = self.kwargs.get('command') == 'Track'
        if doing_single_file:
            header = "%s %s" % (self.date, header)
        k = kml.doc_header(header)
        last_activity_id = last_date_name = ""
        first_activity = True
        for seg in self.compressed.segments:
            seg_dict = seg.as_dict()
            activity_id = seg.activity_id
            activity_name = _activities[activity_id].name
            color = _activities[activity_id].color1
            color = param_color if param_color != "" else color
            color = lib.rgb2aabbggrr(color)
            color2 = _activities[activity_id].color2
            date_name = str(seg_dict['date']) + " "  # +seg_dict['date_header']
            u_safe_name = seg_dict['name'].decode("utf-8")
            u_safe_name = u_safe_name[0:20].encode("utf-8")
            seg_name = seg_fmt.format(**seg_dict) % u_safe_name
            new_activity_id = activity_id != last_activity_id
            new_date = date_name != last_date_name
            if new_activity_id:
                if not first_activity:
                    if not doing_single_file:
                        k += kml.end_section(last_date_name)
                    k += kml.end_section(last_activity_id)
                k += kml.begin_section(activity_name, comment=activity_id)
                if not doing_single_file:
                    k += kml.begin_section(date_name)
            elif new_date and not doing_single_file:
                k += kml.end_section(last_date_name)
                k += kml.begin_section(date_name)
            k += kml.placemark_header(seg_name)
            k += kml.linestyle_header_footer(color)
            k += kml.linestring_pure_header()

            for trackpoint in seg:
                k += trackpoint.as_coordinate_tag()
            k += kml.linestring_footer()
            k += kml.placemark_footer()
            last_activity_id = activity_id
            last_date_name = date_name
            first_activity = False

        k += kml.begin_section('Start, stop, breaks')
        for seg in self.compressed.segments:
            is_first_segment = seg.previous_segment is None
            is_last_segment = seg.next_segment is None
            if is_first_segment:
                k += kml.placemark_header(seg.first['tp'].time_hm())
                icon_url = _placetypes['start'].url
                k += kml.point_header_footer(
                    seg.first['tp'].as_coordinate_tag(), icon_url)
                k += kml.placemark_footer()

            if is_last_segment:
                k += kml.placemark_header(seg.last['tp'].time_hm())
                icon_url = _placetypes['stop'].url
                k += kml.point_header_footer(
                    seg.last['tp'].as_coordinate_tag(), icon_url)
                k += kml.placemark_footer()
            elif seg.break_duration_hm() != "0:00":
                text = seg.break_label()
                k += kml.placemark_header(text)
                icon_url = _placetypes['pause'].url
                k += kml.point_header_footer(
                    seg.last['tp'].as_coordinate_tag(), icon_url)
                k += kml.placemark_footer()
        k += kml.end_section('Start, stop, breaks')

        k += kml.begin_section('Milestones')
        for milestone in self.milestones:
            k += milestone.as_kml()
        k += kml.end_section('Milestones')

        if not doing_single_file:
            k += kml.end_section("final " + last_date_name)
        k += kml.end_section("final " + last_activity_id)

        k += kml.doc_footer()
        return k

    def as_kml_tour(self):
        header = self.kwargs['header']
        k = kml.doc_header(header, version="2.2")
        #self.tour[0].duration = 5
        #self.tour[0].tilt = 0.1
        pt = self.tour[0]
        k += kml.tour_header(header, pt)
        for i, pt in enumerate(self.tour):
            #wait = "6" if i == 1 else ""
            wait = ""
            k += geo.KML.fly_to(pt.duration, pt, wait)
        k += kml.tour_footer()
        k += kml.overlay()
        k += kml.doc_footer()
        return k

    def as_svg(self, map_area=None, fixed=None, title=None, desc=None,
               append=False, final=True):

        def segments():
            sg = "\n<!-- Segments -->\n"
            colour = "red"
            if False:
                for seg in self.compressed.segments:
                    sg += seg.as_svg(colour, dashes="2 1")
                    colour = "yellow" if colour == "red" else "red"
            if True:
                for seg in self.compressed.segments:
                    #s += seg.as_speed_svg()
                    sg += seg.as_slope_svg()
            return sg

        def breaks():
            br = "\n<!-- Breaks -->\n"
            for seg in self.compressed.segments:
                is_first_segment = seg.previous_segment is None
                is_last_segment = seg.next_segment is None
                if is_first_segment:
                    text = seg.first['tp'].time_hm()
                    lat = seg.first['tp'].lat
                    lon = seg.first['tp'].lon
                    br += svg_map.plot_marker_latlon(lat, lon, text,
                            {'fill': 'black', 'font-size': 2.5},
                            radius=2, icon='start')
                if is_last_segment:
                    text = seg.last['tp'].time_hm() + " " + fmt.km(self.net_dist)
                    br += svg_map.plot_marker_latlon(seg.last['tp'].lat,
                            seg.last['tp'].lon, text,
                            {'fill': 'black', 'font-size': 2.5},
                            radius=2, icon='stop', force_write=True)
                elif seg.break_duration_hm() != "0:00":
                    text = seg.break_label()
                    br += svg_map.plot_marker_latlon(seg.last['tp'].lat,
                            seg.last['tp'].lon, text,
                            {'fill': 'black', 'font-size': 2},
                            radius=2, icon='pause', force_write=True)
            return br

        def milestones():
            s = ""
            style_dict = {'font-size': 2, 'fill': 'Red'}
            for milestone in self.milestones:
                text = milestone.descr + " " + milestone.text
                s += svg_map.plot_marker_latlon(milestone.lat, milestone.lon,
                                                text, style_dict=style_dict,
                                                radius=1)
            return s

        if os.path.exists(_svg_icon_file):
            with codecs.open(_svg_icon_file) as f:
                svg_icons = f.read()
        else:
            print("Track as_svg missing icons file %s" % _svg_icon_file)
            # todo Userbug
            svg_icons = ""

        title = self.name if title is None else title
        desc = self.duration() if desc is None else desc
        map_area = self.map_area if map_area is None else map_area
        map_area = None if fixed is not None else map_area
        # If fixed coordinates given, they should overrule

        svg_map = SVGMap(svg, map_area=map_area, fixed=fixed,
                         icon=self.main_activity_id)
        if not append:
            svg.empty_canvas()
        svg.set_title(title, desc)
        s = ""
        if not append:
            s += svg.doc_header(more_defs=svg_icons)
            s += svg_map.svg_comment
            s += svg_map.draw_map_frame()
            s += svg_map.plot_map_grid(svg_map.spread_km)
            s += svg_map.draw_header(title, desc)
            s += svg_map.plot_scale()
        s += segments()
        s += breaks()
        s += milestones()
        #s += svg_map.svg.draw_pixels()  # For verifying non-printing
        if final:
            s += svg_map.draw_placemarks(_places)
            s += svg.doc_footer()
        return s


class SVGMap(object):
    """Map plotting lats and lons on SVG"""

    def __init__(self, svg_, fixed=None, map_area=None, icon=None):
        """
        Set up a map in an existing SVG object, either
         - based on fixed coordinates given (lat lon of map middle + width km),
         - or on map area (max and min lat and lon, margins, alignment),
           from which the program deduces the fixed coordinates
        """

        self.svg = svg_
        self.fixed = fixed
        self.map_area = map_area
        self.svg_comment = ""
        self.icon = icon
        svg_.set_canvas("A4")
        svg_.reset_margins()
        svg_.def_margins('outer', 'mm', 15, 13, 15, 8)
        svg_.def_margins('inner', 'mm', 21, 19, 21, 14)

        use_map_area = map_area is not None and fixed is None
        if use_map_area:
            self.svg.canvas['user'] = self._lat_lon_of_contents(map_area)
            self.mid_lat = svg.canvas['user']['lat']['mid']
            self.mid_lon = svg.canvas['user']['lon']['mid']
            self.spread_km = svg.canvas['user']['total_spread']
            self.orientation = svg.canvas['user']['orientation']
        elif fixed is not None:
            self.mid_lat = fixed.get('mid_lat', 60)
            self.mid_lon = fixed.get('mid_lon', 21)
            self.spread_km = fixed.get('width_km', 100)
            self.orientation = fixed.get('orientation', 'landscape')
        else:
            raise Exception("Map needs either 'fixed' or 'map_area'")

        self._create_canvas(use_map_area)

    def _create_canvas(self, use_map_area):
        def align_user_area_within_map():
            v_align = self.map_area.get('v_align', 'top')
            h_align = self.map_area.get('h_align', 'middle')

            # Align non-used area of map using v_align h_align parameters
            if user_aspect_ratio < map_aspect_ratio:
                # Wide track, like Crete -> extra space above and below
                extra_vertical_mm = (canvas_mm['height'] *
                                (1 - user_aspect_ratio / map_aspect_ratio))
                extra_lat = extra_vertical_mm / lat_to_mm
                if v_align == 'top':
                    self.mid_lat -= extra_lat / 2
                elif v_align == 'bottom':
                    self.mid_lat += extra_lat / 2
            elif user_aspect_ratio > map_aspect_ratio:
                # Narrow track, like Chile -> extra space left and right
                extra_horizontal_mm = (canvas_mm['width'] -
                            1 / user_aspect_ratio * canvas_mm['height'])
                extra_lon = extra_horizontal_mm / lon_to_mm / 2
                if h_align == 'left':
                    self.mid_lon += extra_lon
                elif h_align == 'right':
                    self.mid_lon -= extra_lon

            svg.canvas['user']['lat'] = {'y_mid': self.mid_lat}
            svg.canvas['user']['lon'] = {'x_mid': self.mid_lon}

        def lat_lon_of_canvas():
            lat_height = canvas_mm['height'] / lat_to_mm
            lon_width = canvas_mm['width'] / lon_to_mm
            lat_d = {'height': lat_height, 'y_mid': self.mid_lat,
                     'bottom': self.mid_lat - lat_height / 2,
                     'top': self.mid_lat + lat_height / 2}
            lon_d = {'width': lon_width, 'x_mid': self.mid_lon,
                     'left': self.mid_lon - lon_width / 2,
                     'right': self.mid_lon + lon_width / 2}
            svg.canvas['inner']['lat'] = lat_d
            svg.canvas['inner']['lon'] = lon_d
            lat_str = "lat bottom {bottom:.5f} y_mid {y_mid:.5f} top {top:.5f}"
            lon_str = "lon left {left:.5f} x_mid {x_mid:.5f} right {right:.5f}"
            self.svg_comment += svg.comment(lat_str.format(
                **svg.canvas['inner']['lat']) + " - " + lon_str.format(
                **svg.canvas['inner']['lon']))

        svg.set_orientation(self.orientation)
        svg.set_margins()

        canvas_mm = svg.canvas['inner']['mm']
        spread_mm = max(canvas_mm['width'], canvas_mm['height'])
        map_aspect_ratio = canvas_mm['aspect_ratio']
        if use_map_area:
            user_aspect_ratio = (svg.canvas['user']['lat']['km'] /
                                 svg.canvas['user']['lon']['km'])

            self.spread_km = self._zoom_out_if_necessary(self.spread_km,
                                    user_aspect_ratio, map_aspect_ratio)
        self.svg_comment += svg.comment(
            "%s km (= spread_km) = %s mm (= max width/height of map frame)"
            % (self.spread_km, spread_mm))

        lat_to_mm = spread_mm / geo.km2lat_diff(self.spread_km)
        lon_to_mm = spread_mm / geo.km2lon_diff(self.spread_km, self.mid_lat)

        self.svg.canvas['inner']['km'] = {'width': canvas_mm['width'] *
                                              self.spread_km / spread_mm,
                                          'height': canvas_mm['height'] *
                                              self.spread_km / spread_mm}
        if use_map_area:
            align_user_area_within_map()
        lat_lon_of_canvas()

        self.lat_to_mm = lat_to_mm
        self.lon_to_mm = lon_to_mm
        self.xmid_mm = canvas_mm['x_mid']
        self.ymid_mm = canvas_mm['y_mid']
        svg.map = self

        if svg.canvas.get('user') is None:
            svg.canvas['user'] = {'lat': {'y_mid': self.mid_lat},
                                  'lon': {'x_mid': self.mid_lon}}

    @staticmethod
    def _lat_lon_of_contents(map_area):
        margin_factor = map_area.get('margin_factor', 1.25)
        mid_lat = map_area['mid']['lat']
        mid_lon = map_area['mid']['lon']
        west = Point(mid_lat, map_area['min']['lon'])
        east = Point(mid_lat, map_area['max']['lon'])
        south = Point(map_area['min']['lat'], mid_lon)
        north = Point(map_area['max']['lat'], mid_lon)
        lat_spread = south.distance(north)
        lon_spread = west.distance(east)

        orientation = "landscape" if lon_spread > lat_spread else "portrait"
        total_spread = margin_factor * max(lat_spread, lon_spread)

        margin_min_lat = mid_lat - geo.km2lat_diff(lat_spread) / 2
        margin_max_lat = mid_lat + geo.km2lat_diff(lat_spread) / 2
        margin_min_lon = mid_lon - geo.km2lon_diff(lon_spread, mid_lat) / 2
        margin_max_lon = mid_lon + geo.km2lon_diff(lon_spread, mid_lat) / 2

        return {'lat': {'top': margin_max_lat, 'bottom': margin_min_lat,
                        'mid': mid_lat, 'km': lat_spread},
                'lon': {'left': margin_min_lon, 'right': margin_max_lon,
                        'mid': mid_lon, 'km': lon_spread},
                'orientation': orientation, 'total_spread': total_spread}

    @staticmethod
    def _zoom_out_if_necessary(spread_km,
                              user_aspect_ratio, map_aspect_ratio):
        # The user area within the map may be "too square"
        # for the "spread" distance to be used unadjusted.
        # This happens if the user area has a smaller aspect ratio
        # (lat-to-lon ratio) than the map area, in which case
        # we need to "zoom out", enlarging the spread distance.

        if svg.canvas['orientation'] == 'landscape':
            if user_aspect_ratio > map_aspect_ratio:
                spread_km *= user_aspect_ratio / map_aspect_ratio
        elif svg.canvas['orientation'] == 'portrait':
            if user_aspect_ratio < map_aspect_ratio:
                spread_km *= map_aspect_ratio / user_aspect_ratio
        return spread_km

    @staticmethod
    def draw_map_frame():
        s = svg.plot_frame('outer', {'stroke': 'Green'})
        s += svg.plot_frame('inner', {'stroke': 'Green'})
        return s

    def draw_header(self, title, desc):
        use_template = '<use xlink:href="#%s" style="fill:%s;" '
        use_template += 'transform="translate(%s %s) scale(%s)" />\n'
        x = svg.canvas['inner']['mm']['left']
        y = svg.canvas['outer']['mm']['top'] - 1
        s = "\n<!-- Page header above outer frame, time stamp below -->\n"
        s += svg.plot_header(title, 'outer', 'left', 'top',
                             class_="header")

        s += svg.plot_header(desc, 'outer', 'right', 'top',
                             style_dict={'font-size': 4})
        if self.icon is not None:
            cx = x + 17
            cy = y + 24
            r = 15
            s += svg.plot_blue_sign(cx, cy, r)
            s += use_template % (self.icon , "white", cx - 14, cy - 13, 5.0)
        dimensions = "%s km x %s km" % (
            fmt.onedecimal(svg.canvas['inner']['km']['width']),
            fmt.onedecimal(svg.canvas['inner']['km']['height']))
        s += svg.plot_header(dimensions, 'outer', 'right', 'top',
                             dy = -5, style_dict={'font-size': 4})
        y = svg.canvas['outer']['mm']['bottom'] + 6
        s += use_template % ("elk-inv", lib.app_color(_colors, 'Green'),
                             x - 4, y - 5, 1.7)

        s += svg.plot_header("Green Elk %s " % fmt.current_timestamp(),
                             'outer', 'left', 'bottom',
                             +12, style_dict={'font-size': 2.5})
        return s

    def draw_placemarks(self, places):
        s = "\n<!-- Placemarks -->\n"
        has_map_area = self.map_area is not None
        if has_map_area:
            min_lat = self.map_area['min']['lat']
            max_lat = self.map_area['max']['lat']
            min_lon = self.map_area['min']['lon']
            max_lon = self.map_area['max']['lon']
            margin_lat = -0.03 * (max_lat - min_lat)
            margin_lon = -0.03 * (max_lon - min_lon)
        else:
            inner_canvas = svg.canvas['inner']
            min_lat = inner_canvas['lat']['bottom']
            max_lat = inner_canvas['lat']['top']
            min_lon = inner_canvas['lon']['left']
            max_lon = inner_canvas['lon']['right']
            margin_lat = 0.05 * (max_lat - min_lat)
            margin_lon = 0.05 * (max_lon - min_lon)

        sw = Point(min_lat + margin_lat, min_lon + margin_lon)
        ne = Point(max_lat - margin_lat, max_lon - margin_lon)
        for pm in places:
            if pm.inside(sw, ne):
                text = pm.text
                if pm.prominence > 19:  # todo - make it into parameter
                    # Skip lifts and other not-so-important placemarks
                    continue
                color = pm.placetype['color']
                size = (3 if pm.tot_prominence <= 10 else 2
                        if pm.tot_prominence <= 17 else 1)
                r = 6 if pm.placetype['category'] == 'logo' else 2.5
                text = "" if pm.placetype['category'] == 'logo' else text
                icon = pm.placetype['svg']
                icon = icon.replace('.svg', '')
                use_frame = pm.placetype_id in ["village", "island"]
                s += self.plot_marker_latlon(pm.lat, pm.lon, text,
                    {'fill': color, 'font-size': size}, radius=r, icon=icon,
                    use_frame=use_frame)
        return s

    def _plot_text_latlon(self, lat, lon, rotation, size_mm, anchor="left"):
        pass

    def _plot_icon_latlon(self, lat, lon, r_mm=5, style_dict=None):
        pass

    def plot_marker_latlon(self, lat, lon, txt, style_dict=None,
                           angle=0, radius=2.5, icon="circle",
                           use_frame=False, force_write=False):
        max_y = svg.canvas['inner']['mm']['bottom']
        if style_dict is None:
            style_dict = {}
        x, y = self.latlon2xy(lat, lon)
        if use_frame:
            return svg.plot_framed_sign_mm(x, y, txt)
        font_size = style_dict.get('font-size', 3)
        color = style_dict.get('fill', 'Red')
        x_text = x + radius * 1.2
        y_text = y + font_size * 0.4
        color = lib.app_color(_colors, color)
        s1 = s2 = ""
        done = False
        while not done:
            s1 = svg.plot_icon_mm(x, y, r=radius, icon=icon, color=color)
            done = s1 != "" or not force_write
            if not done:
                y += 1  # Try 1 mm lower
                y_text += 1  # Keep text aligned
            done = done or y > max_y
        done = False
        while not done:
            s2 = svg.plot_text_mm(x_text, y_text, txt, style_dict, angle=angle)
            done = s2 != "" or not force_write
            if not done:
                y_text += 1  # Try 1 mm lower
            done = done or y_text > max_y
        return s1+s2

    def plot_line_latlon(self, p1, p2, style_dict=None):
        x1, y1 = self.latlon2xy(p1.lat, p1.lon)
        x2, y2 = self.latlon2xy(p2.lat, p2.lon)
        return svg.plot_line_mm(x1, y1, x2, y2, style_dict)

    def plot_map_grid(self, spread_km):
        corners = svg.canvas['inner']['mm']
        min_lat, min_lon = self.xy2latlon(corners['left'], corners['bottom'])
        max_lat, max_lon = self.xy2latlon(corners['right'], corners['top'])

        s = "\n<!-- Horizontal grid - latitudes -->\n"
        left_mm = (svg.canvas['outer']['mm']['left'] +
                   svg.canvas['inner']['mm']['left']) / 2
        right_mm = (svg.canvas['outer']['mm']['right'] +
                    svg.canvas['inner']['mm']['right']) / 2
        d, m, sec = geo.decdeg2dms(min_lat)
        text_style = {'font-size': 2.5, 'text-anchor': 'middle'}

        while geo.dms2decdeg(d, m + 1, 0) < max_lat:
            m += 1
            if m >= 60:
                d += 1
                m = 0
            grid_lat = geo.dms2decdeg(d, m, 0)
            w = Point(grid_lat, min_lon)
            e = Point(grid_lat, max_lon)
            opacity = 0.8 if m % 30 == 0 else 0.5 if m % 15 == 0 else 0.3
            line_style = {'stroke': 'grey', 'opacity': opacity,
                          'stroke-width': 0.2}
            if spread_km > 40 and opacity < 0.5:
                continue
            x, y = self.latlon2xy(grid_lat, min_lon)
            fmt_d = "%s°" % d
            fmt_m = "%s′" % m
            s += svg.plot_text_mm(left_mm, y - 1, fmt_d, text_style)
            s += svg.plot_text_mm(left_mm, y + 2, fmt_m, text_style)
            s += svg.plot_text_mm(right_mm, y - 1, fmt_d, text_style)
            s += svg.plot_text_mm(right_mm, y + 2, fmt_m, text_style)
            s += self.plot_line_latlon(w, e, line_style)

        s += "\n<!-- Vertical grid - longitudes -->\n"
        top_mm = (svg.canvas['outer']['mm']['top'] +
                  svg.canvas['inner']['mm']['top']) / 2 + 2
        bottom_mm = (svg.canvas['outer']['mm']['bottom'] +
                     svg.canvas['inner']['mm']['bottom']) / 2
        d, m, sec = geo.decdeg2dms(min_lon)
        while geo.dms2decdeg(d, m + 1, 0) < max_lon:
            m += 1
            if m >= 60:
                d += 1
                m = 0
            grid_lon = geo.dms2decdeg(d, m, 0)
            south = Point(min_lat, grid_lon)
            n = Point(max_lat, grid_lon)
            opacity = 0.8 if m % 30 == 0 else 0.5 if m % 15 == 0 else 0.3
            line_style = {'stroke': 'grey', 'opacity': opacity,
                          'stroke-width': 0.2}
            if spread_km > 40 and opacity < 0.5:
                continue
            x, y = self.latlon2xy(min_lat, grid_lon)
            fmt_d_m = "%s°%s′" % (d, m)
            s += svg.plot_text_mm(x, top_mm, fmt_d_m, text_style)
            s += svg.plot_text_mm(x, bottom_mm, fmt_d_m, text_style)
            s += self.plot_line_latlon(south, n, line_style)
        return s

    @staticmethod
    def _printed_scale_km(max_distance):
        # 500 200 100 km - 50 20 10 km - 5 2 1 km ...
        max_lat_distance = max_distance / 3  # svg.canvas['aspect_ratio']
        dist_metres = 1000 * max_lat_distance
        dist_1st_number = int(str(dist_metres)[0])
        if dist_1st_number >= 5:
            dist_1st_number = 5
        elif dist_1st_number > 2:
            dist_1st_number = 2
        scale_metres = dist_1st_number * 10 ** int(log10(dist_metres))
        return float(scale_metres) / 1000

    def plot_scale(self, valign="bottom", halign="right"):
        s = "\n<!-- Scale (%s %s) -->\n" % (valign, halign)
        max_spread_km = max(svg.canvas['inner']['km'].values())
        printed_scale_km = self._printed_scale_km(max_spread_km)
        lon_width = geo.km2lon_diff(printed_scale_km, self.mid_lat)
        width_mm = lon_width * self.lon_to_mm
        y = svg.canvas['outer']['mm'][valign] + 6
        x_right_mm = svg.canvas['inner']['mm'][halign]
        x_left_mm = x_right_mm - width_mm
        s += svg.plot_line_mm(x_left_mm, y, x_right_mm, y,
                              {'stroke-width': 0.4})

        first_digit = str(printed_scale_km).strip("0.")[0]
        ticks = {'1': 10, '5': 5, '2': 2}[first_digit]
        interval = {'1': 5, '5': 5, '2': 1}[first_digit]

        scale_height = 1

        for i in range(0, ticks + 1):
            x = x_left_mm + i * width_mm / ticks
            s += svg.plot_line_mm(x, y, x, y - scale_height,
                                  {'stroke-width': 0.4})
            if i % interval == 0:
                tick_km = i * printed_scale_km / ticks
                unit = "m" if tick_km < 1 else "km"
                tick_km = (int(1000*tick_km) if 0 < tick_km < 1 else
                           int(tick_km))
                tick_km = "%s %s" % (tick_km, unit) if i == ticks else tick_km
                s += svg.plot_text_mm(x, y - 2, str(tick_km),
                                      {'font-size': 2.5,
                                       'text-anchor': 'middle'})
        return s

    def latlon2xy(self, lat, lon):
        x = (lon - self.mid_lon) * self.lon_to_mm + self.xmid_mm
        y = (self.mid_lat - lat) * self.lat_to_mm + self.ymid_mm
        return x, y

    def xy2latlon(self, x, y):
        lat = self.mid_lat - (y - self.ymid_mm) / self.lat_to_mm
        lon = self.mid_lon + (x - self.xmid_mm) / self.lon_to_mm
        return lat, lon

    @staticmethod
    def speed2colour(speed_kmh):
        colour_speed = [[2, "#af8000"], [5, "#ff8000"], [10, "#ff4000"],
                        [15, "#ff0000"], [20, "#af2000"], [25, "#802000"],
                        [30, "#602000"], [40, "#402000"]]
        for speed, colour in colour_speed:
            if speed_kmh < speed:
                return colour
        return "#ffffff"


class Timetable(object):
    """SVG matrix with days as columns, hours as rows"""
    def __init__(self, infile, outfile, mode="", header="",
                 activity="downhill", param="portrait"):
        self.infile = infile
        self.outfile = outfile
        self.mode = mode
        self.hdr = header
        self.activity = activity
        svg.set_canvas("A4")
        svg.set_orientation(param)
        svg.reset_margins()
        svg.def_margins('outer', 'mm', 15, 13, 15, 8)
        svg.def_margins('inner', 'mm', 30, 19, 21, 14)
        svg.set_margins()

    def __str__(self):
        s = "infile %s outfile %s mode %s header %s activity %s"
        return s % (self.infile, self.outfile, self.mode, self.hdr,
                    self.activity)

    def as_svg(self):
        svg.set_title(self.hdr, "Timetable")
        s = svg.doc_header()
        s += self._header()
        s += self._frame_page()
        s += self._day_grid()
        field = self.activity
        tracklist = Tracklist(self.infile, mode="segments")
        date_from = fmt.datetime_from_ymd(self.date_from)
        date_to = fmt.datetime_from_ymd(self.date_to)
        examined_date = date_from
        hours_origo = datetime.time(0)  # self.hour_from)
        last_minute_delta = datetime.timedelta(hours=self.hour_to)
        s += svg.comment('Mode %s activity %s' % (self.mode, self.activity))
        if self.mode == "hours":
            while examined_date <= date_to:
                for track in tracklist.tracks:
                    track_date = track['date']
                    if track_date != examined_date.date():
                        continue
                    minute_examined = (examined_date +
                                       datetime.timedelta(
                                           hours=self.hour_from))
                    last_minute = examined_date + last_minute_delta
                    while minute_examined < last_minute:
                        minute_hm = fmt.hm(minute_examined)
                        timepoint = track['track'].timepoints.get(minute_hm)
                        if timepoint is not None:
                            minute_dict = timepoint.as_dict()
                            distance = timepoint.distance
                            hm_up = timepoint.hm_up
                            hm_down = abs(timepoint.hm_down)
                            max_speed = timepoint.max_speed
                            max_slope_up = timepoint.max_slope_up
                            max_slope_down = abs(timepoint.max_slope_down)
                            max_slope = (max_slope_down if hm_down > hm_up else
                                         max_slope_up)
                            speed = distance * 60
                            alt = timepoint.alt
                            day = (examined_date - date_from).days
                            hour = int(minute_hm[0:2])
                            minute = int(minute_hm[3:5])
                            color = 'Green' if hm_up > hm_down else 'Red'
                            # opacity = min(speed / 30, 1)
                            opacity = max(0, max_slope / 30)

                            s += self._plot_minute(day, hour, minute,
                                                  opacity, color)
                        minute_examined += datetime.timedelta(minutes=1)
                examined_date += datetime.timedelta(days=1)
        if self.mode == "profile":
            while examined_date <= date_to:
                for track in tracklist.tracks:
                    track_date = track['date']
                    if track_date != examined_date.date():
                        continue
                    minute_examined = (examined_date +
                                       datetime.timedelta(
                                           hours=self.hour_from))
                    last_minute = examined_date + last_minute_delta
                    last_color = ""
                    while minute_examined < last_minute:
                        minute_hm = fmt.hm(minute_examined)
                        timepoint = track['track'].timepoints.get(minute_hm)
                        if timepoint is not None:
                            minute_dict = timepoint.as_dict()
                            distance = timepoint.distance
                            hm_up = timepoint.hm_up
                            hm_down = abs(timepoint.hm_down)
                            max_speed = timepoint.max_speed
                            max_slope_up = timepoint.max_slope_up
                            max_slope_down = abs(timepoint.max_slope_down)
                            max_slope = (max_slope_down if hm_down > hm_up else
                                         max_slope_up)
                            speed = distance * 60
                            alt = timepoint.alt
                            day = (examined_date - date_from).days
                            hour = int(minute_hm[0:2])
                            minute = int(minute_hm[3:5])
                            color = ("black" if max_slope_down > 24 else
                                     "Red" if max_slope_down > 16 else
                                     "Blue" if max_slope_down > 8 else
                                     "Green" if max_slope_down > 1 else "Grey")
                            # color = 'Green' if hm_up > hm_down else 'Red'
                            #opacity = min(speed / 30, 1)
                            #opacity = max(0, max_slope/30)
                            opacity = 1

                            s += self._plot_minute(day, hour, minute,
                                                  opacity, color)
                        minute_examined += datetime.timedelta(minutes=1)
                examined_date += datetime.timedelta(days=1)
        else:
            for seg_dict in tracklist.segments:
                start_date = seg_dict['start_datetime'].date()
                time_origo = datetime.datetime.combine(start_date, hours_origo)
                start_time = seg_dict['start_datetime']
                end_time = seg_dict['end_datetime']
                days = (start_date - date_from).days
                start_hour = (start_time - time_origo).total_seconds() / 3600.0
                end_hour = (end_time - time_origo).total_seconds() / 3600.0
                name = seg_dict['short_name']
                dist = seg_dict['distance']
                activity_id = seg_dict['activity_id']
                s += self._plot(days, start_hour, end_hour, activity_id, name)
        s += svg.doc_footer()
        return s

    def save_as(self, filename):
        s = self.as_svg()
        lib.save_as(filename, s, verbose=True)

    def _header(self):
        use_template = '<use xlink:href="#%s" style="fill:%s;" '
        use_template += 'transform="translate(%s %s) scale(%s)" />\n'
        x = svg.canvas['inner']['mm']['left']
        y = svg.canvas['outer']['mm']['top'] - 1
        s = "\n<!-- Page header above outer frame, time stamp below -->\n"
        s += svg.plot_header("%s" % self.hdr, 'outer', 'left', 'top',
                             class_="header")

        s += svg.plot_header("ngt", 'outer', 'right', 'top',
                             style_dict={'font-size': 4})
        y = svg.canvas['outer']['mm']['bottom'] + 6
        s += use_template % ("elk-inv", lib.app_color(_colors, 'Green'),
                             x - 4, y - 5, 1.7)
        s += svg.plot_header("Green Elk %s " % fmt.current_timestamp(),
                             'outer', 'left', 'bottom',
                             +9, style_dict={'font-size': 3})
        return s

    @staticmethod
    def _frame_page():
        s = svg.plot_frame('outer', {'stroke': 'Green'})
        s += svg.plot_frame('inner', {'stroke': 'Green'})
        return s

    def _day_grid(self):
        s = svg.comment("Frame for timetable")

        canvas_mm = svg.canvas['inner']['mm']
        width = canvas_mm['width']
        height = canvas_mm['height']

        date_from = "2015-03-22"
        self.date_from = date_from
        date_to = "2015-03-28"
        self.date_to = date_to
        date_from = datetime.datetime.strptime(date_from, "%Y-%m-%d")
        date_to = datetime.datetime.strptime(date_to, "%Y-%m-%d")
        days = (date_to - date_from).days
        columns = days + 2

        hour_from = 9
        self.hour_from = hour_from
        hour_to = 17
        self.hour_to = hour_to
        rows = hour_to - hour_from + 1

        column_width = float(width) / columns
        row_height = float(height) / rows
        self.column_width = column_width
        self.row_height = row_height

        s += svg.comment("Matrix %s rows x %s columns, width %s height %s" %
                         (rows, columns, column_width, row_height))

        weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

        for column in range(0, columns):
            date = (date_from + datetime.timedelta(days=column - 1)).date()
            weekday = date.isoweekday()
            date_fmt = date.strftime("%d.%m.%Y")
            weekday_name = weekdays[weekday - 1]
            s += svg.comment("%s - %s" % (date_fmt, weekday_name))
            for row in range(0, rows):
                x = canvas_mm['left'] + column * column_width
                y = canvas_mm['top'] + row * row_height
                style = {'stroke-width': 0.1}
                s += svg.plot_rect_mm(x, y, column_width, row_height, style)
                if column == 0 and row > 0:
                    x = canvas_mm['left'] + 0.5 * column_width
                    y = (canvas_mm['top'] - 0.45 * row_height +
                         (row + 1) * row_height)
                    h = hour_from + row - 1
                    h_label = "%s-%s" % (h, h + 1)
                    s += svg.plot_text_mm(x, y, h_label,
                                          {'font-size': 6,
                                           'text-anchor': 'middle'})
            if column > 0:
                x = canvas_mm[
                        'left'] + column * column_width + 0.5 * column_width
                y = canvas_mm['top'] + 0.5 * row_height
                s += svg.plot_text_mm(x, y, weekday_name,
                                      {'font-size': 6,
                                       'text-anchor': 'middle'})
                y += 5
                s += svg.plot_text_mm(x, y, date_fmt,
                                      {'font-size': 3,
                                       'text-anchor': 'middle'})
        return s

    def _plot(self, day, time_from, time_to, activity_id, text=""):
        global _last_text
        canvas_mm = svg.canvas['inner']['mm']
        column = day + 1
        if day < 0:
            return ""
        clrs = {'downhill': 'red', 'snowboard': 'red', 'lift': 'yellow',
                'road': 'blue', 'walk': 'green'}
        clr = clrs[activity_id]
        x = canvas_mm['left'] + column * self.column_width
        y1 = (canvas_mm['top'] +
              (time_from - self.hour_from + 1) * self.row_height)
        y2 = (canvas_mm['top'] +
              (time_to - self.hour_from + 1) * self.row_height)
        s = svg.plot_rect_mm(x, y1, self.column_width, abs(y2 - y1),
                             {'fill': clr, 'fill-opacity': 0.2})
        print_text = "" if text == _last_text else text
        s += svg.plot_text_mm(x + self.column_width / 2, (y1 + y2) / 2 + 1,
                              print_text,
                              {'font-size': 2, 'text-anchor': 'middle'})
        _last_text = text if text != "" else _last_text
        return s

    def _plot_minute(self, day, hour, minute, opacity, color):
        canvas_mm = svg.canvas['inner']['mm']
        minute_column = float(minute % 10) / 10
        minute_row = float(int(minute / 10)) / 6
        column = day + 1 + minute_column
        row = hour - self.hour_from + 1 + minute_row
        width = self.column_width / 10
        height = self.row_height / 6
        x = canvas_mm['left'] + column * self.column_width
        y = canvas_mm['top'] + row * self.row_height
        style = {'fill': color, 'opacity': opacity}
        return svg.plot_rect_mm(x, y, width, height, style)


class Command(object):
    """User command"""

    def __init__(self, user_input, invoked_from_outside=False):
        self.user_input = user_input
        self.params = {'i': None, 'o': None, 'log': None, 'f': None,
                      'iactivity': 'run', 'ifmt': 'gpx', 'ofmt': 'json'}
        if invoked_from_outside:
            self._server_level_code(argv=user_input)
        elif user_input == "check":
            self.check_status(verbose=True)
        else:
            self._execute_commands(user_input)

    @staticmethod
    def str_(row):
        s = "{command}: mode {mode} parameters {parameters} header {header}\n"
        s += "  {activity_id} lat {lat} lon {lon} km {km}\n"
        s += "  in {infile} out {outfile}"
        return s.format(row)

    @staticmethod
    def as_dict(row):
        return {'command': row.command, 'mode': row.mode,
                'parameters': row.parameters, 'header': row.header,
                'activity_id': row.activity,
                'lat': row.lat, 'lon': row.lon, 'km': row.km,
                'infile': os.path.expanduser(row.infile),
                'outfile': os.path.expanduser(row.outfile)}

    def _execute_commands(self, user_input):
        global _debug_object, _day_metadata, _time_metadata, _svg_icon_file
        global _places
        lib.start_log("_execute_commands")
        for row in user_input:
            command = row.command
            infile = os.path.expanduser(row.infile)
            outfile = os.path.expanduser(row.outfile)
            _debug_object = row.command
            params = self.as_dict(row)
            lib.log_event(command + " " + infile)

            dir_ = infile
            if not os.path.isdir(dir_):
                dir_ = os.path.dirname(dir_)

            if command == 'Places':
                place = Places(**params)
                change_global_places_file = outfile == ""
                if change_global_places_file:
                    _places = place
                else:
                    place.save_as(outfile)
            elif command == 'Tracklist':
                tracklist = Tracklist(**params)
                tracklist.save_as(outfile)
                if row.parameters == "missing":
                    outfile_2 = outfile.replace(".html", "_missing.csv")
                    tracklist.mode = "missing"
                    tracklist.save_as(outfile_2)
            elif command == 'Timetable':
                timetable = Timetable(**params)
                timetable.save_as(outfile)
            elif command == 'Cache':
                cache = TrackCache(**params)
                if cache.count == 0:
                    print("No rows matching criteria %s" % self.str_(row))
                elif params['mode'] != "edit":
                    cache.save_as(outfile)
            elif command == 'SVG':
                svg_map = self._svg_test_output()
                lib.save_as(outfile, svg_map, verbose=True)
            elif command == 'Track':
                params['main_activity_id'] = params['activity_id']
                track = Track(**params)
                if params['mode'] != "tour":
                    track.calc_milestones()
                track.save_as(outfile)
            elif command == 'Config':
                config_entity = row.mode
                infile = config_files[config_entity]['filename']
                fields = config_files[config_entity]['fields']
                dir_ = config_files[config_entity]['dir_']
                enumerate_rows = config_entity in "Commands Time_metadata"
                print("Config %s %s" % (infile, fields))
                config = lib.Config(config_entity, fields, infile,
                                    enumerate_rows, dir_)
                field_transformations = None
                if config_entity == "Placetype":
                    field_transformations = [
                        ['url', Placetypes.img_url],
                        ['svg', Placetypes.svg_img_with_text]]
                config.save_as(outfile, subhead_field=row.parameters,
                               field_transformations=field_transformations)
            elif command == 'SVGMerge':
                dir_ = infile
                svg_files = []
                for placetype in _placetypes:
                    icon_file = placetype.svg
                    if icon_file != "":
                        svg_files.append(icon_file)
                kajsvg.merge(dir_, svg_files, outfile)
            lib.log_event(" - Done: " + row.command + " " + outfile)

    def _server_level_code(self, argv):
        def translate_argv_find_config_py():
            # Parse parameter values into dict by name of params
            config_py = 'config'
            for arg in argv:
                if '=' in arg:
                    param, val = arg.split("=")
                    for par in self.params:
                        par_minus = "-" + par
                        if param == par_minus:
                            self.params[par] = val
                    if param == '-config':
                        config_py = val
            return config_py

        def import_right_config_py(config_py):
            sys.path.insert(1, '/greenelk/www/stage/kajgps')
            sys.path.insert(2, '/greenelk/www/live/kajgps')
            importlib.import_module(config_py)

        config_py = translate_argv_find_config_py()
        import_right_config_py(config_py)

        input_files = self.params['i'].split(",")
        tracklist = []
        for input_file in input_files:
            one_track = Track(input_file, server_level=True,
                              activity_id=self.params['iactivity'])
            first_tp = one_track.trackpoints[0]
            last_tp = one_track.trackpoints[len(one_track.trackpoints) - 1]
            a_track = {'track': one_track,
                       'first_time': first_tp.datetime,
                       'last_time': last_tp.datetime,
                       'filename': input_file}
            tracklist.append(a_track)
        # Sort the tracks in ascending order (user may have entered randomly)
        tracklist.sort(key=lambda x: x['first_time'])
        prev_last_time = tracklist[0]['first_time']
        prev_file = ""
        input_is_valid = False
        output = ""
        complete_track = Track(None)  # We append all tracks to this one
        for track_dict in tracklist:
            filename = track_dict['filename'].split("/")[-1]
            # Strip away the path
            first_time = track_dict['first_time']
            input_is_valid = (first_time >= prev_last_time)
            if not input_is_valid:
                errmsg = "Overlapping track times in files A %s and B %s. "
                errmsg += "A starts at %s which is before B ends at %s. "
                errmsg += "These two files cannot be merged."
                errmsg = errmsg % (filename, prev_file, first_time,
                                   prev_last_time)
                output = '{"success": false, "errcode": 7001, "error": "%s"}'
                output %= errmsg
                break
            first_file = (prev_file == "")
            if first_file:
                complete_track = track_dict['track']
            else:
                complete_track.append(track_dict['track'])
            prev_file = filename
            prev_last_time = track_dict['last_time']

        output_to_stdout = (self.params['o'] == 'stdout')
        if not output_to_stdout:  # Comments on screen are OK
            print(complete_track)
        output_format = self.params['ofmt']
        if input_is_valid:
            output = format(complete_track, output_format)
        if output_to_stdout:
            print(output)
        else:
            output_file = self.params['o']
            lib.save_as(output_file, output)
        # Append log to end of log file
        log_file = self.params['log']
        # log_content = str(complete_track.logger)
        #with open(log_file, "a") as f:
        #    f.write(log_content)

    def check_status(self, verbose=False):

        def check_missing_fields():
            count, text_rows = table.missing_fields()
            if count > 0:
                print("  - Error! %s entries with missing fields" % count)
                if count > 5:
                    print("    (only first 5 shown)")
                for i, row in enumerate(text_rows):
                    if i == 5:
                        break
                    print("    %s" % row)

        def check_duplicates():
            if table.enumerate_rows:
                return  # For such tables, duplicates are allowed
            count, text_rows = table.duplicates()
            if count > 0:
                print("  - Error! %s entries with duplicates" % count)
                if count > 500:
                    print("    (only first 5 shown)")
                for i, row in enumerate(text_rows):
                    if i == 500:
                        break
                    print("    %s" % row)

        def check_placetype_integrity():
            count, text_rows = table.integrity('placetype_id', placetypes)
            other_table_name = placetypes.filename

            if count > 0:
                e = "  - Error! %s entries referring to placetype_id"
                e += " not present in\n    file '%s'\n"
                e += "    => add missing entries there, or rename "
                e += "erroneous placetype_id values"
                print(e % (count, other_table_name))
                if count > 5:
                    print("    (only first 5 shown)")
                for i, row in enumerate(text_rows):
                    if i == 5:
                        break
                    print("    %s" % row)

        def check_placetype_svg_files():
                j = 0
                for i, pt in enumerate(placetypes):
                    filename = os.path.join(_icon_dir, pt.svg)
                    if pt.svg == "":
                        continue
                    exists = os.path.isfile(filename)
                    if not exists:
                        j += 1
                        if j > 5:
                            print("(only first five shown)")
                            break
                        e = "Placetype %s (%s)" % (i, pt.id)
                        e += " has missing svg file %s" % filename
                        print("    %s" % e)

        if verbose:
            print("kajgps.py: Check status %s\n" % fmt.current_timestamp())

            print("\nParsing config .csv files in %s" % _config_file_dir)
        files = [['1. Commands (change always)', ['Commands']],
                 ['2. User data (change sometimes)',
                      ['Places', 'Areaname', 'Day_metadata', 'Time_metadata']],
                 ['3. Base data (change seldom if ever)',
                      ['Activity', 'Colors', 'Placetype']]]
        placetypes = Placetypes(**config_files['Placetype'])
        for category in files:
            print("\n%s" % category[0])
            for table_name in category[1]:
                values = config_files[table_name]
                filename = values['filename']
                dir_ = str(values['dir_'])
                full_filename = os.path.join(dir_, filename)
                is_file = os.path.isfile(full_filename)
                if not is_file:
                    msg = "Error! %s does not exist" % full_filename
                    print("- %s (%s): %s" % (table_name, filename, msg))
                    continue
                enumerate_rows = table_name in ['Commands', 'Time_metadata']
                table = lib.Config(enumerate_rows=enumerate_rows,
                                   **config_files[table_name])
                msg = "%s rows" % len(table)
                print("- %s (%s): %s" % (table_name, filename, msg))
                check_missing_fields()
                check_duplicates()
                if table_name == 'Places':
                    check_placetype_integrity()
                if table_name == 'Placetype':
                    check_placetype_svg_files()

        print("")

    @staticmethod
    def list_configs():
        for table_name in ['Activity', 'Placetype', 'Forcedbreak',
                           'Banarea', 'Areaname']:
            table = lib.Config(**config_files[table_name])
            print(str(table))
            print(repr(table))

    @staticmethod
    def _svg_test_output():
        svg.set_canvas("A4")
        svg.set_orientation("portrait")
        print("canvas before, with portrait %s" % str(svg.canvas))
        svg.set_orientation("landscape")
        print("canvas after, with landscape %s" % str(svg.canvas))
        svg.reset_margins()
        svg.def_margins('outer', 'mm', 15, 13, 15, 8)
        svg.def_margins('inner', 'mm', 30, 19, 21, 14)
        print("margins before %s" % svg.margins)
        svg.set_margins()
        print("canvas after %s" % str(svg.canvas))
        svg.set_title("SVG test output", "Verifying functionality")

        fixed = {'mid_lat': 60.0, 'mid_lon': 21.0, 'km': 100,
                 'orientation': 'landscape'}
        svg_map = SVGMap(svg, fixed=fixed)

        s = svg.doc_header()

        s += svg.plot_frame('outer', {'stroke': 'Dark Blue',
                                      'stroke-width': 1})
        s += svg.plot_frame('inner', {'color': 'Green', 'stroke-width': 2})
        s += svg.comment('Headers')
        s += svg.plot_header(svg.title, 'inner', 'left', 'top',
                             class_="header")
        s += svg.plot_header(svg.desc, 'inner', 'right', 'top',
                             class_="small_header")
        s += svg.plot_header(fmt.current_timestamp(), 'outer', 'left',
                             'bottom', class_="small_header")
        for frame in ['outer', 'inner']:
            color = {'inner': 'Green', 'outer': 'Red'}[frame]
            style = {'font-size': 3, 'fill': color}
            for h in ['left', 'x_mid', 'right']:
                for v in ['top', 'y_mid', 'bottom']:
                    x = svg.canvas[frame]['mm'][h]
                    y = svg.canvas[frame]['mm'][v]
                    latlon = ""
                    if frame == "inner":
                        lat = "{:.5f}".format(svg.canvas[frame]['lat'][v])
                        lon = "{:.5f}".format(svg.canvas[frame]['lon'][h])
                        latlon = "= (%s, %s)" % (lat, lon)
                    text = "%s %s %s: (%smm, %smm) %s"
                    text = text % (frame, h, v, x, y, latlon)
                    s += svg.plot_header(text, frame, h, v, style_dict=style)

        s += svg.comment('Line 60.0, 20.9 to 60.2, 21.1')
        pt1 = Point(59.75, 20.5)
        pt2 = Point(60.25, 21.5)
        s += svg_map.plot_line_latlon(pt1, pt2)

        s += svg_map.plot_map_grid(100)
        s += svg.doc_footer()
        return s


html = kajhtml.HTML()
kml = geo.KML()

userbug = lib.Userbug('kajgps')

svg_filename = dict(
    svg_icons='ge_svg_icons.svg',)

config_files = {
    'Commands': {'filename': 'ge_commands.csv', 'item': 'Command',
                   'fields': 'command mode parameters header activity ' +
                             'lat lon km infile outfile'},
    'Places': {'filename': 'ge_places.csv', 'item': 'Places',
                 'fields': 'placemark descr placetype_id prominence ' +
                           'lat lon alt folder color'},
    'Area': {'filename': 'ge_areas.csv',
             'item': 'Area',
             'fields': 'area *subarea'},
    'Day_metadata': {'filename': 'ge_day_metadata.csv',
                     'item': 'Day_metadata',
                     'fields': 'date activity_id timezone name ' +
                               'distance comment'},
    'Time_metadata': {'filename': 'ge_time_metadata.csv',
                      'item': 'Time_metadata',
                      'fields': 'date time activity_id'},
    'Activity': {'filename': 'ge_activities.csv', 'item': 'Activity',
                 'fields': 'activity_id order name color1 color2 ' +
                           'min_speed alt_slow max_speed alt_fast ' +
                           'tick_long tick_short time_window_s ' +
                           'window_dist_m final_hop_m minimum_break_s'},
    'Colors': {'filename': 'ge_colors.csv', 'item': 'Color',
            'fields': 'color ge_color pass_1 hex pass_2 r g b pass_3 c m y k'},
    'Placetype': {'filename': 'ge_placetypes.csv', 'item': 'Placetype',
                  'fields': 'id category url svg color ' +
                            'prominence terra'},
    'Forced_break': {'filename': 'ge_forced_breaks.csv',
                     'item': 'Forced_break', 'fields':
                        'text lat lon from_activity to_activity direction'},
}

_py_dir = os.path.dirname(os.path.realpath(__file__))
_config_file_dir = os.path.join(_py_dir, "config")
_icon_dir = os.path.join(_py_dir, "svg")

for conf in config_files:
    config_files[conf]['dir_'] = _config_file_dir

_check = (sys.argv[-1] == "check" and len(sys.argv) > 1)
if _check:
    Command("check")
    print("Exiting (no commands will be executed after 'check')")
    exit()

filename = os.path.join(_config_file_dir,config_files['Area']['filename'])
_areas = {}
with open(filename) as csvfile:
    for i, row in enumerate(csvfile):
        row = row.strip()
        area = row.split(",")[0]
        comment_or_empty = (area + " ")[0] in ["#", " "]
        if not comment_or_empty:
            _areas[area] = {'order': i, 'sub_areas': []}
            for j, sub_area in enumerate(row.split(",")[1:]):
                order = i * 100 + j
                _areas[sub_area] = {'area': area, 'order_area': i,
                                    'order_sub_area': order}
_placetypes = Placetypes(**config_files['Placetype'])
_places = Places(os.path.join(_config_file_dir, 'ge_places.csv'))
_day_metadata = lib.Config(**config_files['Day_metadata'])
_time_metadata = lib.Config(enumerate_rows=True,
                            **config_files['Time_metadata'])
_activities = lib.Config(**config_files['Activity'])
_forced_breaks = lib.Config(**config_files['Forced_break'])
_svg_icon_file = os.path.join(_config_file_dir, svg_filename['svg_icons'])

colors = lib.Config(**config_files['Colors'])
_colors = {}
for color in colors:
    _colors[color.color] = color.hex
svg = kajsvg.SVG(_colors)

_debug_object = ""
_current_object = ""
_log = {}
_last_text = ""

_invoked_from_outside = len(sys.argv) > 1
if _invoked_from_outside:
    Command(sys.argv, invoked_from_outside=True)
else:
    user_input = lib.Config(enumerate_rows=True,
                            **config_files['Commands'])
    Command(user_input)
    if _log != {}:
        print("Ended %s, response time %s" % (
            datetime.datetime.now().strftime("%H:%M:%S"),
            lib.response_time()))
    if userbug.bug_count > 0:
        print("User bug count %s" % userbug.bug_count)
        log_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
        log_dir = os.path.join(log_dir, 'log')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        filename = os.path.join(log_dir, 'userbugs.txt')
        lib.save_as(filename, repr(userbug), True)