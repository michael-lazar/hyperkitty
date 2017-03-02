# -*- coding: utf-8 -*-
#
# Copyright (C) 2017-2017 by the Free Software Foundation, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301,
# USA.

"""
Definition of async tasks using Celery.

Author: Aurelien Bompard <abompard@fedoraproject.org>
"""

from __future__ import absolute_import, unicode_literals

import errno
import importlib
import logging
import os.path
from binascii import crc32
from functools import wraps
from tempfile import gettempdir

from django.conf import settings
from django.core.cache.utils import make_template_fragment_key
from django_mailman3.lib.cache import cache
from django_q.conf import Conf
from django_q.tasks import Async
from lockfile import AlreadyLocked, LockFailed
from lockfile.pidlockfile import PIDLockFile
from mailmanclient import MailmanConnectionError

from hyperkitty.lib.analysis import compute_thread_order_and_depth
from hyperkitty.models.email import Email
from hyperkitty.models.mailinglist import MailingList
from hyperkitty.models.sender import Sender
from hyperkitty.models.thread import Thread
from hyperkitty.search_indexes import update_index

log = logging.getLogger(__name__)


def unlock_and_call(func, cache_key, *args, **kwargs):
    """
    This method is a wrapper that will actually be called by the workers.
    """
    # Drop the lock before run instead of after because the DB data may
    # have changed during the task's runtime.
    cache.delete(cache_key)
    if not callable(func):
        module, func_name = func.rsplit('.', 1)
        m = importlib.import_module(module)
        func = getattr(m, func_name)
    return func(*args, **kwargs)


class SingletonAsync(Async):
    """A singleton task implementation.

    A singleton task does not enqueue the function if there's already one in
    the queue.

    The cache is used for locking: the lock is acquired when the run() method
    is executed. If there's already an identical task in the queue, it will
    return this task's id.
    """

    LOCK_EXPIRE = 60 * 10  # Lock expires in 10 minutes

    def __init__(self, func, *args, **kwargs):
        func_name = func.__name__ if callable(func) else func
        # No space allowed in memcached keys. Use CRC32 on the arguments
        # to have a fast and sufficiently unique way to identify tasks.
        self._cache_key = "task:status:%s:%s" % (
            func_name, crc32(repr(args) + repr(kwargs)) & 0xffffffff)
        super(SingletonAsync, self).__init__(
            unlock_and_call, func, self._cache_key, *args, **kwargs)

    # def _report_start(self, func):
    #     @wraps(func)
    #     def wrapper(*args, **kwargs):
    #         # Drop the lock before run instead of after because the DB data
    #         # may have changed during the task's runtime.
    #         cache.delete(self._lock_cache_key)
    #         return func(*args, **kwargs)
    #     return wrapper

    def run(self):
        pending_id = cache.get(self._cache_key)
        if pending_id is not None:
            self.id = pending_id
            self.started = True
            return pending_id
        # cache.set(self._lock_cache_key, "enqueuing...", self.LOCK_EXPIRE)
        super(SingletonAsync, self).run()
        cache.set(self._cache_key, self.id, self.LOCK_EXPIRE)
        return self.id

    @classmethod
    def task(cls, func):
        """Turn a function into an async task.

        Adds a ``delay()`` method to the decorated function which will run it
        asynchronously with the provided arguments.  The arguments accepted by
        the :py:class:`Async` class are accepted here too.
        """
        def delay(*args, **kwargs):
            async_class = cls
            if kwargs.get("sync", False) or Conf.SYNC:
                # Singleton locking does not work on sync calls because the
                # lock is placed after the run() call (to have the task id).
                async_class = Async
            # Use a more intuitive task name
            if "task_name" not in kwargs:
                kwargs["task_name"] = func.__name__ if callable(func) else func
            task = async_class(func, *args, **kwargs)
            return task.run()
        func.delay = delay
        return func
        # @wraps(func)
        # def wrapper(*args, **kwargs):
        #     task = cls(func, *args, **kwargs)
        #     return task.run()
        # return wrapper


#
# Decorator to make functions asynchronous.
#

