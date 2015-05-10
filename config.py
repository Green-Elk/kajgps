#!/usr/bin/env python
# -*- coding: utf-8

"""Parameters and hard coded defaults for kajgps"""

dir = dict(
    # Main configuration files
    config_file_dir='~/Code/kajgps/config',
    icon_dir='~/Code/kajgps/svg',
)

config = dict(
    # Default activity for loading new Tracks (has to match activity coding in settings)
    compression_tolerance=0.00001,
    # Maximum acceptable deviation in distance-along-path between compressed track and original track
    # compression_tolerance = 0.00001
)
