# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 by the Free Software Foundation, Inc.
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


from hyperkitty import tasks
from hyperkitty.models.email import Email
from hyperkitty.models.thread import Thread
from hyperkitty.tests.utils import TestCase


class TaskTestCase(TestCase):

    def test_rebuild_thread_cache_new_email_no_thread(self):
        try:
            tasks.rebuild_thread_cache_new_email(42)
        except Thread.DoesNotExist:
            self.fail("No protection when the thread is deleted")

    def test_compute_thread_positions_no_thread(self):
        try:
            tasks.compute_thread_positions(42)
        except Thread.DoesNotExist:
            self.fail("No protection when the thread is deleted")

    def test_check_orphans_no_email(self):
        try:
            tasks.check_orphans(42)
        except Email.DoesNotExist:
            self.fail("No protection when the email is deleted")
