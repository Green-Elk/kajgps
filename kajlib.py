#!/usr/bin/env python
# -*- coding: latin-1 -*-

"""
Library of commonly used functions in kajgps and elsewhere
"""

from functools import wraps
from collections import namedtuple

import datetime
import codecs
import sys
import errno
import os
import csv

import kajfmt as fmt
import kajhtml
from kajhtml import td, tdr, th, thr


def start_log(debug_object, text=""):
    now = datetime.datetime.now()
    print("start_log %s" % now)
    global _log, _debug_object
    _debug_object = debug_object
    _log = {'stack': [], 'object': _debug_object, 'text': text,
            'start_time': now, 'last_time': now}
    _log['stack'].append("%s\n%s: start %s" % (now.date(), now.time(), text))


def log_event(text, count=None, decorated=False):
    if decorated and _log.get('object') != _debug_object:
        return
    current = datetime.datetime.now()
    print("log_event %s" % current)
    delta = current - _log['last_time']
    count_text = " (%s)" % count if count is not None else ""
    _log['last_time'] = current
    _log['stack'].append("+%s%s: %s" % (str(delta), count_text, text))


def response_time():
    log_event("End")
    print "from %s to %s" % (_log['start_time'], _log['last_time'])
    return str(_log['last_time'] - _log['start_time'])


def log_rpt():
    s = "Log report "
    for r in _log['stack']:
        s += r + "\n"
    return s + ">" + response_time()


def log_rpt_html():
    s = "Object %s" % _log['object']
    for r in _log['stack']:
        s += "\n<br>"+r
    s += "<br>Now: %s" % datetime.datetime.now()
    return s + "\n<br>" + response_time()


