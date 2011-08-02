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

"""Request Handler for Task Queue Tasks."""

__author__ = "dwightguth@google.com (Dwight Guth)"

import logging

from apiclient import discovery
from apiclient.oauth2client import appengine

from google.appengine.api import apiproxy_stub_map
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

import httplib2

from common import apiparse
from common import apiupload
import csvparse
import icalparse
import model


def urlfetch_timeout_hook(service, call, request, response):
  if call != 'Fetch':
    return  # Make the default deadline 10 seconds instead of 5.
  if not request.has_deadline():
    request.set_deadline(30.0)


class SnapshotWorker(webapp.RequestHandler):
  """Handler for /worker/snapshot."""

  def post(self):
    """Handles POST requests for /worker/snapshot."""
    snapshot = model.Snapshot.gql("WHERE __key__ = KEY('Snapshot', :key)",
                                  key=int(self.request.get("id"))).get()
    user = snapshot.user
    credentials = appengine.StorageByKeyName(
        model.Credentials, user.user_id(), "credentials").get()

    if credentials is None or credentials.invalid == True:
      snapshot.status = "error"
      snapshot.errorMessage = "Must be logged in to create snapshot."
      snapshot.put()
    else:
      try:
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = discovery.build("tasks", "v1", http)
        tasklists = service.tasklists()
        tasklists_list = tasklists.list().execute()

        parser = apiparse.Parser(model.TaskList, None, snapshot, tasklists.list,
                                 model)
        tasklist_entities = parser.ParseAndStore(tasklists_list)

        for tasklist in tasklist_entities:
          tasks = service.tasks()
          tasks_list = tasks.list(tasklist=tasklist.id,
                                  showHidden=True).execute()
          parser = apiparse.Parser(model.Task,
                                   tasklist,
                                   snapshot,
                                   tasks.list,
                                   model,
                                   tasklist=tasklist.id,
                                   showHidden=True)
          parser.ParseAndStore(tasks_list)
        snapshot.status = "completed"
        snapshot.put()
      except Exception, e:
        snapshot.status = "error"
        snapshot.errorMessage = "Snapshot creation process failed unexpectedly."
        logging.error(e, exc_info=True)
        snapshot.put()


class ImportWorker(webapp.RequestHandler):
  """Handler for /worker/import."""

  def post(self):
    """Handles POST requests for /worker/snapshot."""
    snapshot = model.Snapshot.gql("WHERE __key__ = KEY('Snapshot', :key)",
                                  key=int(self.request.get("id"))).get()
    user = snapshot.user
    credentials = appengine.StorageByKeyName(
        model.Credentials, user.user_id(), "credentials").get()

    if credentials is None or credentials.invalid == True:
      snapshot.status = "error"
      snapshot.errorMessage = "Must be logged in to create snapshot."
      snapshot.put()
    else:
      try:
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = discovery.build("tasks", "v1", http)

        tasklist = model.TaskList(parent=snapshot)
        tasklist.title = self.request.get("name")
        tasklist.put()

        if self.request.get("format") == "ics":
          try:
            parser = icalparse.Parser(tasklist)
            tasks_list = parser.ParseAndStore(self.request.get("file"))
          except Exception, e:
            snapshot.status = "error"
            snapshot.errorMessage = "The iCalendar file was malformed."
            logging.info(e, exc_info=True)
            snapshot.put()
            return
        elif self.request.get("format") == "csv":
          try:
            parser = csvparse.Parser(tasklist)
            tasks_list = parser.ParseAndStore(self.request.get("file"))
          except Exception, e:
            snapshot.status = "error"
            snapshot.errorMessage = "The CSV file was malformed."
            logging.info(e, exc_info=True)
            snapshot.put()
            return
        else:
          tasks_list = []

        tasklists = service.tasklists()
        uploader = apiupload.Uploader(tasklists.insert)
        tasklist_id = uploader.Upload([tasklist])[0]

        tasks = service.tasks()
        uploader = apiupload.Uploader(tasks.insert, tasklist=tasklist_id,
                                      previous=apiupload.PREVIOUS_ARGUMENT)
        uploader.Upload(tasks_list)
        snapshot.status = "completed"
        snapshot.put()
      except Exception, e:
        snapshot.status = "error"
        snapshot.errorMessage = "Snapshot creation process failed unexpectedly."
        logging.error(e, exc_info=True)
        snapshot.put()


def main():
  apiproxy_stub_map.apiproxy.GetPreCallHooks().Append(
      'urlfetch_timeout_hook', urlfetch_timeout_hook, 'urlfetch')
  application = webapp.WSGIApplication(
      [
          ("/worker/snapshot", SnapshotWorker),
          ("/worker/import", ImportWorker)
      ])
  util.run_wsgi_app(application)

if __name__ == "__main__":
  main()
