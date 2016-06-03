# -*- coding: utf-8 -*-
#
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

from __future__ import absolute_import, unicode_literals

from urllib2 import HTTPError

import dateutil.parser
import mailmanclient

from django.conf import settings
from django.core.urlresolvers import reverse, NoReverseMatch
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect
from django.utils.timezone import get_current_timezone

from hyperkitty.models import (
    Favorite, LastView, MailingList, Sender, Email, Vote, Profile)
from hyperkitty.forms import UserProfileForm
from hyperkitty.lib.view_helpers import is_mlist_authorized
from hyperkitty.lib.paginator import paginate
from hyperkitty.lib.mailman import get_mailman_client


import logging
logger = logging.getLogger(__name__)


@login_required
def user_profile(request):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        # Create the profile if it does not exist. There's a signal receiver
        # that creates it for new users, but HyperKitty may be added to an
        # existing Django project with existing users.
        profile = Profile.objects.create(user=request.user)
    mm_user = profile.get_mailman_user()

    if request.method == 'POST':
        form = UserProfileForm(request.POST)
        if form.is_valid():
            request.user.first_name = form.cleaned_data["first_name"]
            request.user.last_name = form.cleaned_data["last_name"]
            profile.timezone = form.cleaned_data["timezone"]
            request.user.save()
            profile.save()
            # Now update the display name in Mailman
            if mm_user is not None:
                mm_user.display_name = "%s %s" % (
                        request.user.first_name, request.user.last_name)
                mm_user.save()
            messages.success(request, "The profile was successfully updated.")
            return redirect(reverse('hk_user_profile'))
    else:
        form = UserProfileForm(initial={
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
                "timezone": get_current_timezone(),
                })

    # Emails
    other_addresses = profile.addresses[:]
    other_addresses.remove(request.user.email)

    # Extract the gravatar_url used by django_gravatar2.  The site
    # administrator could alternatively set this to http://cdn.libravatar.org/
    gravatar_url = getattr(settings, 'GRAVATAR_URL', 'http://www.gravatar.com')
    gravatar_shortname = '.'.join(gravatar_url.split('.')[-2:]).strip('/')

    context = {
        'user_profile': profile,
        'form': form,
        'other_addresses': other_addresses,
        'gravatar_url': gravatar_url,
        'gravatar_shortname': gravatar_shortname,
    }
    try:
        # Try to get Postorius' profile url
        context['profile_url'] = reverse('user_profile')
    except NoReverseMatch:
        pass
    return render(request, "hyperkitty/user_profile.html", context)


@login_required
def favorites(request):
    # Favorite threads
    favs = Favorite.objects.filter(
        user=request.user).order_by("-thread__date_active")
    favs = paginate(favs, request.GET.get('favpage'))
    return render(request, 'hyperkitty/ajax/favorites.html', {
                "favorites": favs,
            })


@login_required
def last_views(request):
    # Last viewed threads
    lviews = LastView.objects.filter(
        user=request.user).order_by("-view_date")
    lviews = paginate(lviews, request.GET.get('lvpage'))
    return render(request, 'hyperkitty/ajax/last_views.html', {
                "last_views": lviews,
            })


@login_required
def votes(request):
    all_votes = paginate(
        request.user.votes.all(), request.GET.get('vpage'))
    return render(request, 'hyperkitty/ajax/votes.html', {
                "votes": all_votes,
            })


