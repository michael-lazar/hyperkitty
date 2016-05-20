# -*- coding: utf-8 -*-
# Copyright (C) 1998-2012 by the Free Software Foundation, Inc.
#
# This file is part of HyperKitty.
#
# HyperKitty is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# HyperKitty is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# HyperKitty.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Aurelien Bompard <abompard@fedoraproject.org>
#


from __future__ import absolute_import, print_function, unicode_literals

import json
from email.message import Message

from django.core.urlresolvers import reverse

from hyperkitty.models import MailingList, ArchivePolicy
from hyperkitty.lib.incoming import add_to_list
from hyperkitty.tests.utils import TestCase


class PrivateListTestCase(TestCase):

    def setUp(self):
        MailingList.objects.create(
            name="list@example.com", subject_prefix="[example] ",
            archive_policy=ArchivePolicy.private.value)
        msg = Message()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msgid>"
        msg["Subject"] = "Dummy message"
        msg.set_payload("Dummy message")
        msg["Message-ID-Hash"] = self.msgid = add_to_list("list@example.com", msg)

    def _do_test(self, sort_mode):
        response = self.client.get(reverse("hk_root"), {"sort": sort_mode})
        self.assertNotContains(response, "list@example.com", status_code=200)

    def test_sort_active(self):
        self._do_test("active")
    def test_sort_popular(self):
        self._do_test("popular")

class FindTestCase(TestCase):

    def setUp(self):
        MailingList.objects.create(name="list-one@example.com")
        MailingList.objects.create(name="list-two@example.com",
                                   display_name="List Two")

    def test_find(self):
        response = self.client.get("%s?term=one" % reverse("hk_find_list"))
        self.assertEqual(
            json.loads(response.content),
            [{'label': 'list-one@example.com', 'value': 'list-one@example.com'}]
            )

    def test_name(self):
        response = self.client.get("%s?term=example" % reverse("hk_find_list"))
        self.assertEqual(
            json.loads(response.content),
            [{'label': 'list-one@example.com', 'value': 'list-one@example.com'},
             {'label': 'List Two', 'value': 'list-two@example.com'}]
            )

    def test_display_name(self):
        ml = MailingList.objects.get(name="list-one@example.com")
        ml.display_name = "Test Value"
        ml.save()
        response = self.client.get("%s?term=value" % reverse("hk_find_list"))
        self.assertEqual(
            json.loads(response.content),
            [{'label': 'Test Value', 'value': 'list-one@example.com'}]
            )
