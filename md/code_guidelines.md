# Coding Guidelines for `kaj**gps**.py` 

## Audience: The User

Even if you have no intention of contributing any code to kaj**gps**, this
document may still be for you. Part of the below guidelines have **usability** 
implications for all users, and many of the others are significant for those 
who wish to **submit bugs** or **enhancement requests**.

## Preamble: Good intentions

The following thoughts have guided the configuration and coding style of 
Green Elk’s adventure mapping software kajgps.py. If you notice **violations** 
of the style, do alert us. Also, if you think the style is **bad manners**, do 
alert us. In both cases, assume the coder has good intentions and good will.

## Configuration: Balance **features** against **configuration work**
* Make things work with minimum configuration (through smart defaults)
* Catch configuration errors early
* Make incomplete configuration work stand out (assert configuration files)
* Keep the number of configuration files low