def async_task(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        task = Async(f, *args, **kwargs)
        return task.run()
    return wrapper


# File-based locking

def run_with_lock(fn, *args, **kwargs):
    lock = PIDLockFile(getattr(
        settings, "HYPERKITTY_JOBS_UPDATE_INDEX_LOCKFILE",
        os.path.join(gettempdir(), "hyperkitty-jobs-update-index.lock")))
    try:
        lock.acquire(timeout=-1)
    except AlreadyLocked:
        if check_pid(lock.read_pid()):
            log.warning("The job 'update_index' is already running")
            return
        else:
            lock.break_lock()
            lock.acquire(timeout=-1)
    except LockFailed as e:
        log.warning("Could not obtain a lock for the 'update_index' "
                    "job (%s)", e)
        return
    try:
        fn(*args, **kwargs)
    except Exception as e:
        log.exception("Failed to update the fulltext index: %s", e)
    finally:
        lock.release()


def check_pid(pid):
    """ Check For the existence of a unix pid. """
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except OSError as e:
        if e.errno == errno.ESRCH:
            # if errno !=3, we may just not be allowed to send the signal
            return False
    return True


#
# Tasks
#

@SingletonAsync.task
def update_search_index():
    run_with_lock(update_index, remove=False)

# @SingletonAsync.task
# def update_and_clean_search_index():
#     run_with_lock(update_index, remove=True)


@SingletonAsync.task
def rebuild_cache_recent_threads(mlist_name):
    mlist = MailingList.objects.get(name=mlist_name)
    begin_date, end_date = mlist.get_recent_dates()
    cache_key = "MailingList:%s:recent_threads" % mlist.name
    cache.delete(cache_key)
    cache.delete("%s_count" % cache_key)
    # Warm up the cache.
    thread_ids = list(mlist.get_threads_between(
        begin_date, end_date).values_list("id", flat=True))
    # It will be rebuilt daily by a cron job to expunge old threads.
    cache.set(cache_key, thread_ids, None)
    cache.set("%s_count" % cache_key, len(thread_ids), None)


@SingletonAsync.task
def rebuild_mailinglist_cache_new_email(mlist_name, year, month):
    mlist = MailingList.objects.get(name=mlist_name)
    cache.delete("MailingList:%s:recent_participants_count" % mlist.name)
    mlist.recent_participants_count
    cache.delete("MailingList:%s:p_count_for:%s:%s"
                 % (mlist.name, year, month))
    mlist.get_participants_count_for_month(year, month)
    cache.delete("MailingList:%s:top_threads" % mlist.name)
    mlist.top_threads
    cache.delete("MailingList:%s:top_posters" % mlist.name)
    mlist.top_posters


@SingletonAsync.task
def rebuild_thread_cache_new_email(thread_id):
    thread = Thread.objects.get(id=thread_id)
    cache.delete("Thread:%s:emails_count" % thread.id)
    cache.delete("Thread:%s:participants_count" % thread.id)
    cache.delete(make_template_fragment_key(
        "thread_participants", [thread.id]))
    # Warm up the cache.
    thread.emails_count
    thread.participants_count


@SingletonAsync.task
def rebuild_cache_popular_threads(mlist_name):
    mlist = MailingList.objects.get(name=mlist_name)
    cache.delete("MailingList:%s:popular_threads" % mlist.name)
    mlist.popular_threads


@SingletonAsync.task
def compute_thread_positions(thread_id):
    thread = Thread.objects.get(id=thread_id)
    compute_thread_order_and_depth(thread)


@SingletonAsync.task
def update_from_mailman(mlist_name):
    mlist = MailingList.objects.get(name=mlist_name)
    mlist.update_from_mailman()


@SingletonAsync.task
def sender_mailman_id(sender_id):
    sender = Sender.objects.get(pk=sender_id)
    try:
        sender.set_mailman_id()
    except MailmanConnectionError:
        pass


@SingletonAsync.task
def check_orphans(email_id):
    """
    When a reply is received before its original message, it must be
    re-attached when the original message arrives.
    """
    email = Email.objects.get(id=email_id)
    orphans = Email.objects.filter(
            mailinglist=email.mailinglist,
            in_reply_to=email.message_id,
            parent_id__isnull=True,
        ).exclude(
            # guard against emails with the in-reply-to header pointing to
            # themselves
            id=email.id
        )
    for orphan in orphans:
        orphan.set_parent(email)


@SingletonAsync.task
def rebuild_thread_cache_votes(thread_id):
    thread = Thread.objects.get(id=thread_id)
    cache.delete("Thread:%s:votes" % thread.id)
    cache.delete("Thread:%s:votes_total" % thread.id)
    thread.get_votes()


@SingletonAsync.task
def rebuild_email_cache_votes(email_id):
    email = Email.objects.get(id=email_id)
    cache.delete("Email:%s:votes" % email.id)
    email.get_votes()
