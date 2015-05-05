# kaj**gps**: Entering Placemarks

This document describes the ways to enter named locations (Placemarks) into 
kaj**gps**.

![Logo](https://lh3.googleusercontent.com/-KouDlj6ewlQ/VTUaFSBIlHI/AAAAAAAAUu0/WDKwZf2NXO8/s288/kajgps-green.png)

##Placemarks need to be in many files

### Primary places

* for **Google Earth**: `MyPlaces.kml`
* for kajgps **calculations**: `ge_places.csv` (faster format than `MyPlaces.kml`)
* for **easy editing**: `ge_places.ods`

### Secondary files
* export into *SVG* (for display on screen map)
* export into *HTML* (for display as a table)
* export into *GPX* (for input into other applications)

### Discovering improvements to data
* export routes into KML, to find missing points

## Issues and how to avoid them

1. Commas in placemark descriptions 
  * cause problems when kajgps reads in `ge_places.csv`
  * do not use commas in placemark names and descriptions
  * search for commas either in 
  * validation: find extra commas in `ge_places.csv` (assert)

2. Ampersands in placemark descriptions
  * caused problems when Google Earth displays KML
  * now avoided by substituting `&` with `&amp;` upon KML creation

3. Invalid placetypes
  * validation: find missing placetypes upon load

4. Not knowing which data is current
  * keep `ge_places.ods` the standard
  * dump `ge_places.ods` regularly to KML and csv

## Usability tips for end user

1. Keep **folder hierarchies** clean (Europe|Finland|Nagu)  
  * consistency in your own eyes

2. Keep **placemark ordering** clean
  * sort placemarks in the spreadsheet
  * always sort by folder hierarchy
  * within folder hierarchy, sort as you please
  * one idea: first by placetype, then west-to-east 

## Entering data

### Entering stray points, character based

* cut and paste lats and lons into corresponding spreadsheet cell
* remember to put lat before lon (some sources, notably KML, give lon before lat)

### Entering many points, over Google Earth

* create folder in My Places, e.g. Chillingholm
 * for ease of use, place it appropriately in the hierarchy
* save My Places (**all** placemarks)
* save just the new folder into a KML file, e.g. Chillingholm.kml
* use kaj**gps** to convert KML to CSV
 * `Places,edit,,Ängsö,,,,,/Users/kaj/Geodata/lib/placemark/kml/angso.kml,/Users/kaj/Geodata/lib/placemark/csv/angso.csv`
* edit the resulting CSV file into the `ge_places.ods` spreadsheet, using the guidelines in the rest of this document
 * in particular, give the places the right placetypes
 * while you're at it, give them appropriate ordering and prominence
* dump the new 'gold standard' placemarks
 * into KML form for re-entry into Google Earth, now with appropriate icons (based on placetypes)
 * into csv form `ge_places.csv` for usage in kaj**gps** (segment naming, calculations, svg maps etc.)
 * take care to copy the appropriate new parts
  * sometimes it's best to partly overwrite old data
  * sometimes it's better to just enter new data
  * in both cases, take care to a) not delete placemarks by mistake and b) not enter duplicates 

## Cleaning data

* to clean **placetypes**: sort the spreadsheet by placetype
* to clean **folders**: sort the spreadsheet by lat, lon or folder
* to clean **needlessly long names**: sort by name length, move text to description
