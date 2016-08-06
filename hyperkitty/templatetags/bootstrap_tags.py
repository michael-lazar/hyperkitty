# -*- coding: utf-8 -*-
# Copyright (C) 1998-2016 by the Free Software Foundation, Inc.
#
# This file is part of Postorius.
#
# Postorius is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# Postorius is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Postorius.  If not, see <http://www.gnu.org/licenses/>.

from django import template


register = template.Library()


@register.filter(name='add_form_control')
def add_form_control(field):
    return field.as_widget(attrs={'class': 'form-control'})


@register.filter('fieldtype')
def fieldtype(field):
    return field.field.widget.__class__.__name__


@register.filter('is_checkbox')
def is_checkbox(field):
    return field.field.widget.__class__.__name__ in (
        'CheckboxInput', 'CheckboxSelectMultiple')


@register.inclusion_tag('hyperkitty/fragments/bootstrap/form.html',
                        takes_context=True)
def bootstrap_form(context, form, button=None):
    return dict(
        form=form,
        button=button,
        )


@register.inclusion_tag('hyperkitty/fragments/bootstrap/form-horizontal.html',
                        takes_context=True)
def bootstrap_form_horizontal(
        context, form, size_left=2, size_right=8, button=None):
    return dict(
        form=form,
        size_left=size_left,
        size_right=size_right,
        button=button,
        )