def logged(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if args[0].__class__.__name__ != _debug_object:
            return func(*args, **kwargs)
        log_event(func.__name__ + " start", decorated=True)
        result = func(*args, **kwargs)
        log_event(func.__name__ + " end", decorated=True)
        return result
    return wrapper


def rgb2aabbggrr(rgb_str):  # colour conversion for KML
    return "ff" + rgb_str[4:6] + rgb_str[2:4] + rgb_str[0:2]


def decile_color(decile):  # Ten colours in a continuum
    values = ["FF0", "FC3", "F96", "F90", "F63",
              "F33", "C33", "C00", "900", "600"]
    rgb = values[decile - 1]
    rgb = rgb[0]*2 + rgb[1]*2 + rgb[2]*2
    return rgb2aabbggrr(rgb)


def app_color(color_dict, color):
    """App-specific global colours, if exist - otherwise default colours"""
    return color_dict.get(color, color)


def indent(text, levels=0, step=1, char=" "):  # char="tab" -> \t
    char = chr(9) if char == "tab" else char
    prepend = char * levels * step
    return prepend + text.replace('\n', '\n' + prepend) + "\n"


def ensure_dir(dir_name):
    try:
        os.makedirs(dir_name)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise


def save_as(filename, a_str, verbose=False):
    a_unicode = a_str
    if sys.version_info < (3,):
        if type(a_str) is str:
            a_unicode = unicode(a_str, "utf-8")

    with codecs.open(filename, "w", "utf8") as f:
        val = f.write(a_unicode)
        if verbose:
            chars = i1000((len(a_str)))
            print("%s chars saved into file %s" % (chars, filename))
    return val


def i1000(an_int):
    """Example: 1.234.567"""
    return "{0:,}".format(an_int).replace(",", ".")


def csv_header_instructions(count, item, filename):
    s1 = """\
# Saved %s Green Elk %ss on %s
#   in file named %s
"""
    s2 = """\
# Instructions:
# - edit in your favourite text editor
# - alternatively, use a spreadsheet (OOo tested in Excel mode)
# - sort and edit as desired
# - save the file again as csv
# - upon import, empty rows and # comment rows will be ignored
# - the # and empty row layouting is hence only to give you an overview
#   of a freshly created csv file
#
# On formats:
# - do retain the first line with field names unchanged (required by program)
# - UTF8 is to be used; åäö should show as aao with ring and dots
#   (if not, change your editor format or face problems later)
# - Text fields with commas, double " and single ' quotes will be
#   "safe quoted", i.e. surrounded by " and the " itself is doubled
#   (courtesy of Python import csv)
"""
    timestamp = "%s, %s" % (fmt.current_date_yymd(),
                            fmt.current_time_hm())
    return s1 % (count, item, timestamp, filename), s2


class Config(object):
    def __init__(self, item, fields, filename, enumerate_rows=False,
                 dir_=None):
        full_filename = os.path.join(dir_, filename)
        self.item = item
        self.fields = fields
        self.filename = full_filename
        self.enumerate_rows = enumerate_rows
        self.list = []
        self.dict = {}
        self.field_list = fields.split()
        self.first_field_name = self.field_list[0]
        self.timestamp = "%s, %s" % (fmt.current_date_yymd(),
                                     fmt.current_time_hm())

        # enumerate_rows = create artificial key, to allow duplicates
        # of first field (which otherwise is taken as a key)
        if enumerate_rows:
            self.fields = "z_rowno_ " + self.fields
        self.field_list = self.fields.split()
        self.index_field_name = self.field_list[0]
        self.field_count = len(self.field_list)

        if not os.path.exists(self.filename):
            e = "Config %s missing file %s" % (item, full_filename)
            raise Exception(e)
        self.import_csv()

    def __getitem__(self, item):
        if type(item) == str:
            return self.dict.get(item, "")
        elif type(item) == int:
            return self.dict[self.list[item]]

    def __setitem__(self, key, value):
        if type(key) == str:
            self.dict[key] = value

    def __str__(self):
        s = "Config('%s'): %s items"
        s += " fields: %s"
        s += " filename: %s"
        return s % (self.item, len(self.list), self.fields, self.filename)

    def __repr__(self):
        s = str(self)
        for row in self:
            s += "\n"
            for field in row:
                s += str(field) + " "
        return s

    def __len__(self):
        return len(self.list)

    def exists(self, item):
        return self.dict.get(item) is not None

    def as_html(self, subhead_field=None, field_transformations=None):
        html = kajhtml.HTML()
        html.set_title_desc(self.item, self.filename)
        h = html.doc_header()

        field_count = self.field_count
        use_subheads = subhead_field is not None
        if use_subheads:
            field_count -= 1
        h += "\n\n<table>"
        h += "\n<tr>"
        if self.enumerate_rows:
            h += td("")
        r = dict(self[0]._asdict())
        for field in self.field_list:
            if field == subhead_field:
                continue # Don't list subhead field redundantly as column
            val = r[field]
            if isinstance(val, (int, float)):
                h += thr(field)
            else:
                h += th(field)
        h += "</tr>"
        prev_subhead = subhead = ""
        for i, row in enumerate(self):
            r = dict(row._asdict())
            if use_subheads:
                subhead = "%s: %s" % (subhead_field, r[subhead_field])
                if subhead != prev_subhead:
                    h += '\n<tr><td colspan="%s">' % field_count
                    h += html.h4(subhead)
                    h += '</td></tr>'
            h += "\n<tr>"
            if self.enumerate_rows:
                h += tdr(i)
            for field in self.field_list:
                if field == subhead_field:
                    continue # Don't list subhead field redundantly as column
                val = r[field]
                if isinstance(val, (int, float)):
                    h += tdr(val)
                else:
                    if field_transformations is not None:
                        for t_field, t_function in field_transformations:
                            if field == t_field:
                                val = t_function(val)
                    h += td(val)
            h += "</tr>"
            prev_subhead = subhead

        h += "</table>"
        h += html.doc_footer()
        return h

    def import_csv(self, verify=False):
        def verify_no_value_is_none():
            for field in self.fields.split():
                if row.get(field) is None:
                    e = "Field %s is None for '%s' row " % (field, self.item)
                    e += "%s ('%s').\nEdit file " % (i, first_field)
                    e += "%s (and check for similar errors)." % self.filename
                    raise Exception(e)
        full_filename = self.filename
        named_t = namedtuple(self.item, self.fields)
        tuple_instance = named_t(*[''] * self.field_count)
        with open(full_filename) as csvfile:
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                if self.enumerate_rows:
                    row['z_rowno_'] = str(i)
                first_field = row[self.first_field_name]
                index_field = row[self.index_field_name]
                is_blank = len(first_field.strip()) == 0
                is_comment = (first_field + " ")[0] == "#"
                if not (is_blank or is_comment):
                    # noinspection PyProtectedMember
                    if verify:
                        verify_no_value_is_none()
                    r = tuple_instance._replace(**row)
                    self.list.append(index_field)
                    self.dict[index_field] = r

    def missing_fields(self):
        count = 0
        msg = []
        for i, entry in enumerate(self.list):
            row = self.dict[entry]
            for field in self.fields.split():
                if getattr(row, field) is None:
                    count += 1
                    first_field = getattr(row, self.first_field_name)
                    text = "Item %s (%s): Field %s is None"
                    text %= (i, first_field, field)
                    msg.append(text)
        return count, msg

    def duplicates(self):
        count = 0
        msg = []
        self.list.sort()
        prev_first_field = ""
        for i, entry in enumerate(self.list):
            row = self.dict[entry]
            first_field = getattr(row, self.first_field_name)
            if first_field == prev_first_field:
                count += 1
                text = "Item %s (%s): Row is duplicate"
                text %= (i, first_field)
                msg.append(text)
            prev_first_field = first_field
        return count, msg

    def integrity(self, field, other_table):
        count = 0
        msg = []
        for i, entry in enumerate(self.list):
            row = self.dict[entry]
            value = getattr(row, field)
            other_value = other_table[value]
            if other_value is "":
                count += 1
                first_field = getattr(row, self.first_field_name)
                text = "Item %s (%s): %s %s is missing"
                text %= (i, first_field, field, value)
                msg.append(text)
        return count, msg

    def save_as(self, filename, subhead_field=None,
                field_transformations=None):
        file_format = filename.split(".")[-1]
        if file_format == 'csv':
            self.save_as_csv(filename, subhead_field)
            return
        if file_format == 'html':
            a_str = self.as_html(subhead_field,
                                 field_transformations=field_transformations)
            save_as(filename, a_str, verbose=True)

    def save_as_csv(self, filename, subhead_field=None):
        with open(filename, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fields.split())
            writer.writeheader()
            h1, h2 = self._csv_header_instructions()
            csvfile.write("\n%s\n%s\n" % (h1, h2))
            use_subheads = subhead_field is not None
            prev_subhead = subhead = ""
            for row in self:
                r = dict(row._asdict())
                if use_subheads:
                    subhead = r[subhead_field]
                    if subhead != prev_subhead:
                        csvfile.write("\n# %s\n" % subhead)
                writer.writerow(r)
                prev_subhead = subhead

    def _csv_header_instructions(self):
        return csv_header_instructions(len(self.list), self.item,
                                       self.filename)


class Userbug(object):
    def __init__(self, name, verbose=True):
        self.name = name
        self.bug_count = 0
        self.list = []
        self.timestamp = "%s, %s" % (fmt.current_date_yymd(),
                                     fmt.current_time_hm())

    def __str__(self):
        s = "Userbug('%s'): %s items"
        s += " start: %s\n"
        return s % (self.name, len(self.list), self.timestamp)

    def __repr__(self):
        s = str(self)
        for row in self.list:
            s += " %s" % row
        return s

    def add(self, text):
        self.list.append(text)
        self.bug_count += 1
        print "Userbug added: %s" % text
