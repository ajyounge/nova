# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2013 ISP RAS.
# All Rights Reserved.
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

from nova.openstack.common import log as logging
from nova import pci
from nova.scheduler import filters


LOG = logging.getLogger(__name__)


class PciPassthroughFilter(filters.BaseHostFilter):
    """Pci Passthrough Filter based on PCI labels."""

    def host_passes(self, host_state, filter_properties):
        """Only return hosts that have required labels."""
        instance_type = filter_properties.get('instance_type')
        if not instance_type:
            return True

        requested_labels = pci.get_labels_from_instance_type(instance_type)
        if len(requested_labels) == 0:
            return True
        free_labels = list(host_state.free_pci_labels)

        try:
            for label in requested_labels:
                free_labels.remove(label)
            return True
        except ValueError:
            LOG.debug(_("%(host_state)s does not have %(requested_labels)s "
                        "labels, it has only %(free_labels)s."),
                      {'host_state': host_state,
                       'free_labels': host_state.free_pci_labels,
                       'requested_labels': requested_labels})
        return False
