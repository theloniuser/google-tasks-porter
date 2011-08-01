#!/usr/bin/python2.5
#
# Copyright 2011 Google Inc.  All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Parser for Outlook CSV file data."""

__author__ = "dwightguth@google.com (Dwight Guth)"

import csv
import datetime
import StringIO

import model


class Parser(object):
  """Parses CSV export from Outlook into App Engine datastore entities."""

  def __init__(self, tasklist):
    """Creates a new Parser object.

    Args:
      tasklist: the tasklist to put the parsed tasks into.
    """
    self.tasklist = tasklist

  def ParseAndStore(self, csv_data):
    """Parses the provided data and stores the resulting entities.

    Args:
      csv_data: the text of a CSV file to be parsed for todo objects.

    Returns:
      The list of entities created by parsing csv_data.
    """
    csv_reader = csv.DictReader(StringIO.StringIO(csv_data))

    results = []
    for row in csv_reader:
      results.append(self.ParseItem(row))
    return results

  def ParseItem(self, item):
    """Parses a single CSV row and stores the resulting entity.

    Args:
      item: a csv row object representing an Outlook todo item.

    Returns:
      The entity created by parsing item.
    """
    task = model.Task()
    if self.tasklist:
      task.parent_entity = self.tasklist
    if item["Subject"]:
      task.title = item["Subject"]
    else:
      # we need a title so if it's not there we use the empty string
      task.title = ""
    if item["Notes"]:
      task.notes = item["Notes"]
    if item["Due Date"]:
      task.due = datetime.datetime.strptime(item["Due Date"], "%m/%d/%Y").date()
    if item["Date Completed"]:
      task.completed = datetime.datetime.strptime(item["Date Completed"],
                                                  "%m/%d/%Y")
    if item["Status"]:
      if item["Status"] == "Complete":
        task.status = "completed"
      else:
        task.status = "needsAction"
    task.put()
    return task