@login_required
def subscriptions(request):
    profile = request.user.hyperkitty_profile
    mm_user_id = profile.get_mailman_user_id()
    subs = []
    for mlist_id in profile.get_subscriptions():
        try:
            mlist = MailingList.objects.get(list_id=mlist_id)
        except MailingList.DoesNotExist:
            mlist = None  # no archived email yet
        posts_count = likes = dislikes = 0
        first_post = all_posts_url = None
        if mlist is not None:
            posts_count = profile.emails.filter(
                mailinglist__name=mlist.name).count()
            likes, dislikes = profile.get_votes_in_list(mlist.name)
            first_post = profile.get_first_post(mlist)
            if mm_user_id is not None:
                all_posts_url = "%s?list=%s" % (
                    reverse("hk_user_posts", args=[mm_user_id]),
                    mlist.name)
        likestatus = "neutral"
        if likes - dislikes >= 10:
            likestatus = "likealot"
        elif likes - dislikes > 0:
            likestatus = "like"
        subs.append({
            "list_name": mlist.name if mlist else mlist_id,
            "mlist": mlist,
            "posts_count": posts_count,
            "first_post": first_post,
            "likes": likes,
            "dislikes": dislikes,
            "likestatus": likestatus,
            "all_posts_url": all_posts_url,
        })
    return render(request, 'hyperkitty/ajax/user_subscriptions.html', {
                "subscriptions": subs,
            })


def public_profile(request, user_id):
    class FakeMailmanUser(object):
        display_name = None
        created_on = None
        addresses = []
        subscription_list_ids = []
        user_id = None
    try:
        client = get_mailman_client()
        mm_user = client.get_user(user_id)
    except HTTPError:
        raise Http404("No user with this ID: %s" % user_id)
    except mailmanclient.MailmanConnectionError:
        mm_user = FakeMailmanUser()
        mm_user.user_id = user_id
    # XXX: don't list subscriptions, there's a privacy issue here.
    # # Subscriptions
    # subscriptions = get_subscriptions(mm_user, db_user)
    all_votes = Vote.objects.filter(email__sender__mailman_id=user_id)
    likes = all_votes.filter(value=1).count()
    dislikes = all_votes.filter(value=-1).count()
    likestatus = "neutral"
    if likes - dislikes >= 10:
        likestatus = "likealot"
    elif likes - dislikes > 0:
        likestatus = "like"
    # This is only used for the Gravatar. No email display on the public
    # profile, we have enough spam as it is, thank you very much.
    try:
        email = unicode(mm_user.addresses[0])
    except (KeyError, IndexError):
        email = None
    fullname = mm_user.display_name
    if not fullname:
        fullname = Sender.objects.filter(mailman_id=user_id).exclude(
            name="").values_list("name", flat=True).first()
    if mm_user.created_on is not None:
        creation = dateutil.parser.parse(mm_user.created_on)
    else:
        creation = None
    posts_count = Email.objects.filter(sender__mailman_id=user_id).count()
    is_user = request.user.is_authenticated() and bool(
        set([str(a) for a in mm_user.addresses]) &
        set(request.user.hyperkitty_profile.addresses))
    context = {
        "fullname": fullname,
        "creation": creation,
        "posts_count": posts_count,
        "likes": likes,
        "dislikes": dislikes,
        "likestatus": likestatus,
        "email": email,
        "is_user": is_user,
    }
    return render(request, "hyperkitty/user_public_profile.html", context)


def posts(request, user_id):
    mlist_fqdn = request.GET.get("list")
    if mlist_fqdn is None:
        mlist = None
        return HttpResponse("Not implemented yet", status=500)
    else:
        try:
            mlist = MailingList.objects.get(name=mlist_fqdn)
        except MailingList.DoesNotExist:
            raise Http404("No archived mailing-list by that name.")
        if not is_mlist_authorized(request, mlist):
            return render(request, "hyperkitty/errors/private.html", {
                            "mlist": mlist,
                          }, status=403)

    fullname = Sender.objects.filter(mailman_id=user_id).exclude(
        name="").values_list("name", flat=True).first()
    # Get the messages and paginate them
    emails = Email.objects.filter(
        mailinglist=mlist, sender__mailman_id=user_id)
    try:
        page_num = int(request.GET.get('page', "1"))
    except ValueError:
        page_num = 1
    emails = paginate(emails, page_num)

    for email in emails:
        email.myvote = email.votes.filter(user=request.user).first()

    context = {
        'user_id': user_id,
        'mlist': mlist,
        'emails': emails,
        'fullname': fullname,
    }
    return render(request, "hyperkitty/user_posts.html", context)
