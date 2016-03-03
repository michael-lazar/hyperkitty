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
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.contrib import admin
from django.dispatch import receiver
from django.utils.timezone import now, utc

from hyperkitty.lib.cache import cache
from .common import get_votes
from .sender import Sender


import logging
logger = logging.getLogger(__name__)


class Thread(models.Model):
    """
    A thread of archived email, from a mailing-list. It is identified by both
    the list name and the thread id.
    """
    mailinglist = models.ForeignKey("MailingList", related_name="threads")
    thread_id = models.CharField(max_length=255, db_index=True)
    date_active = models.DateTimeField(db_index=True, default=now)
    category = models.ForeignKey("ThreadCategory", related_name="threads", null=True)
    starting_email = models.OneToOneField("Email",
        related_name="started_thread", null=True)

    class Meta:
        unique_together = ("mailinglist", "thread_id")

    @property
    def participants(self):
        """Set of email senders in this thread"""
        return Sender.objects.filter(emails__thread_id=self.id).distinct()

    @property
    def participants_count(self):
        return cache.get_or_set(
            "Thread:%s:participants_count" % self.id,
            lambda: self.participants.count(),
            None)

    def replies_after(self, date):
        return self.emails.filter(date__gt=date)

    #def _get_category(self):
    #    if not self.category_id:
    #        return None
    #    return self.category_obj.name
    #def _set_category(self, name):
    #    if not name:
    #        self.category_id = None
    #        return
    #    session = object_session(self)
    #    try:
    #        category = session.query(Category).filter_by(name=name).one()
    #    except NoResultFound:
    #        category = Category(name=name)
    #        session.add(category)
    #    self.category_id = category.id
    #category = property(_get_category, _set_category)

    @property
    def emails_count(self):
        return cache.get_or_set(
            "Thread:%s:emails_count" % self.id,
            lambda: self.emails.count(),
            None)

    @property
    def subject(self):
        return cache.get_or_set(
            "Thread:%s:subject" % self.id,
            lambda: self.starting_email.subject,
            None)

    def get_votes(self):
        return get_votes(self)

    @property
    def prev_thread(self): # TODO: Make it a relationship
        return Thread.objects.filter(
                mailinglist=self.mailinglist,
                date_active__lt=self.date_active
            ).order_by("-date_active").first()

    @property
    def next_thread(self): # TODO: Make it a relationship
        return Thread.objects.filter(
                mailinglist=self.mailinglist,
                date_active__gt=self.date_active
            ).order_by("date_active").first()

    def is_unread_by(self, user):
        if not user.is_authenticated():
            return False
        try:
            last_view = LastView.objects.get(thread=self, user=user)
        except LastView.DoesNotExist:
            return True
        except LastView.MultipleObjectsReturned:
            last_view_duplicate, last_view = LastView.objects.filter(
                thread=self, user=user).order_by("view_date").all()
            last_view_duplicate.delete()
        return self.date_active.replace(tzinfo=utc) > last_view.view_date


#@receiver(pre_save, sender=Thread)
#def Thread_find_starting_email(sender, **kwargs):
#    """Find and set the staring email if it was not specified"""
#    instance = kwargs["instance"]
#    if instance.starting_email is not None:
#        return
#    try:
#        instance.starting_email = instance.emails.get(parent_id__isnull=True)
#    except Email.DoesNotExist:
#        instance.starting_email = instance.emails.order_by("date").first()


@receiver([post_save, post_delete], sender=Thread)
def refresh_thread_count_cache(sender, **kwargs):
    thread = kwargs["instance"]
    cache.delete("MailingList:%s:recent_threads" % thread.mailinglist_id)
    # don't warm up the cache in batch mode (mass import)
    if not getattr(settings, "HYPERKITTY_BATCH_MODE", False):
        # pylint: disable=pointless-statement
        thread.mailinglist.recent_threads


#@receiver(new_thread)
#def cache_thread_subject(sender, **kwargs):
#    thread = kwargs["instance"]
#    thread.subject



class LastView(models.Model):
    thread = models.ForeignKey("Thread", related_name="lastviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="lastviews")
    view_date = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        """Unicode representation"""
        return u"Last view of %s by %s was %s" % (
            unicode(self.thread), unicode(self.user),
            self.view_date.isoformat())

    def num_unread(self):
        if self.thread.date_active.replace(tzinfo=utc) <= self.view_date:
            return 0 # avoid the expensive query below
        else:
            return self.thread.emails.filter(date__gt=self.view_date).count()

admin.site.register(LastView)
