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

"""Generic Parser for Apiary API data.

This module contains code to take an arbitrary type of python data from an
Apiary API and convert it into entities in the datastore.
"""

__author__ = "dwightguth@google.com (Dwight Guth)"

import datetime
import logging
from google.appengine.api import urlfetch
from google.appengine.ext import db

import properties


class Parser(object):
  """Parses API data into App Engine datastore entities."""

  _EXCLUDED_FIELDS = ("kind", "etag")
  _RESERVED_WORDS = ("parent")

  def __init__(self, entity_to_parse, parent_entity, snapshot, method, model,
               date_type="friendly", index=False, **args):
    """Creates a new Parser object.

    Args:
      entity_to_parse: the subclass of db.Model to be created.
      parent_entity: the entity to set as parent of the created entities,
        or None if there is no parent.
      snapshot: the entity representing the snapshot this data is for.
      method: the method which is called to invoke the API.
      model: a module containing the many_many_mapping and child_mapping
        dictionaries necessary for parsing.
      date_type: "friendly" for strings of the format "%Y-%m-%dT%H:%M:%S",
        "timestamp" for unix timestamps with milliseconds.  Default is
        "friendly".
      index: False for token-based paging, True for index-based paging.  Default
        is False.
      args: keyword parameters to pass to the method that invokes the API.
    """
    self.entity_to_parse = entity_to_parse
    self.parent_entity = parent_entity
    self.snapshot = snapshot
    self.method = method
    self.model = model
    self.date_type = date_type
    self.index = index
    self.args = args

  def ParseAndStore(self, api_data):
    """Parses the provided data and stores the resulting entities.

    This method automatically pages through all results by reinvoking
    the API on each successive page.

    Args:
      api_data: a Python dict or list returned by the Apiary API.

    Returns:
      The list of entities created by parsing api_data.
    """
    if ("items" not in api_data and "entry" not in api_data and not
        isinstance(api_data, list)):
      # top level is a record itself
      return self.ParseItem(api_data, self.entity_to_parse, self.parent_entity)

    if self.index:
      return self.ParseIndexPaging(api_data)
    else:
      return self.ParseTokenPaging(api_data)

  def ParseTokenPaging(self, api_data):
    """Parses the provided data and stores the resulting entities.

    This method automatically uses token-based paging to page through all the
    results by reinvoking the API on each successive page.

    Args:
      api_data: a Python dict returned by the Apairy API.

    Returns:
      The list of entities created by parsing api_data.
    """
    results = []
    while "nextPageToken" in api_data:
      results += self.ParsePage(api_data)
      args = self.args.copy()
      args["pageToken"] = api_data["nextPageToken"]
      api_data = self.method(**args).execute()
    results += self.ParsePage(api_data)
    return results

  def ParseIndexPaging(self, api_data):
    """Parses the provided data and stores the resulting entities.

    This method automatically uses index-based paging to page through all the
    results by reinvoking the API on each successive page.

    Args:
      api_data: a Python dict returned by the Apairy API.

    Returns:
      The list of entities created by parsing api_data.
    """
    results = []
    start_index = 0
    while api_data:
      next_page = self.ParsePage(api_data)
      results += next_page
      start_index += len(next_page)
      args = self.args.copy()
      args["start_index"] = start_index
      api_data = self.method(**args).execute()
    return results

  def ParsePage(self, api_data):
    """Parses a single page of API data and stores the resulting entities.

    Args:
      api_data: a Python dict returned by the Apiary API.

    Returns:
      The list of entities created from that page of data.
    """
    page = []
    if "items" in api_data:
      l = api_data["items"]
    elif "entry" in api_data:
      l = api_data["entry"]
    elif isinstance(api_data, list):
      l = api_data
    for item in l:
      page.append(self.ParseItem(item, self.entity_to_parse,
                                 self.parent_entity))
    return page

  def ParseItem(self, item, entity_to_parse, parent_entity):
    """Parses a single item of API data and stores the resulting entity.

    Args:
      item: a Python dict representing a single item of data.
      entity_to_parse: the type of entity being created.
      parent_entity: the value to set the entity's parent_entity property to.

    Raises:
      ValueError: if an unknown property is found in the results.

    Returns:
      The entity created by parsing item.
    """
    if "id" in item:
      model_obj = entity_to_parse(parent=self.snapshot,
                                  key_name=str(item["id"]))
    else:
      logging.warning("no id: %s" % item)
      model_obj = entity_to_parse(parent=self.snapshot)
    model_obj.put()
    if parent_entity:
      model_obj.parent_entity = parent_entity
    props = model_obj.properties()
    for key, value in item.items():
      if key not in Parser._EXCLUDED_FIELDS:
        prop_name = Parser.ApiToModel(key)

        if (entity_to_parse, key) in self.model.child_mapping:
          for item in value:
            self.ParseItem(item, self.model.child_mapping[entity_to_parse, key],
                           model_obj)
        elif (isinstance(props[prop_name], db.StringProperty) or
              isinstance(props[prop_name], db.TextProperty) or
              isinstance(props[prop_name], db.BooleanProperty) or
              isinstance(props[prop_name], db.IntegerProperty)):
          setattr(model_obj, prop_name, value)
        elif isinstance(props[prop_name], db.FloatProperty):
          setattr(model_obj, prop_name, float(value))
        elif isinstance(props[prop_name], db.LinkProperty):
          link = db.Link(value)
          setattr(model_obj, prop_name, link)
        elif isinstance(props[prop_name], db.PhoneNumberProperty):
          pn = db.PhoneNumber(value)
          setattr(model_obj, prop_name, pn)
        elif isinstance(props[prop_name], db.BlobProperty):
          blob = db.Blob(urlfetch.fetch(value).content)
          setattr(model_obj, prop_name, blob)
        elif isinstance(props[prop_name], db.DateProperty):
          # The elif clause for DateProperty must come ABOVE the elif clause for
          # DateTimeProperty because DateProperty is a subclass of
          # DateTimeProperty. If we ever add a TimeProperty we will need it
          # to be above DateTimeProperty as well.
          d = datetime.datetime.strptime(value, "%Y-%m-%dT00:00:00.000Z").date()
          setattr(model_obj, prop_name, d)
        elif isinstance(props[prop_name], db.DateTimeProperty):
          if self.date_type == "friendly":
            part1, part2 = value.split(".")
            dt = datetime.datetime.strptime(part1, "%Y-%m-%dT%H:%M:%S")
            dt = dt.replace(microsecond=int(part2[0:3])*1000)
          elif self.date_type == "timestamp":
            part1 = value[:-3]
            part2 = value[-3:]
            dt = datetime.datetime.fromtimestamp(long(part1))
            dt = dt.replace(microsecond=int(part2)*1000)
          else:
            raise ValueError("Not a valid date_type: %s" % self.date_type)
          setattr(model_obj, prop_name, dt)
        elif isinstance(props[prop_name], db.ReferenceProperty):
          key_obj = db.Key.from_path(
              self.snapshot.kind(), self.snapshot.key().id(),
              props[prop_name].reference_class.kind(), value)
          setattr(model_obj, prop_name, key_obj)
        elif isinstance(props[prop_name], db.ListProperty):
          if props[prop_name].item_type == db.Key:
            key_objs = []
            for key_obj in value:
              key_objs.append(
                  db.Key.from_path(
                      self.snapshot.kind(), self.snapshot.key().id(),
                      self.model.many_many_mapping[entity_to_parse,
                                                   key].__name__, key_obj))
            setattr(model_obj, prop_name, key_objs)
          else:
            setattr(model_obj, prop_name, value)
        elif isinstance(props[prop_name], properties.TimeDeltaProperty):
          milliseconds = long(value)
          dt = datetime.timedelta(seconds=milliseconds / 1000,
                                  milliseconds=milliseconds % 1000)
          setattr(model_obj, prop_name, dt)
        elif isinstance(props[prop_name], properties.DictProperty):
          setattr(model_obj, prop_name, value)
        else:
          raise ValueError("Could not parse property %s.\n"
                           "Value: %s" % (key, value))

    model_obj.put()
    return model_obj

  @staticmethod
  def ApiToModel(key):
    """Converts an API property name to a Model property name.

    Args:
      key: the name of the property in the API results.

    Returns:
      The name of the same property in the datastore model.
    """
    if key in Parser._RESERVED_WORDS:
      return key + "_"
    return key
