# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Nebula, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging

from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import forms
from horizon import messages

from openstack_dashboard import api


LOG = logging.getLogger(__name__)


class CreateFlavor(forms.SelfHandlingForm):
    _flavor_id_regex = (r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
                        r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9]+|auto$')
    _flavor_id_help_text = _("Flavor ID should be UUID4 or integer. "
                             "Leave this field blank or use 'auto' to set "
                             "a random UUID4.")
    name = forms.RegexField(label=_("Name"),
                            max_length=25,
                            regex=r'^[\w\.\- ]+$',
                            error_messages={'invalid': _('Name may only '
                                'contain letters, numbers, underscores, '
                                'periods and hyphens.')})
    flavor_id = forms.RegexField(label=_("ID"),
                             regex=_flavor_id_regex,
                             required=False,
                             initial='auto',
                             help_text=_flavor_id_help_text)
    vcpus = forms.IntegerField(label=_("VCPUs"))
    memory_mb = forms.IntegerField(label=_("RAM MB"))
    disk_gb = forms.IntegerField(label=_("Root Disk GB"))
    eph_gb = forms.IntegerField(label=_("Ephemeral Disk GB"))
    swap_mb = forms.IntegerField(label=_("Swap Disk MB"))

    def clean_name(self):
        name = self.cleaned_data.get('name')
        try:
            flavors = api.nova.flavor_list(self.request)
        except Exception:
            flavors = []
            msg = _('Unable to get flavor list')
            exceptions.check_message(["Connection", "refused"], msg)
            raise
        if flavors is not None:
            for flavor in flavors:
                if flavor.name == name:
                    raise forms.ValidationError(
                      _('The name "%s" is already used by another flavor.')
                      % name
                    )
        return name

    def clean_flavor_id(self):
        flavor_id = self.data.get('flavor_id')
        try:
            flavors = api.nova.flavor_list(self.request)
        except Exception:
            flavors = []
            msg = _('Unable to get flavor list')
            exceptions.check_message(["Connection", "refused"], msg)
            raise
        if flavors is not None:
            for flavor in flavors:
                if flavor.id == flavor_id:
                    raise forms.ValidationError(
                      _('The ID "%s" is already used by another flavor.')
                      % flavor_id
                    )
        return flavor_id

    def handle(self, request, data):
        try:
            flavor = api.nova.flavor_create(request,
                                            data['name'],
                                            data['memory_mb'],
                                            data['vcpus'],
                                            data['disk_gb'],
                                            flavorid=data["flavor_id"],
                                            ephemeral=data['eph_gb'],
                                            swap=data['swap_mb'])
            msg = _('Created flavor "%s".') % data['name']
            messages.success(request, msg)
            return flavor
        except Exception:
            exceptions.handle(request, _("Unable to create flavor."))


class EditFlavor(CreateFlavor):
    flavor_id = forms.CharField(widget=forms.widgets.HiddenInput)

    def clean_flavor_id(self):
        return self.data.get('flavor_id')

    def handle(self, request, data):
        try:
            flavor_id = data['flavor_id']
            # grab any existing extra specs, because flavor edit currently
            # implemented as a delete followed by a create
            extras_dict = api.nova.flavor_get_extras(self.request,
                                                     flavor_id,
                                                     raw=True)
            # First mark the existing flavor as deleted.
            api.nova.flavor_delete(request, data['flavor_id'])
            # Then create a new flavor with the same name but a new ID.
            # This is in the same try/except block as the delete call
            # because if the delete fails the API will error out because
            # active flavors can't have the same name.
            flavor = api.nova.flavor_create(request,
                                            data['name'],
                                            data['memory_mb'],
                                            data['vcpus'],
                                            data['disk_gb'],
                                            ephemeral=data['eph_gb'],
                                            swap=data['swap_mb'])
            if (extras_dict):
                api.nova.flavor_extra_set(request, flavor.id, extras_dict)
            msg = _('Updated flavor "%s".') % data['name']
            messages.success(request, msg)
            return flavor
        except Exception:
            exceptions.handle(request, _("Unable to update flavor."))
