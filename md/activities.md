# kaj**gps**: Allocating activities

This document describes the logic by which kaj**gps** allocates activities 
(to days, tracks, track segments, maps etc.).

![Logo](https://lh3.googleusercontent.com/-KouDlj6ewlQ/VTUaFSBIlHI/AAAAAAAAUu0/WDKwZf2NXO8/s288/kajgps-green.png)

## Source of input

Activities can be partially judged based on **geodata available in tracks**, 
partially need **user input**.

Using only user input puts a lot of burden on the user. Yet some user tuning 
should be made possible.

The value of user input is maximised, by making small amounts of user input 
most meaningful. Default activity by day. Alternative activity during certain 
days. 

Exceptions include sporadic measurements of **supporting logistics**, i.e. 
road transport to and from starting points, ferry transport etc. These 
can be detected by speed (> 80 km/h is usually by road, regardless of 
sports activity) or a combination of speed and duration (> 50 km/h 
for > 10 km is also usually by road). Gaining or losing altitude is 
also a helpful indicator, especially in combination with the basic activity. 
A downhill skier or snowboarder doing > 5 km/h at a slope of over 8° uphill 
for > 4 minutes is likely in a ski lift. Such rules are combined into 
heuristics.

A key factor is **the speed of the iterative process**, by which correct 
activities for trips are identified. This involves
* keeping the **amount of user input low**, 
* keeping the **heuristics smart**, 
* keeping the **batch runs short**, and 
* keeping the **data entry of exceptions easy**. 
And it involves creating an easy overview (in both HTML and KML) of currently 
determined activities.

## Basic logic

The overall logic by which activities are chosen is this

1. **User input** of activity **by day**. 
2. Default from **previous batch** run of activities.
3. **Heuristics** based on distance, speed, and altitude change.
4. **User input** on exceptions, by day and **hour of day**.

The logic of 1-2-3-4 is re-applied for each run, as the end user can have 
made corrections in the day-activity allocation.

The above logic is less than ideal, in the scenario of several tracks per 
day. Having several tracks per day may be due to having several measurements 
for a particular stretch (for different participants, and/or by different 
devices), and having split up different stretches into different tracks (by 
mistake or by purpose). For the case where the different stretches have the 
same basic activity, the logic works fine. For the case where the different 
tracks refer ot distinct same-day trips with different activities, it's not 
ideal. The day will have just one default activity, and exceptions cannot be 
entered on track level, but must be entered on the fourth, "exception by time" 
level. This means that the exceptions don't go through any of the heuristic 
processing. However, this is something to merely be aware of; it should seldom 
surface as an item requiring additional action.