#!/usr/bin/env python
# -*- coding: latin-1 -*-

"""
HTML helper functions
"""

import datetime
import kajfmt as fmt


def tr(text):
    h = '\n<tr>%s</tr>' % text
    return h


def td(text):
    h = '<td>%s</td>' % text
    return h


def tdr(text):
    h = '<td align="right">%s</td>' % text
    return h


def th(text):
    h = '<th>%s</th>' % text
    return h


def thr(text):
    h = '<th align="right">%s</th>' % text
    return h


class HTML(object):
    def __init__(self, col_count=5, header_font="Open Sans",
                 text_font="Open Sans"):
        self.col_count = col_count
        self.header_font = header_font
        self.text_font = text_font
        self.title = ""
        self.desc = ""
        self.stamp = ""
        self._table_cols = 1
        self._using_table = False

    def set_title_desc(self, title, desc):
        self.title = title
        self.desc = desc

    def doc_header(self):
        current = datetime.datetime.now()
        start_date_time = "%s %s" % (fmt.dmyy(current), fmt.hm(current))
        url = "green-elk.com/util"
        comment = "Source: http://%s %s" % (url, start_date_time)
        url = '<a href="http://%s">%s</a>' % (url, url)
        self.stamp = 'GPL code by %s, the Outdoor Sports Community' % url
        self.stamp = self.span(self.stamp, "ge_green")
        subhead = start_date_time
        h1 = self.span(self.title, "ge_green")
        # noinspection PyPep8
        style = """\
 <style>
	p, th, td, li, .small {font-family: %s; }
	h1, h2, h3, h4 {font-family: %s; }
    a {text-decoration: none;}
    p {font-size: 10pt; orphans: 3; widows: 3;
      margin-top: 0pt; margin-bottom: 0; padding-top: 0; line-height: 120%%;}
    h1 {font-size: 16pt; margin: 3pt 0 20px 0;}
    h1 {font-size: 16pt; margin: 3pt 0 5pt 0;}
	h2, h3, h4 {margin: 2pt 0 1pt 0; padding: 2pt 0 0 2pt;}
    h2 {font-size: 14pt; page-break-after: avoid; border-top: 0px solid black;}
    h3 {font-size: 12pt; border-top: 1px solid black;
        background-color: #8cba5c;}
    h4 {font-size: 10pt; border-top: 0px solid black;
        background-color: rgba(140,186,92,0.5);}
    .subhead {font-size: 13pt; margin-top: 0;}
    .no_emph {font-size: 9pt; font-weight:normal;}
    .boilerplate {font-size: 7pt; padding-top: 10pt;}
    .columns {-webkit-column-count: §col; -moz-column-count: §col;
        column-count: §col; column-gap: 2em;}
    .ge_green {color: #668d3c;}
    .ge_lightest_green {background-color: #8cba5c;}
    .ge_red {background-color: #cf3a27;}
    .ge_blue {background-color: #4e6172;}
    .space {line-height: 20%%;}
    .small {font-size:11pt; font-weight:normal; }
    .red {color: #cf3a27;}
    .lr_tag {font-style: italic; font-size: 8pt; }
    @media print {.ge_red {color: #cf3a27;} .ge_blue {color: #4e6172;}}
    @page {margin: 0.9cm 0.5cm 0.7cm 0.5cm;}
 </style>
"""
        style %= (self.header_font, self.text_font)
        style = style.replace("§col", str(self.col_count))

        html_head = """\
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<!--%s-->
<html>
<head>
 <title>%s</title>
 <meta http-equiv="Content-type" content="text/html; charset=utf-8" />
%s
</head>

<body>
 <article>
  <header>
   <p class="subhead">%s</p>
   <h1>%s</h1>
  </header>
"""
        # <div class="columns">\n"""
        return html_head % (comment, self.title, style, subhead, h1)

    def doc_footer(self):
        footer = '   <p class="boilerplate">%s</p>' % self.stamp
        return "   </div>\n%s\n </article>\n</body>\n</html>" % footer

    def start_table(self, column_count=1):
        self._table_cols = column_count
        self._using_table = True
        return '\n\n<table>\n'

    def end_table(self):
        self._using_table = False
        return '\n\n</table>\n'

    @staticmethod
    def span(text, css_class):
        return '<span class="%s">%s</span>' % (css_class, text)

    def _before(self):
        return ('<tr><td colspan="%s">' % self._table_cols
                  if self._using_table else "")

    def _after(self):
        return '</td></tr>' if self._using_table else ""

    def h2(self, text):
        h = '\n\n%s<h2>%s</h2>%s\n' % (self._before(), text, self._after())
        return h

    def h3(self, text, is_first=False):
        div_start = "" if is_first else "\n</div>"
        h = '\n\n%s<h3>%s</h3>%s\n' % (self._before(), text, self._after())
        h = '%s\n%s\n<div class="columns">' % (div_start, h)
        return h

    def h4(self, text, within_table=False):
        h = '\n\n%s<h4>%s</h4>%s\n' % (self._before(), text, self._after())
        return h

