#!/usr/bin/env python
# -*- coding: latin-1 -*-

"""
Geodata analysis of tracks; management of placemarks
"""

import os.path
from time import strftime

import kajfmt as fmt
import kajlib as lib


def merge(dir_, svg_files, filename, prominence=9):
    """
    Merge many .svg files into one large, with def pointers
    :param dir_: directory where .svg files are
    :param svg_files: list of svg files to be merged ['one.svg','two.svg'..]
    :param filename: outfile, such as merged.svg
    """
    dir_ = os.path.abspath(dir_)  # should there be a ~/ home reference

    defs = ""
    use = ""
    icons = []
    for svg_file in svg_files:
        svg_input_file = os.path.join(dir_, svg_file)
        icon_id = svg_file.replace(".svg", "")
        icons.append(icon_id)
        if not os.path.isfile(svg_input_file):
            raise Exception("merge: file %s does not exist" % svg_input_file)
        with open(svg_input_file) as f:
            defs += '\n  <g id="%s">\n' % icon_id
            before_start = True
            file_has_viewbox = False
            for svg_row in f.readlines():
                before_start = before_start and not "<svg" in svg_row
                if before_start:
                    continue
                    # Uncomment next row to check whether all files
                    # claim encoding="utf-8"
                    # print svg_row
                desired_width = "5"  # And height, too
                for token in ['width="', 'height="']:
                    row_has_token = (token in svg_row and
                                     not '-%s' % token in svg_row)
                    if row_has_token:
                        before, after = svg_row.split(token)
                        end = after[after.find('"'):]
                        svg_row = before + token + desired_width + end
                defs += svg_row
                row_has_viewbox = "viewBox" in svg_row
                file_has_viewbox = file_has_viewbox or row_has_viewbox
                if row_has_viewbox:
                    if not 'viewBox="0 0' in svg_row:
                        print('%s: Strange viewBox row, not starting in\
 viewBox="0 0"\n %s' % (icon_id, svg_row.strip()))
            if not file_has_viewbox:
                print("%s: SVG source has no viewBox - please edit" % icon_id)
            defs += '\n  </g>\n'

    use_template = """
        <use %s />
        <use %s fill="#cf3a27" transform="translate(7 0) rotate(-30 %s %s)"/>
        <use %s fill="#668d3c" transform="translate (14 0) rotate(45 %s %s)"/>
    """

    for i, icon in enumerate(icons):
        x = 10 + 24 * int(i/20)
        y = 10 * (i % 20)
        xlink = 'xlink:href="#%s" x="%s" y="%s"' % (icon, x, y)
        x2 = x + 2.5
        y2 = y + 2.5
        use += use_template % (xlink, xlink, x2, y2, xlink, x2, y2)

    date_format_string = "%a %d.%m.%Y %H:%M:%S"

    before = """<?xml version="1.0" standalone="no"?>
    <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"
     "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
     <svg width="200.0mm" height="287.0mm" viewBox="0 0 200.0 287.0"
          xmlns="http://www.w3.org/2000/svg" version="1.1"
          xmlns:xlink="http://www.w3.org/1999/xlink" xml:space="preserve">
     <title>SVG icons %s</title>
     <descr></descr>

     <defs>
    """ % (strftime(date_format_string))

    between = " </defs>\n"
    after = "</svg>"

    contents = before + defs + between + use + after

    lib.save_as(filename, defs, True)
    demo_filename = filename.replace(".svg", "-demo.svg")
    lib.save_as(demo_filename, contents, True)


