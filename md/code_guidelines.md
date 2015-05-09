# Coding Guidelines for kaj**gps** 

## Audience: The User

Even if you have no intention of contributing any code to kaj**gps**, this
document may still be for you. Part of the below guidelines have **usability** 
implications for all users, and many of the others are significant for those 
who wish to **submit bugs** or **enhancement requests**.

## Preamble: Good intentions

The following thoughts have guided the configuration and coding style of 
Green Elk’s adventure mapping software kajgps.py. If you notice **violations** 
of the style, do alert us. Also, if you think the style itself is **bad 
manners**, do alert us. In both cases, assume the coder has good intentions 
and good will.

## Usability guidelines: Installation

### Language version and package installation: Low threshold
* If possible, **require no patching of Python** on a reasonably new Mac
* Consequently, use **Python 2.7** and `import` only **built-in packages**
* Facilitate moving to Python 3, such as using `print()` instead of mere 
`print`

## Usability guidelines: Configuration

### Configuration: Balance **features** against **configuration work**
* Make things work with minimum configuration (through smart defaults)
* Catch configuration errors early
* Make incomplete configuration work stand out (assert configuration files)
* Keep the number of configuration files low

### Parametres on code level: Run a tight ship
* Keep parametres **in config files**, separated from non-user-dependent code
* Make parameters **stand out** (in code, in files)
* Tie parameters to the **right entity** (user, trip, day etc.) and the 
**right piece of code**
* Avoid **magic numbers** in code (but not in a fundamentalist way; 
**don’t drown** the real parametres in a sea of quasi parameters hardly 
anybody needs to change)

## Usability guidelines: User feedback

### User feedback: Moderately verbose 
* When saving files, console log the **filename** and **directory**, and 
**file size**
* Give some indication of things happening and of **remaining response time**, 
such as console logging a text “`14:25 GPX track 34 of 401`”
* Otherwise, be moderately verbose; if a non-obvious configuration item 
influences calculations (such as guessing activities based on speeds and 
durations), indicate the program logic through a descriptive comment

## Usability guidelines: Internationalisation

### User data formatting: Meet most expectations, but not all
* Use **km** for storing distances; allow output in miles 
* Use **km/h** for storing speeds; allow output in mph
* Use **m** for storing elevations and altitudes; allow output in feet
* Format km and km/h with **one decimal**, and use comma as decimal separator
* Format miles and mph with one decimal, and use point as decimal separator 
* Format m and ft as **integers**
* Use **d.m.yy** when merely displaying dates, and **yy-m-d** when displaying 
a date influences ordering
* Use the **24h** clock

### Limitations in support of non-metric, non-European user data formatting
* The excuse in all cases is “**too much error-prone and laborious 
configuration**”; there needs to be a balance between the complexity of the 
parameter structure and the value add
* The excuse in some cases is “**too much space**” (as the 12h clock takes more 
space than the 24h clock, and month names in text do so too, even if 
shortened to three chars) 
* The excuse in some cases is “**do your own visualisation layer**”; for UIs, 
there are widgets in particular for dates and times, where the text output 
isn’t used at all
* Decimal points (as opposed to commas) only used with miles, not km
* No usage of mdy dates
* No usage of 12h clock
* No usage of knots

## Coder guidelines

### Code formatting
* Keep the code “green”, i.e. fix any **PyCharm** warnings
* Keep the code reasonably **PEP-8 compliant**, especially for whitespace
* Line length below 80

### Code readability: Make the code easy to read
* Use descriptive variable and method names
* Keep all methods short
* Keep __init__ methods particularly short
