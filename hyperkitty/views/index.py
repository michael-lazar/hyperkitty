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

import json

from django.db.models import Q
from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse
from django_mailman3.lib.paginator import paginate

from hyperkitty.lib.view_helpers import show_mlist, is_mlist_authorized
from hyperkitty.models import MailingList


def index(request):
    mlists = [
        ml for ml in MailingList.objects.all()
        if not settings.FILTER_VHOST or show_mlist(ml, request)]

    # Sorting
    sort_mode = request.GET.get('sort')
    if not sort_mode:
        sort_mode = "popular"
    if sort_mode == "name":
        mlists.sort(key=lambda ml: ml.name)
    elif sort_mode == "active":
        # Don't show private lists when sorted by activity, to avoid disclosing
        # info about the private list's activity
        mlists = [ml for ml in mlists if not ml.is_private]
        mlists.sort(key=lambda l: l.recent_threads_count, reverse=True)
    elif sort_mode == "popular":
        # Don't show private lists when sorted by popularity, to avoid
        # disclosing info about the private list's popularity.
        mlists = [l for l in mlists if not l.is_private]
        mlists.sort(key=lambda l: l.recent_participants_count, reverse=True)
    elif sort_mode == "creation":
        mlists.sort(key=lambda l: l.created_at, reverse=True)
    else:
        return HttpResponse("Wrong search parameter",
                            content_type="text/plain", status=500)

    mlists = paginate(mlists, request.GET.get('page'),
                      request.GET.get('count'))

    # Permissions
    for mlist in mlists:
        if not mlist.is_private:
            mlist.can_view = True
        else:
            if is_mlist_authorized(request, mlist):
                mlist.can_view = True
            else:
                mlist.can_view = False

    context = {
        'view_name': 'all_lists',
        'all_lists': mlists,
        'sort_mode': sort_mode,
        }
    return render(request, "hyperkitty/index.html", context)


def find_list(request):
    term = request.GET.get('term')
    result = []
    if term:
        query = MailingList.objects.filter(
            Q(name__icontains=term) | Q(display_name__icontains=term)
            ).order_by("name").values("name", "display_name")
        for line in query[:20]:
            result.append({
                "value": line["name"],
                "label": line["display_name"] or line["name"],
            })
    return HttpResponse(
        json.dumps(result), content_type='application/javascript')
