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

"""Represents the App Engine model of Google Tasks data in the datastore."""

from oauth2client import appengine

from google.appengine.ext import db


class Credentials(db.Model):
  """Represents the credentials of a particular user."""
  credentials = appengine.CredentialsProperty()


class Snapshot(db.Model):
  """The datastore entity for a Snapshot of a user's data."""
  user = db.UserProperty()
  type = db.StringProperty(choices=("import", "export"))
  timestamp = db.DateTimeProperty(auto_now_add=True)
  status = db.StringProperty(choices=("building", "completed", "error"))
  errorMessage = db.StringProperty()


class TaskList(db.Model):
  """The datastore entity for a list of tasks."""

  id = db.StringProperty()
  title = db.StringProperty()  #CATEGORIES/Categories
  selfLink = db.LinkProperty()


class Task(db.Model):
  """The datastore entity for a single task."""

  parent_entity = db.ReferenceProperty(TaskList, collection_name="tasks")
  id = db.StringProperty()  #UID
  selfLink = db.LinkProperty()
  title = db.StringProperty()  #SUMMARY/Subject
  notes = db.TextProperty()  #DESCRIPTION/Notes
  parent_ = db.SelfReferenceProperty(collection_name="children")
  position = db.StringProperty()
  updated = db.DateTimeProperty()  #LAST-MODIFIED
  due = db.DateProperty()  #DUE/Due Date
  hidden = db.BooleanProperty()
  status = db.StringProperty(choices=("completed",
                                      "needsAction"))  #STATUS/Status
  deleted = db.BooleanProperty()
  completed = db.DateTimeProperty()  #COMPLETED/Date Completed

child_mapping = {}
many_many_mapping = {}
