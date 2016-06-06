# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 by the Free Software Foundation, Inc.
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

from django.dispatch import receiver
from allauth.account.signals import email_confirmed, user_signed_up
from allauth.socialaccount.signals import social_account_added
from hyperkitty.lib.mailman import add_address_to_mailman_user

import logging
logger = logging.getLogger(__name__)


# @receiver(user_logged_in)
# def on_user_logged_in(sender, **kwargs):
#     # Sent when a user logs in.
#     print("ON_USER_LOGGED_IN", kwargs.keys())


@receiver(user_signed_up)
def on_user_signed_up(sender, **kwargs):
    # Sent when a user signs up for an account.
    # We want to add the user to Mailman with all its verified email addresses.
    if "sociallogin" in kwargs:
        sociallogin = kwargs["sociallogin"]
        for address in sociallogin.email_addresses:
            if address.verified:
                add_address_to_mailman_user(sociallogin.user, address)


# @receiver(email_added)
# def on_email_added(sender, **kwargs):
#     print("ON_EMAIL_ADDED", kwargs.keys())
#     # Sent when a new email address has been added.
#     # Do nothing, wait for confirmation
#     pass


@receiver(email_confirmed)
def on_email_confirmed(sender, **kwargs):
    # Sent after the email address in the db was updated and set to confirmed.
    # Associate it with the user and set it to verified in Mailman.
    email_address = kwargs["email_address"]
    logger.debug("Confirmed email %s of user %s",
                 email_address.email, email_address.user.username)
    add_address_to_mailman_user(email_address.user, email_address.email)


# @receiver(email_changed)
# def on_email_changed(sender, **kwargs):
#     # Sent when a primary email address has been changed.
#     user = get_mailman_client().get_user(kwargs['user'].email)
#     # TODO: do something?


@receiver(social_account_added)
def on_social_account_added(sender, **kwargs):
    # Sent after a user connects a social account to a their local account.
    # Add to mailman emails that were marked as verified by the social account
    # provider.
    sociallogin = kwargs["sociallogin"]
    logger.debug("Social account %s added for user %s",
                 sociallogin.account, sociallogin.user.username)
    for address in sociallogin.email_addresses:
        if address.verified:
            add_address_to_mailman_user(sociallogin.user, address)
