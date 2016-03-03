# -*- coding: utf-8 -*-
# Copyright (C) 2014-2015 by the Free Software Foundation, Inc.
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

# pylint: disable=no-init,unnecessary-lambda,unused-argument

from __future__ import absolute_import, unicode_literals, print_function

from django.conf import settings
from django.contrib import admin
from django.db import models
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver

from hyperkitty.lib.cache import cache


class Vote(models.Model):
    """
    A User's vote on a message
    """
    email = models.ForeignKey("Email", related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="votes")
    value = models.SmallIntegerField(db_index=True)

    class Meta:
        unique_together = ("email", "user")

admin.site.register(Vote)

@receiver([pre_save, pre_delete], sender=Vote)
def Vote_clean_cache(sender, **kwargs):
    """Delete cached vote values for Email and Thread instance"""
    vote = kwargs["instance"]
    cache.delete("Thread:%s:votes" % vote.email.thread_id)
    # re-populate the cache?
    cache.delete("Email:%s:votes" % vote.email_id)

