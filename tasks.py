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

"""Main web application handler for Google Tasks Porter."""

__author__ = "dwightguth@google.com (Dwight Guth)"

import logging
import os
import pickle
import urllib

from apiclient.oauth2client import appengine
from apiclient.oauth2client import client

from google.appengine.api import mail
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util


import model
import settings


def _RedirectForOAuth(self, user):
  """Redirects the webapp response to authenticate the user with OAuth2."""
  flow = client.OAuth2WebServerFlow(
      client_id=settings.CLIENT_ID + ".apps.googleusercontent.com",
      client_secret=settings.CLIENT_SECRET,
      scope="https://www.googleapis.com/auth/tasks",
      user_agent="task-porter/1.0",
      xoauth_displayname="Google Tasks Porter",
      state=self.request.path_qs)

  callback = self.request.relative_url("/oauth2callback")
  authorize_url = flow.step1_get_authorize_url(callback)
  memcache.set(user.user_id(), pickle.dumps(flow))
  self.redirect(authorize_url)


def _GetCredentials():
  user = users.get_current_user()
  credentials = appengine.StorageByKeyName(
      model.Credentials, user.user_id(), "credentials").get()
  return user, credentials


class MainHandler(webapp.RequestHandler):
  """Handler for /."""

  def get(self):
    """Handles GET requests for /."""
    credentials = _GetCredentials()[1]
    path = os.path.join(os.path.dirname(__file__), "index.html")
    if not credentials or credentials.invalid:
      template_values = {"is_authorized": False,
                         "logout_url": users.create_logout_url("/")}
      self.response.out.write(template.render(path, template_values))
    else:
      template_values = {"is_authorized": True,
                         "logout_url": users.create_logout_url("/")}
      self.response.out.write(template.render(path, template_values))


class AuthRedirectHandler(webapp.RequestHandler):
  """Handler for /auth."""

  def get(self):
    """Handles GET requests for /auth."""
    user, credentials = _GetCredentials()

    if not credentials or credentials.invalid:
      _RedirectForOAuth(self, user)
    else:
      self.redirect("/")


class ListHandler(webapp.RequestHandler):
  """Handler for /snapshots."""

  def get(self):
    """Handles GET requests for /snapshots."""
    user, credentials = _GetCredentials()

    if not credentials or credentials.invalid:
      _RedirectForOAuth(self, user)
    else:
      path = os.path.join(os.path.dirname(__file__), "snapshots.html")
      snapshots = model.Snapshot.gql("WHERE user = :user and type = 'export'",
                                     user=user)

      counts = []
      refresh = False

      for snapshot in snapshots:
        tasklists = model.TaskList.gql("WHERE ANCESTOR IS :id",
                                       id=snapshot.key())
        task_count = 0
        tasklist_count = 0
        if snapshot.status == "building":
          refresh = True
        for tasklist in tasklists:
          task_count += tasklist.tasks.count()
          tasklist_count += 1

        counts.append((snapshot, task_count, tasklist_count))

      template_values = {"snapshots": counts,
                         "msg": self.request.get("msg"),
                         "refresh": refresh,
                         "logout_url": users.create_logout_url("/snapshots")}
      self.response.out.write(template.render(path, template_values))


class SnapshotHandler(webapp.RequestHandler):
  """Handler for /snapshot."""

  def get(self):
    """Handles GET requests for /snapshot."""
    user, credentials = _GetCredentials()

    if not credentials or credentials.invalid:
      _RedirectForOAuth(self, user)
    else:
      # need to create snapshot outside of task queue because there is no easy
      # way to pass user identity to a task other than through a datastore
      # entity.
      snapshot = model.Snapshot()
      snapshot.type = "export"
      snapshot.user = users.get_current_user()
      snapshot.status = "building"
      snapshot.put()

      taskqueue.add(url="/worker/snapshot",
                    params={"id": snapshot.key().id()})
      self.redirect("/snapshots")