class SVG(object):
    """Output class for SVG"""

    def __init__(self, colors):
        self.canvas = {}
        self.margins = {}
        self.title = ""
        self.desc = ""
        self.colors = colors
        self.map = None
        self.pixels = None

        self.set_canvas()

    def doc_header(self, more_defs=""):
        height = self.canvas['mm']['height']
        width = self.canvas['mm']['width']
        return """\
<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"\
 "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
 <svg width="%smm" height="%smm" viewBox="0 0 %s %s"
      xmlns="http://www.w3.org/2000/svg" version="1.1"
      xmlns:xlink="http://www.w3.org/1999/xlink" xml:space="preserve">\n
 <title>%s</title>
 <desc>%s</desc>
 <!-- %s -->\n
 <defs>
 <style type="text/css"><![CDATA[
    .header { font-family: trailmap; font-size: 3mm; }
    .small_header { font-size: 1.5mm; }
    text {font-family: titillium web; font-size: 2mm;
          fill: black; stroke: none; }
    polyline, rect {fill: none;}
    * { stroke: black; stroke-width: 0.2; }
    ]]></style>
  <marker id='mid' orient="auto"
    markerWidth='6' markerHeight='12' refX='0.3' refY='3'>
    <path d='M0,0 V6 L3,3 Z'/>
  </marker>
  %s
 </defs>\n""" % (width, height, width, height, self.title, self.desc,
                 fmt.current_timestamp(), more_defs)

    @staticmethod
    def doc_footer(comment=""):
        return "%s\n</svg>" % comment

    @staticmethod
    def comment(text):
        return "\n<!-- %s -->\n" % text

    def set_canvas(self, format_="A4"):
        if format_ == "A4":
            self.canvas = {'format': format_,
                           'mm': {'width': 210, 'height': 297}}
        else:
            raise Exception("SVG.set_canvas: Unsupported canvas format %s" %
                            format_)

    def set_orientation(self, orientation="portrait"):
        larger = max(self.canvas['mm'].values())
        smaller = min(self.canvas['mm'].values())
        self.canvas['orientation'] = orientation
        if orientation == "portrait":
            self.canvas['mm'] = {'width': smaller, 'height': larger}
        elif orientation == "landscape":
            self.canvas['mm'] = {'width': larger, 'height': smaller}
        else:
            raise Exception("SVG.set_orientation: Unsupported orientation %s" %
                            orientation)

    def reset_margins(self):
        self.margins = {}

    def def_margins(self, frame, unit, top, right, bottom, left):
        self.margins[frame] = {unit: {'top': top, 'right': right,
                                      'bottom': bottom, 'left': left}}

    def set_margins(self):
        for frame in list(self.margins):
            self.canvas[frame] = {}
            for unit in list(self.margins[frame]):
                # noinspection PyPep8,PyPep8
                trbl = {'top': self.margins[frame][unit]['top'],
                        'right': self.canvas[unit]['width'] -
                                 self.margins[frame][unit]['right'],
                        'bottom': self.canvas[unit]['height'] -
                                  self.margins[frame][unit]['bottom'],
                        'left': self.margins[frame][unit]['left']}
                trbl['width'] = trbl['right'] - trbl['left']
                trbl['height'] = trbl['bottom'] - trbl['top']
                trbl['x_mid'] = trbl['left'] + trbl['width'] / 2.0
                trbl['y_mid'] = trbl['top'] + trbl['height'] / 2.0
                trbl['aspect_ratio'] = float(trbl['height']) / trbl['width']
                self.canvas[frame][unit] = trbl

    def empty_canvas(self):
        self.pixels = Pixels(self.canvas['mm']['width'],
                             self.canvas['mm']['height'])
        self.icon_pixels = Pixels(self.canvas['mm']['width'],
                             self.canvas['mm']['height'])

    def set_title(self, title, desc):
        self.title = title
        self.desc = desc

    def set_graph_window(self):
        pass

    def style(self, style_dict):
        if style_dict is None:
            return ""
        s = ""
        for property_ in list(style_dict):
            value = style_dict.get(property_, None)
            if property_ in ['fill', 'stroke']:  # Translate colours
                value = lib.app_color(self.colors, value)
            if value is not None:
                s += "%s: %s; " % (property_, value)
        return ' style="%s"' % s if s != "" else ""

    def plot_text_mm(self, x, y, text, style_dict=None, class_=None,
                     angle=0.0, dy=0.0):
        class_ = "" if class_ is None else ' class="%s"' % class_
        transform = ("" if angle == 0 else
                     ' transform="rotate(%s %s %s)"' % (angle, x, y))
        text = '<tspan dy="%s">%s</tspan>' % (dy, text) if dy != 0 else text
        s = ' <text x="%s" y="%s"%s%s%s>%s</text>\n'
        font_size = style_dict.get('font-size', 2)
        text_anchor = style_dict.get('text-anchor', 'left')
        #print "text %s in font size %s adjustment %s" % (text, font_size, text_anchor)
        length = len(text)
        x1_factor = {'left': 0, 'middle': -0.5, 'end': -1}[text_anchor]
        x2_factor = {'left': 1, 'middle': 0.5, 'end': 0}[text_anchor]
        x1 = x + x1_factor * length * font_size / 2
        y1 = y - font_size + 1
        x2 = x + x2_factor * length * font_size / 2
        y2 = y + 1
        #print "set-pixels x1-x2 %s-%s y1-y2 %s-%s" % (x1, x2, y1, y2)
        if self.pixels is None:
            is_free = True
        else:
            is_free = self.pixels.rectangle_is_empty(x1, y1, x2, y2)
        if not is_free:
            #print "text is not free %s" % text
            return ""
        if self.pixels is not None:
            self.pixels.set(x1, y1, x2, y2)
        return s % (fmt.mm2(x), fmt.mm2(y), self.style(style_dict),
                    class_, transform, text)

    def plot_icon_mm(self, cx, cy, r=2.5, icon="circle", color="Red"):
        x1, y1, x2, y2 = cx - r, cy - r, cx + r, cy + r
        if self.pixels is None:
            is_free = True
        else:
            is_free = self.pixels.rectangle_is_empty(x1, y1, x2, y2)
        if not is_free:
            #print "icon is not free %s" % icon
            return ""
        if self.pixels is not None:
            self.pixels.set(x1, y1, x2, y2)
        if icon == "circle":
            s = '<circle cx="%s" cy="%s" r="%s" '
            s += 'fill="%s" stroke="black" stroke-width="0.2" />\n'
            return s % (cx, cy, r, color)
        else:
            scale = r/2.5
            s = '<use xlink:href="#%s" x="%s" y="%s" style="fill:%s;" %s/>\n'
            s = '<use xlink:href="#{}" transform="translate({:.1f},{:.1f}) '
            s += 'scale({:.1f})" style="fill:{};" />\n'
            return s.format(icon, cx - r, cy - r, scale, color)

    def plot_line_mm(self, x1, y1, x2, y2, style_dict=None):
        line = ' <line x1="%s" y1="%s" x2="%s" y2="%s" %s/>\n'
        return line % (fmt.mm2(x1), fmt.mm2(y1), fmt.mm2(x2), fmt.mm2(y2),
                       self.style(style_dict))

    def plot_rect_mm(self, x, y, width, height, style_dict=None):
        r = ' <rect x="%s" y="%s" width="%s" height="%s" %s/>\n'
        return r % (fmt.mm2(x), fmt.mm2(y), fmt.mm2(width), fmt.mm2(height),
                    self.style(style_dict))

    def plot_framed_sign_mm(self, x, y, text):

        text = text.decode('utf-8').upper().encode('utf-8')

        height = 4.8
        margin = 0.4
        font_size = 3.0
        stroke_width = 0.3
        fi_blue = '#0091FF'
        width = 2.3 * len(text.decode('utf-8'))  # SJÄLÖ is otherwise 7 char
        inner_width = width - 2 * margin
        inner_height = height - 2 * margin

        xa = x - width / 2
        ya = y
        xb = xa + margin
        yb = y + margin
        xc = x
        yc = y + font_size + 0.5

        style_a = {'fill': fi_blue, 'stroke-width': 0}
        style_b = {'fill': fi_blue, 'stroke-width': stroke_width, 'stroke': 'white'}
        style_c = {'fill': 'white', 'font-size': font_size, 'text-anchor': 'middle'}
        r = self.plot_rect_mm(xa, ya, width, height, style_a)
        r += self.plot_rect_mm(xb, yb, inner_width, inner_height, style_b)
        r += self.plot_text_mm(xc, yc, text, style_c)
        return r

    def polyline_begin(self, style_dict=None, class_="", marker=""):
        self.canvas['polyline'] = {'style': self.style(style_dict),
                                   'marker': marker,
                                   'class_': class_, 'points': []}

    def polyline_add_point(self, x, y):
        self.canvas['polyline']['points'].append([x, y])

    def plot_polyline(self):
        polyline = self.canvas['polyline']
        class_ = ('class="%s"' % polyline['class_']
                  if polyline['class_'] != "" else '')
        points = polyline['points']
        s = (' <polyline %s %s %s points="' % (polyline['style'],
                                               polyline['marker'], class_))
        if len(points) == 0:
            return self.comment('No points - Empty%s' % s)
        columns = 6
        for i, point in enumerate(points):
            if i % columns == 0:
                s += "\n   "
            s += "{:.2f},{:.2f} ".format(*point)
        s += '" />\n'
        return s

    def plot_header(self, text, frame, h, v, dx=0, dy=0,
                    class_=None, style_dict=None):
        if style_dict is None:
            style_dict = {}
        x = self.canvas[frame]['mm'][h] + dx
        y = self.canvas[frame]['mm'][v] + dy
        angle = 0
        style_dict['text-anchor'] = {'left': 'left', 'x_mid': 'middle',
                                     'y_mid': 'middle', 'right': 'end', }[h]
        if v == 'y_mid':
            x += {'left': -1, 'right': +5, 'x_mid': 0}[h]
            angle = 0 if h == 'x_mid' else -90
            style_dict['text-anchor'] = 'middle'
        y += {'bottom': +5, 'top': -1, 'y_mid': 0}[v]
        return self.plot_text_mm(x, y, text, style_dict, class_, angle=angle)

    def plot_frame(self, frame, style=None):
        style = {} if style is None else style
        s = self.comment("Plot %s frame" % frame)
        #print "frame %s self.canvaws %s " % (frame, self.canvas)
        #print "self.canvas[frame] %s " % (self.canvas[frame])
        #print "self.canvas[frame]['mm'] %s " % (self.canvas[frame]['mm'])
        margins = self.margins[frame]['mm']
        canvas = self.canvas[frame]['mm']
        s += self.plot_rect_mm(margins['left'], margins['top'],
                               canvas['width'], canvas['height'], style)
        return s

    @staticmethod
    def speed2colour(speed_kmh):
        colour_speed = [[2, "#af8000"], [5, "#ff8000"], [10, "#ff4000"],
                        [15, "#ff0000"], [20, "#af2000"], [25, "#802000"],
                        [30, "#602000"], [40, "#402000"]]
        for speed, colour in colour_speed:
            if speed_kmh < speed:
                return colour
        return "#ffffff"

    def printer_testing_raster(self):
        s = self.comment("Raster to test printable area of printers")
        s += self.comment("Vertical lines")
        y1 = 0
        y2 = self.canvas['mm']['height']
        for x in range(0, self.canvas['mm']['width'] + 1):
            if x % 20 == 0:
                style = {'stroke-width': 0.2}
            elif x % 5 == 0:
                style = {'stroke-width': 0.1, 'stroke': "red"}
            else:
                style = {'stroke-width': 0.05}
            s += self.plot_line_mm(x, y1, x, y2, style)

        s += self.comment("Horisontal lines")
        x1 = 0
        x2 = self.canvas['mm']['width']
        for y in range(0, self.canvas['mm']['height'] + 1):
            if y % 20 == 0:
                style = {'stroke-width': 0.2}
            elif y % 5 == 0:
                style = {'stroke-width': 0.1, 'stroke': "red"}
            else:
                style = {'stroke-width': 0.05}
            s += self.plot_line_mm(x1, y, x2, y, style)
        return s

    def draw_pixels(self):
        s = ""
        for x in range(0, self.pixels.x_max):
            for y in range(0, self.pixels.y_max):
                if self.pixels.matrix[y][x]:
                    s += self.plot_rect_mm(x, y, 1, 1, {'fill': 'red',
                                                        'opacity': 0.2})
        return s


class Pixels(object):
    def __init__(self, x_max=300, y_max=300):
        self.x_max = x_max
        self.y_max = y_max
        self.matrix = [[False for x in range(0, x_max)]
                       for y in range(0, y_max)]

    def clean(self, x1, y1, x2, y2):
        x1 = max(0, int(x1))
        x2 = min(self.x_max, int(x2))
        y1 = max(0, int(y1))
        y2 = min(self.y_max, int(y2))
        return x1, y1, x2, y2

    def set(self, x1, y1, x2, y2):
        x1, y1, x2, y2 = self.clean(x1, y1, x2, y2)
        for x in range(x1, x2):
            for y in range(y1, y2):
                self.matrix[y][x] = True

    def rectangle_is_empty(self, x1, y1, x2, y2):
        x1, y1, x2, y2 = self.clean(x1, y1, x2, y2)
        no_text = True
        for x in range(x1, x2):
            for y in range(y1, y2):
                no_text = no_text and not self.matrix[y][x]
        return no_text
