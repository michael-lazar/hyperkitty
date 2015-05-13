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

# pylint: disable=unnecessary-lambda

from __future__ import absolute_import, print_function, unicode_literals

from mock import Mock
from django.core.urlresolvers import reverse
from django.contrib.auth.models import AnonymousUser, User
from django.test.client import RequestFactory
from django.test.utils import override_settings

from hyperkitty.middleware import SSLRedirect
from hyperkitty.tests.utils import TestCase


class SSLRedirectTestCase(TestCase):


    def setUp(self):
        self.mw = SSLRedirect()
        self.rf = RequestFactory()

    def test_is_secure_false(self):
        request = self.rf.get("/")
        self.assertFalse(self.mw._is_secure(request))

    def test_is_secure_headers(self):
        request = self.rf.get("/", HTTP_X_FORWARDED_SSL="on")
        self.assertTrue(self.mw._is_secure(request))

    def test_redirect_https(self):
        request = self.rf.get("/")
        result = self.mw._redirect(request, True)
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result.url.startswith("https://"))

    def test_redirect_http(self):
        request = self.rf.get("/")
        result = self.mw._redirect(request, False)
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result.url.startswith("http://"))

    @override_settings(USE_SSL=True)
    def test_login_redirect(self):
        # Requests to the login page must be redirected to HTTPS
        request = self.rf.get("/")
        request.user = AnonymousUser()
        result = self.mw.process_view(request, None, [], {"SSL": True})
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result.url.startswith("https://"))

    @override_settings(USE_SSL=True)
    def test_login_already_https(self):
        # Requests to the login page must not be redirected if they already are
        # in HTTPS
        request = self.rf.get("/", HTTP_X_FORWARDED_SSL="on")
        request.user = AnonymousUser()
        result = self.mw.process_view(request, None, [], {"SSL": True})
        self.assertIsNone(result)

    @override_settings(USE_SSL=True)
    def test_noredirect(self):
        # Requests to normal pages must not be redirected
        request = self.rf.get("/")
        request.user = AnonymousUser()
        result = self.mw.process_view(request, None, [], {})
        self.assertIsNone(result)

    @override_settings(USE_SSL=True)
    def test_redirect_authenticated_http(self):
        # Requests in HTTP with authenticated users must be redirected to HTTPS
        request = self.rf.get("/")
        request.user = User.objects.create_user(
            'testuser', 'test@example.com', 'testPass')
        result = self.mw.process_view(request, None, [], {})
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result.url.startswith("https://"))

    @override_settings(USE_SSL=True)
    def test_redirect_authenticated_https(self):
        # Requests in HTTPS with authenticated users must stay in HTTPS
        request = self.rf.get("/", HTTP_X_FORWARDED_SSL="on")
        request.user = User.objects.create_user(
            'testuser', 'test@example.com', 'testPass')
        result = self.mw.process_view(request, None, [], {})
        self.assertIsNone(result)