class DeleteHandler(webapp.RequestHandler):
  """Handler for /delete."""

  def get(self):
    """Handles GET requests for /delete."""
    user, credentials = _GetCredentials()

    if self.request.get("import"):
      url = "/import"
    else:
      url = "/snapshots"

    if not credentials or credentials.invalid:
      self.redirect(url)
    else:
      if not self.request.get("id"):
        self.redirect(url + "?msg=NO_ID_DELETE")
        return

      snapshot = model.Snapshot.gql("WHERE user = :user "
                                    "AND __key__ = KEY('Snapshot', :key)",
                                    user=user,
                                    key=int(self.request.get("id"))).get()

      if snapshot is None:
        self.redirect(url + "?msg=INVALID_SNAPSHOT")
        return

      if snapshot.status == "building":
        # can't delete until snapshot is done
        self.redirect(url + "?msg=DELETE_BUILDING")
        return

      taskqueue.add(url="/worker/delete",
                    params={"id": snapshot.key().id()})
      self.redirect(url + "?msg=SNAPSHOT_DELETING")


class DownloadHandler(webapp.RequestHandler):
  """Handler for /download."""

  def get(self):
    """Handles GET requests for /download.

    This handler takes the following query parameters:
      id: the internal id serving as key for the snapshot to download.
      format: either "ics", "csv", or "html" depending on what format is selected
      to download.
    """
    user, credentials = _GetCredentials()

    if not credentials or credentials.invalid:
      self.redirect("/snapshots")
    else:
      if not self.request.get("id"):
        self.redirect("/snapshots?msg=NO_ID_EXPORT")
        return
      snapshot = model.Snapshot.gql("WHERE user = :user "
                                    "AND __key__ = KEY('Snapshot', :key)",
                                    user=user,
                                    key=int(self.request.get("id"))).get()
      tasklist_entities = model.TaskList.gql("WHERE ANCESTOR IS :id",
                                             id=snapshot.key())
      template_values = {"tasklists": list(tasklist_entities),
                         "now": snapshot.timestamp}

      if self.request.get("format") == "ics":
        self.WriteIcsTemplate(template_values)
      elif self.request.get("format") == "csv":
        self.WriteCsvTemplate(template_values)
      elif self.request.get("format") == "html":
        self.WriteHtmlTemplate(template_values)

  def WriteIcsTemplate(self, template_values):
    self.response.headers["Content-Type"] = "text/calendar"
    self.response.headers.add_header(
        "Content-Disposition", "attachment; filename=tasks_%s.ics" %
        template_values["now"].strftime("%m-%d-%Y"))

    path = os.path.join(os.path.dirname(__file__), "todo.ics")
    self.response.out.write(template.render(path, template_values))

  def WriteCsvTemplate(self, template_values):
    self.response.headers["Content-Type"] = "text/csv"
    self.response.headers.add_header(
        "Content-Disposition", "attachment; filename=tasks_%s.csv" %
        template_values["now"].strftime("%m-%d-%Y"))

    path = os.path.join(os.path.dirname(__file__), "todo.csv")
    self.response.out.write(template.render(path, template_values))

  def WriteHtmlTemplate(self, template_values):
    path = os.path.join(os.path.dirname(__file__), "todo.html")
    self.response.out.write(template.render(path, template_values))


class ImportHandler(webapp.RequestHandler):
  """Handler for /import."""

  def get(self):
    """Handles GET requests for /import."""
    user, credentials = _GetCredentials()

    if not credentials or credentials.invalid:
      _RedirectForOAuth(self, user)
    else:
      path = os.path.join(os.path.dirname(__file__), "import.html")
      snapshots = model.Snapshot.gql("WHERE user = :user "
                                     "and type = 'import'",
                                     user=user)

      titles = []
      refresh = False
      for snapshot in snapshots:
        if snapshot.status == "completed":
          title = model.TaskList.gql("WHERE ANCESTOR IS :id",
                                     id=snapshot.key()).get().title
        else:
          title = ""
          if snapshot.status == "building":
            refresh = True
        titles.append((snapshot, title))

      template_values = {"snapshots": titles,
                         "msg": self.request.get("msg"),
                         "refresh": refresh,
                         "logout_url": users.create_logout_url("/import")}
      self.response.out.write(template.render(path, template_values))

  def post(self):
    """Handles POST requests for /import.

    This handler takes the following query parameters:
      name: The name of the tasklist to create and put the imported tasks into.
      format: either "ics" or "csv" depending on whta format to import from.

    The body of the POST request requires the following parameters:
      file: a file reference containing either the ics or csv file to import.
    """
    if (not self.request.get("file") or
        not self.request.get("name") or
        not self.request.get("format")):
      self.redirect("/import?msg=REQUIRED_FIELD")
      return
    snapshot = model.Snapshot()
    snapshot.type = "import"
    snapshot.user = users.get_current_user()
    snapshot.status = "building"
    snapshot.put()

    logging.info(snapshot.key().id())

    try:
      taskqueue.add(url="/worker/import",
                    params={"file": self.request.get("file"),
                            "name": self.request.get("name"),
                            "format": self.request.get("format"),
                            "id": snapshot.key().id()})
    except taskqueue.TaskTooLargeError, e:
      logging.info(e, exc_info=True)
      self.redirect("/import?msg=FILE_TOO_LARGE")
      return

    self.redirect("/import")


