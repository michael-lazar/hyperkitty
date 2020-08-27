# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 by Michael Lazar
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
#
# Author: Michael Lazar <lazar.michael22@gmail.com>
import gzip
import os
import tempfile
import time
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.core.management import call_command
import requests
import lxml.html


class Command(BaseCommand):
    help = 'Downloads mail archives from a public website'

    FILE_EXTENSIONS = (".txt", ".txt.gz")

    def add_arguments(self, parser):
        parser.add_argument(
            "archive_url",
            help="the full URL of the pipermail archive page")
        parser.add_argument(
            '--list-address',
            help="the full list address the mailbox will be imported to")
        parser.add_argument(
            "--full", action="store_true",
            help="download all archives, instead of only the most recent")

    def handle(self, archive_url, **options):

        resp = requests.get(archive_url)
        resp.raise_for_status()

        matches = lxml.html.fromstring(resp.content).xpath('//a/@href')
        links = [str(m) for m in matches if str(m).endswith(self.FILE_EXTENSIONS)]

        if not options['full']:
            # Assume chronological order
            links = links[0]

        yesterday = date.today() - timedelta(days=1)

        command_kwargs = {'list_address': options['list_address']}
        command_kwargs['until'] = yesterday.strftime("%Y-%m-%d")
        if options['full']:
            command_kwargs['since'] = '1980-01-01'

        for link in links:
            self.stdout.write(f"Found archive {link}, downloading...")
            url = os.path.join(archive_url, link)
            resp = requests.get(url)
            resp.raise_for_status()

            mbox_data = resp.content
            if link.endswith('.gz'):
                self.stdout.write("Decompressing gzip archive")
                mbox_data = gzip.decompress(resp.content)

            with tempfile.NamedTemporaryFile() as fp:
                fp.write(mbox_data)
                fp.flush()

                call_command("hyperkitty_import", fp.name, **command_kwargs)

            # Rate limit
            time.sleep(1)
