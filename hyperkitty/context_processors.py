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
# Author: Aamir Khan <syst3m.w0rm@gmail.com>
# Author: Aurelien Bompard <abompard@fedoraproject.org>
#

from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.core.urlresolvers import reverse, NoReverseMatch
from django.shortcuts import resolve_url
from hyperkitty import VERSION


def common(request):
    extra_context = {}
    extra_context.update(export_settings(request))
    extra_context.update(postorius_info(request))
    extra_context["paginator_per_page_options"] = [10, 50, 100, 200]
    extra_context["site_name"] = get_current_site(request).name
    return extra_context


def export_settings(request):
    exports = ["USE_MOCKUPS"]
    extra_context = dict(
        (name.lower(), getattr(settings, name, None)) for name in exports)
    extra_context["HYPERKITTY_VERSION"] = VERSION
    extra_context["login_url"] = resolve_url(settings.LOGIN_URL)
    extra_context["logout_url"] = resolve_url(settings.LOGOUT_URL)
    return extra_context


def postorius_info(request):
    postorius_url = False
    if "postorius" in settings.INSTALLED_APPS:
        try:
            postorius_url = reverse("postorius.views.list.list_index")
            postorius_url = postorius_url.rstrip("/")
        except NoReverseMatch:
            pass
    return {"postorius_installed": postorius_url}