class SendMailHandler(webapp.RequestHandler):
  """Handler for /sendmail."""

  def get(self):
    """Handles GET requests for /sendmail."""
    user, credentials = _GetCredentials()
    if not credentials or credentials.invalid:
      _RedirectForOAuth(self, user)
    else:
      path = os.path.join(os.path.dirname(__file__), "sendmail.html")
      template_values = {"id": self.request.get("id"),
                         "msg": self.request.get("msg"),
                         "logout_url": users.create_logout_url("/sendmail")}

      self.response.out.write(template.render(path, template_values))

  def post(self):
    """Handles POST requests for /sendmail.

    This handler takes the following query parameters:
      id: the internal id serving as key for the snapshot to mail.
      email: the Remember The Milk import email address to send to.
      subject: the name of the task list to create.
    """
    user, credentials = _GetCredentials()
    if not credentials or credentials.invalid:
      _RedirectForOAuth(self, user)
    else:
      if not self.request.get("id"):
        self.redirect("/snapshots?msg=NO_ID_EXPORT")
        return
      if (not self.request.get("email") or
          not self.request.get("subject")):
        self.redirect("/sendmail?id=%s&msg=REQUIRED_FIELD" %
                      urllib.quote_plus(self.request.get("id")))
        return

      snapshot = model.Snapshot.gql("WHERE user = :user "
                                    "AND __key__ = KEY('Snapshot', :key)",
                                    user=user,
                                    key=int(self.request.get("id"))).get()
      tasklist_entities = model.TaskList.gql("WHERE ANCESTOR IS :id",
                                             id=snapshot.key())

      template_values = {"tasklists": list(tasklist_entities),
                         "now": snapshot.timestamp}

      email_body = self.GenerateEmailBody(template_values)

      mail.send_mail(sender="noreply@google.com",
                     to=self.request.get("email"),
                     subject=self.request.get("subject"),
                     body=email_body)

      self.redirect("/snapshots")

  def GenerateEmailBody(self, template_values):
    path = os.path.join(os.path.dirname(__file__), "todo.txt")
    return template.render(path, template_values)


class OAuthHandler(webapp.RequestHandler):
  """Handler for /oauth2callback."""

  def get(self):
    """Handles GET requests for /oauth2callback."""
    if not self.request.get("code"):
      self.redirect("/")
      return
    user = users.get_current_user()
    flow = pickle.loads(memcache.get(user.user_id()))
    if flow:
      credentials = flow.step2_exchange(self.request.params)
      appengine.StorageByKeyName(
          model.Credentials, user.user_id(), "credentials").put(credentials)
      self.redirect(self.request.get("state"))


def main():
  template.register_template_library("common.customdjango")

  application = webapp.WSGIApplication(
      [
          ("/", MainHandler),
          ("/auth", AuthRedirectHandler),
          ("/delete", DeleteHandler),
          ("/download", DownloadHandler),
          ("/import", ImportHandler),
          ("/oauth2callback", OAuthHandler),
          ("/sendmail", SendMailHandler),
          ("/snapshot", SnapshotHandler),
          ("/snapshots", ListHandler)
      ])
  util.run_wsgi_app(application)


if __name__ == "__main__":
  main()
