# kaj**gps**: Geodata analysis of tracks; management of placemarks (in .py)

kaj**gps** is an app for managing your geodata, both track files and 
placemarks.

![Logo](https://lh3.googleusercontent.com/-KouDlj6ewlQ/VTUaFSBIlHI/AAAAAAAAUu0/WDKwZf2NXO8/s288/kajgps-green.png)

(Pronunciation note: "*Kaj*" rhymes with "*rye*")

## Purpose of kaj**gps** ##

kaj**gps** is directed at GPS tracker users who wish to 
* manage their existing *recorded* tracks
* plan *future* tracks
* manage supportive geodata: *placemarks* and place icons (.svg, .png)

using an Open Source (GPLv3) application that converts geodata between
formats such as
* GPX (for most geodata programs)
* KML (for Google Earth, Google Maps etc.)
* HTML (for text based reporting and analysis of geodata)
* CSV (for entry and editing in spreadsheets and text editors)
* SVG (for simple vector graphics "maps" with tracks and placemarks, milestones 
and times, break points - but no "map canvas")
* json and geojson (limited support, for usage in apps)

## Requirements ##

* Python: Python 2.7 without add-on packages
  * Works in OS X 10.7+ as such
* Platform: OS X (but cross platform)
  * Developed first under OS X 10.6, now OS X 10.10
  * Is coded to be cross-platform but currently testing is not done outside 
  OS X
  * Actionable bug reports (preferrably with suggested patches) to make kajgps 
  platform independent will be implemented

## User interface ##

* kajgps.py has no graphical user interface
* kajgps.py works with text files in various formats (.csv .gpx etc.)
* kajgps.py works from the command line (either operating system level or 
Python command level)

## License and copyright ##

* GPLv3
* Copyright 2015 Green Elk [green-elk.com](http://www.green-elk.com) 
(Out-Sports Adventures Ab), Nagu, Finland
* Author Kaj Arnö [kajarno.com](https://kajarno.com)

## Installation ##

1. On **GitHub**, go to `https://github.com/Green-Elk/kajgps`
2. Click on the **`Download ZIP`** button in the lower right. 
   * You’ll get a zip file called `kajgps-master.zip`. 
3. **Unzip** `kajgps-master.zip` in the directory where you want to keep 
the source code 
   * We recommend `Code` under your home directory) 
   * The unzip process will create `Code/kajgps-master` as a directory
   * We recommend you to rename to to simply `Code/kajgps`
4. **Check** your installation from the operating system command level
   * `kajgps$ python kajgps.py check`

## Configuration ##

1. Read the **blog entry** "Using kajgps to make sense of your outdoors 
adventure tracks"
  * which expands upon the very brief elements below
2. **Adapt the core files** in `~/Code/kajgps/config` to your needs, using a text editor 
(if needed, in combination with a spreadsheet and kajgps.py itself)
  * `ge_places.csv` with your placemarks
  * `ge_areas.csv` with your placemark hierarchy
  * `ge_day_metadata.csv` with timezones and sports
  * `ge_time_metadata.csv` with exceptions to `ge_day_metadata.csv`
3. If you're using kajgps.py more liberally (in a non-outdoors-sports setting), 
also adapt the following `~/Code/kajgps/config` files
  * `ge_activities.csv`, the activities of which are sports in the default 
  Green Elk use case
  * `ge_placetypes.csv`, where the types which relate to sports relevant 
  placemarks
  * `ge_forced_breaks.csv`, whereby tracks can be split up into segments 
  when a point is passed
  * `ge_colors.csv`, where activity specific colors are tailored
  
## Running kajgps.py ##

* Enter your **parameters** into `~/Code/kajgps/config/ge_commands.csv` 
(with your favourite text editor)
  * In this comma-separated file, enter parameters, source data files, and 
  destination files in the corresponding columns
* From the **command level** of the operating system, run
  * `cd ~/Code/kajgps`
  * `python kajgps.py`
* **Repeat** as necessary
  * Refine your parameters as needed 
  * Re-issue `python kajgps.py` as needed
  * Review and use the output data (GPX, HTML, SVG, CSV) in the corresponding 
  software (Google Earth, a browser, a spreadsheet) as needed

## Further markdown documentation ##

* How are [activities](md/activities.md) allocated?
* How are [placemarks](md/placemarks.md) entered?
* (Coding Guidelines for kajgps.py)[md/code_guidelines.md]

## Core kajgps.py related blog entries ##

* Releasing adventure mapping software
* Ten basic concepts around GPS adventure tracks
* How to best track your outdoors adventures
* Three sources of adventure geodata you already have
* Using kajgps to make sense of your outdoors adventure tracks