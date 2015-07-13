Google Tasks Porter is an App Engine application written in Python designed to use the public API for Google Tasks in order to facilitate import and export of tasks to and from other common task formats.  The supported formats are:

  * iCalendar
  * Microsoft Outlook
  * Remember the Milk
  * HTML download


Each of these formats supports a slightly different set of features and thus is capable of importing and exporting a slightly different subset of the information Google Tasks can store.

iCalendar supports the following information:
  * Due Date
  * Task Name
  * Task Description
  * Task Status: complete or incomplete
  * Date Completed
  * Task grouping by category (not supported by all programs that use iCalendar files)


Microsoft Outlook supports the following information:
  * Due Date
  * Task Name
  * Task Description
  * Task Status: complete or not started
  * Date Completed
  * Task grouping by category


Remember the Milk supports the following information:
  * Due Date
  * Task Name
  * Task grouping by category


HTML download supports the following information:
  * Due Date
  * Task Name
  * Task Description
  * Task Status: complete or incomplete
  * Date Completed
  * Task lists
  * Sub-tasks
  * Ordering of tasks


In order to use the application, a user logs in and is then presented with a list of snapshots they have taken of their Google Tasks data.  They have the option to take another snapshot at any time, and are able to download any of their previous snapshots in any of the four export formats.  They are also able to select a csv or ics file and import it into Google Tasks by specifying the name of a task list and having all tasks in that file added to that task list.