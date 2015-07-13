# Introduction #
The microformat used by this application in order to render tasks in HTML is based loosely on the specification for hCalendar which can be found [here](http://microformats.org/wiki/hcalendar).  In the same manner that that specification is based on the VEVENT component in [RFC2445](http://www.ietf.org/rfc/rfc2445.txt), this specification is based on the VTODO component in the same specification.


# Format #

## Root Class Name ##
The root class name for hCalendar is "vcalendar". An element with a class name of "vcalendar" is itself called an hCalendar.

The root class name for tasks is "vtodo". An element with a class name of "vtodo" is itself called an hCalendar task.

For authoring convenience, both "vtodo" and "vcalendar" are treated as root class names for parsing purposes. If a document contains elements with class name "vtodo" but not "vcalendar", the entire document has an implied "vcalendar" context.

**vtodo** should be considered required for each event listing.

## Properties and Sub-properties ##
The properties of an hCalendar are represented by elements inside the hCalendar.  Elements with class names of the listed properties represent the values of those properties.  Some properties have sub-properties, and those are represented by elements inside the elements for properties.

## Property List ##
Any field specified in RFC 2445 section 4.6.2 may be used in the manner specified by the standard, in accordance with the usual way in which microformat properties are presented.  Below, however, are several notes about the way in which some properties are unique in their presentation.

### Status ###
The status of the to-do is specified by applying an extra class name to the element which has the class name of "vtodo".  This is one of "status-needsAction", "status-completed", "status-inProcess", or "status-cancelled".

### Due / Completed / Last Modified ###
The due date, last modified date, and completed date of a task are presented using either the [date-design-pattern](http://microformats.org/wiki/date-design-pattern) or the [datetime-design-pattern](http://microformats.org/wiki/datetime-design-pattern).

### Sub-tasks ###
While RFC 2445 does not support nesting of tasks, Google Tasks does.  In order to maximize the amount of information gotten out of the HTML export, child tasks are represented by elements with the "vtodo" class nested inside other elements with that class.  If the html file is being parsed in order to insert the data into a format which does not support nested tasks, each child task should be parsed as a separate root-level entity which is a sibling to the element which would normally be its parent.  If, however, the format being parsed into supports nested tasks, then all the children of a task will be contained in child elements with the "vtodo" class name.