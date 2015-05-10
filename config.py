#!/usr/bin/env python
# -*- coding: utf-8

"""Parameters and hard coded defaults for kajgps"""

dir = dict(
    # Main configuration files
    config_file_dir='~/Code/kajgps/config',
)

config = dict(

    # Directories to start scanning from
    track_base_dir='/Users/kaj/Geodata/src/2014',
    # The topmost directory to scan for tracks
    pict_base_dir='/Volumes/LaCie/kaj/Bilder/rep/2013/kajak/2013-06-23--26_Kokar/2013-06-25_AW110',
    # The topmost directory to scan for pictures

    # Other files
    file_pattern='*.[jJ][pP][gG]',
    # The file types to scan

    # Track analysis parameters
    activity_id='skida',
    # Default activity for loading new Tracks (has to match activity coding in settings)
    compression_tolerance=0.00001,
    # Maximum acceptable deviation in distance-along-path between compressed track and original track
    # compression_tolerance = 0.00001

    # Reporting parameters: Selection criteria and sorting
    selected_activities='vandra,paddla,cykla,springa,bat,skida',
    # selected_activities = 'vandra,mtb,paddla,cykla,skida,skitour,springa,bil,bat,flyg,fota,hus,segla',
    # selected_areas = 'vandra,mtb',
    time_zone=+3,
    # The time zone (e.g. +3, -3) to be currently used for (input and) output (FIX: should be deduced from time and coordinates)
    header='Kajs äventyr sommaren 2014 %timestamp',
    # Header for reports (KML and otherwise); %timestamp substituted at runtime
    milestones='No labels,1;Details,0;n km,0;hh:mm,0',
    # milestones = 'No labels,1;Details,0;n km,0;hh:mm,0',
    sort_order='activity,area',
    # Aggregation (subheader) levels and sort orders of reports
    multiple_files='activity,area',
    # If non-zero-length: Output is divided into multiple files for each combination of the entered fields
    #track_format='etapes,breaks,deciles,milestones,names',
    track_format='breaks,segments',
    # Sections of track-level reporting (currently used for KML only)
    # track_format = 'etapes,breaks,deciles,milestones,names',
    # track_format = 'single',

)
