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

from urllib2 import HTTPError


from django.conf import settings
from django.contrib import admin
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from mailmanclient import MailmanConnectionError
import pytz

from hyperkitty.lib.cache import cache
from hyperkitty.lib.mailman import get_mailman_client
from .email import Email


import logging
logger = logging.getLogger(__name__)



class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                related_name="hyperkitty_profile")

    karma = models.IntegerField(default=1)
    TIMEZONES = sorted([ (tz, tz) for tz in pytz.common_timezones ])
    timezone = models.CharField(max_length=100, choices=TIMEZONES, default=u"")

    def __unicode__(self):
        return u'%s' % (unicode(self.user))

    @property
    def emails(self):
        return Email.objects.filter(
            sender__address__in=self.addresses).order_by("date")

    @property
    def addresses(self):
        addresses = set([self.user.email,])
        mm_user = self.get_mailman_user()
        if mm_user:
            # TODO: caching?
            # (mailman client returns str, must convert to deduplicate)
            addresses.update([unicode(a) for a in mm_user.addresses])
        addresses = list(addresses)
        addresses.sort()
        return addresses

    def get_votes_in_list(self, list_name):
        # TODO: Caching ?
        votes = self.user.votes.filter(email__mailinglist__name=list_name)
        likes = votes.filter(value=1).count()
        dislikes = votes.filter(value=-1).count()
        return likes, dislikes

    def get_mailman_user(self):
        # Only cache the user_id, not the whole user instance, because
        # mailmanclient is not pickle-safe
        cache_key = "User:%s:mailman_user_id" % self.id
        user_id = cache.get(cache_key)
        try:
            mm_client = get_mailman_client()
            if user_id is None:
                try:
                    mm_user = mm_client.get_user(self.user.email)
                except HTTPError as e:
                    if e.code != 404:
                        raise # will be caught down there
                    mm_user = mm_client.create_user(
                        self.user.email, self.user.get_full_name())
                    logger.info("Created Mailman user for %s (%s)",
                                self.user.username, self.user.email)
                cache.set(cache_key, mm_user.user_id, None)
                return mm_user
            else:
                return mm_client.get_user(user_id)
        except (HTTPError, MailmanConnectionError) as e:
            logger.warning(
                "Error getting or creating the Mailman user of %s (%s): %s",
                self.user.username, self.user.email, e)
            return None

    def get_mailman_user_id(self):
        # TODO: Optimization: look in the cache first, if not found call
        # get_mailman_user() as before
        mm_user = self.get_mailman_user()
        if mm_user is None:
            return None
        return unicode(mm_user.user_id)

    def get_subscriptions(self):
        def _get_value():
            mm_user = self.get_mailman_user()
            if mm_user is None:
                return {}
            subscriptions = dict([
                (member.list_id, member.address)
                for member in mm_user.subscriptions
                ])
            return subscriptions
        # TODO: how should this be invalidated? Subscribe to a signal in
        # mailman when a new subscription occurs? Or store in the session?
        return cache.get_or_set(
            "User:%s:subscriptions" % self.id,
            _get_value, 60, version=2) # 1 minute
        # TODO: increase the cache duration when we have Mailman signals

    def get_first_post(self, mlist):
        return self.emails.filter(mailinglist=mlist
            ).order_by("archived_date").first()

admin.site.register(Profile)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, **kwargs):
    user = kwargs["instance"]
    if not Profile.objects.filter(user=user).exists():
        Profile.objects.create(user=user)

