# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2010 Openstack, LLC.
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""
Archtecture Scheduler implementation
"""

import random
import string

from nova import log as logging

LOG = logging.getLogger('nova.scheduler.ArchitectureScheduler')

from nova.scheduler import driver
from nova import db


class ArchitectureScheduler(driver.Scheduler):
    """Implements Scheduler as a random node selector."""

    def grab_children(father):
        local_list = []
        for key, value in father.iteritems():
            local_list.extend(grab_children(value))
        return local_list

    def hosts_up_with_arch(self, context, topic, instance_id):
#    def hosts_up_with_arch(self, context, topic, instance_id, instance_type):

        """Return the list of hosts that have a running service
        for cpu_arch and others.
        """

#        """Figure out what is requested
#        """
        instances = db.instance_get_all_by_instance_id(context,
                                                       instance_id)

        LOG.debug(_("## instances %s"), instances)
        LOG.debug(_("## instance.id %s"), instances[0].id)
        LOG.debug(_("## instance.cpu_arch %s"), instances[0].cpu_arch)

        services = db.service_get_all_by_topic(context, topic)
        LOG.debug(_("## services %s"), services)

        hosts = []

        # from instance table
        wanted_vcpus = instances[0].vcpus
        wanted_memory_mb = instances[0].memory_mb
        wanted_local_gb = instances[0].local_gb

        LOG.debug(_("## wanted-vcpus=%s"), wanted_vcpus)
        LOG.debug(_("## wanted-memory=%s"), wanted_memory_mb)
        LOG.debug(_("## wanted-hard=%s"), wanted_local_gb)

        # from instance_metadata table
        instance_meta = db.instance_metadata_get(context, instance_id)
        LOG.debug(_("## inst-meta=%s"), instance_meta)

        # from instance_type_extra_specs table
        instance_extra = db.instance_type_extra_specs_get( \
            context, instances[0].instance_type_id)
        LOG.debug(_("## inst-extra=%s"), instance_extra)

        # combine to inatance_meta
        instance_meta.update(instance_extra)
        LOG.debug(_("## new inst meta=%s"), instance_meta)

        try:
            wanted_cpu_arch = instance_meta['cpu_arch']
        except:
            wanted_cpu_arch = None

        LOG.debug(_("## wanted-cpu-arch=%s"), wanted_cpu_arch)

        """Get capability from zone_manager and match cpu_arch and others
        """
        cap = self.zone_manager.get_hosts_capabilities(context)
        LOG.debug(_("## cap=%s"), cap)

        for host, host_dict_cap in cap.iteritems():
            LOG.debug(_("## host=%s"), host)
            for service_name_cap, service_dict_cap in \
                host_dict_cap.iteritems():
                if (service_name_cap != 'compute'):
                    continue

                resource_cap = {}
                for cap, value in service_dict_cap.iteritems():
                    if type(value) is int:
                        value = str(value)

                    # simple case: one value
                    if value.find(':') == -1 and value.find(',') == -1:
                        resource_cap[cap] = value

                    # complex; multi-level key-value pairs.
                    # example: cpu_info = { "vendor":"intel", features=
                    #  ["dia", "est"], toplogy={"core":4, "thread":1}}
                    # only the lowest key-value pair is recorded. So, in the
                    # previous eample, the final dict is:
                    #   resource["vendor"] = "intel",
                    #   resource["features"] = "dia, est",
                    #   resource["core"] = "4",
                    #   resource["thread"] = "1",
                    # No key is availabel for cpu_info and topology
                    else:  # decompose capability
                        new_key = ''
                        new_val = ''
                        splitted = value.split(',')
                        for pair in splitted:
                            if pair.find(':') != -1:  # key:value pair
                                if len(new_key) != 0:
                                    resource_cap[new_key] = new_val
                                nspl = pair.split(':')
                                right = nspl[-2].rfind('"', 0, len(nspl[-2]))
                                left = nspl[-2].rfind('"', 0, right)
                                new_key = nspl[-2][left + 1: right]
                                right = nspl[-1].rfind('"', 0, len(nspl[-1]))
                                left = nspl[-1].rfind('"', 0, right)
                                new_val = nspl[-1][left + 1: right]
                            else:  # value only
                                right = pair.rfind('"', 0, len(pair))
                                left = pair.rfind('"', 0, right)
                                if right != -1 and left != -1:
                                    new_val += "," + pair[left + 1:right]
                                else:
                                    new_val += ", " + pair
                        resource_cap[new_key] = new_val

                # if the same architecture is found
                if ((wanted_cpu_arch is None) \
                    or (wanted_cpu_arch == resource_cap['cpu_arch'])):

                    # basic requirements from instance_type
                    LOG.debug(_("## *** wanted arch found: <%s> ***"),
                        wanted_cpu_arch)
                    LOG.debug(_("## cap vcpus = <%s>"),
                        int(resource_cap['vcpus']) \
                        - int(resource_cap['vcpus_used']))
                    LOG.debug(_("## cap memory_mb = <%s>"),
                        resource_cap['host_memory_free'])
                    LOG.debug(_("## cap local_gb = <%s>"),
                        int(resource_cap['disk_total'])
                        - int(resource_cap['disk_used']))

                    if(wanted_vcpus > (int(resource_cap['vcpus'])
                        - int(resource_cap['vcpus_used']))
                    or wanted_memory_mb > int(resource_cap['host_memory_free'])
                    or wanted_local_gb > (int(resource_cap['disk_total')]
                        - int(resource_cap['disk_used'])):

                        flag_different = 1
                    else:
                        flag_different = 0

                    # extra requirements from instance_type_extra_spec
                    # or instance_metadata table

                    for kkey in instance_meta:
                        try:
                            if(flag_different == 0):
                                wanted_value = instance_meta[kkey]
                                LOG.debug(_("## wanted-key=%s"), kkey)
                                LOG.debug(_("## wanted-value=%s"), \
                                    wanted_value)
                                if (wanted_value is not None):
                                    flag_different = 1
                                    if (resource_cap[kkey] is None):
                                        LOG.debug(_("## cap is None"))
                                    else:
                                        # get wanted list first
                                        wanted = wanted_value.split(',')

                                        if type(resource_cap[kkey]) is int:
                                            resource_cap[kkey] = \
                                                str(resource_cap[kkey])

                                        # get provided list now
                                        if resource_cap[kkey].find(',') == -1:
                                            offered = [resource_cap[kkey]]
                                        else:
                                            offered = resource_cap[kkey]. \
                                                split(',')

                                        LOG.debug(_("## offered=%s"), \
                                                offered)

                                        # check if the required are provided
                                        flag_different = 0
                                        for want in wanted:
                                            found = 0
                                            for item in offered:
                                                if(want == item):
                                                    found = 1
                                                    break
                                            if found == 0:
                                                flag_different = 1
                                                LOG.debug(_("**not found"))
                                                break
                                            else:
                                                LOG.debug(_("## found"))
                        except:
                            pass

                    if (flag_different == 0):
                        LOG.debug(_("##\t***** found  **********="))
                        hosts.append(host)
                    else:
                        LOG.debug(_("##\t***** not found  **********="))

        LOG.debug(_("## hosts = %s"), hosts)
        return hosts

    def schedule(self, context, topic, *_args, **_kwargs):
        """Picks a host that is up at random in selected
        arch (if defined).
        """

        instance_id = _kwargs.get('instance_id')
        request_spec = _kwargs.get('request_spec')
#        instance_type = request_spec['instance_type']

        hosts = self.hosts_up_with_arch(context, topic, instance_id)
#        hosts = self.hosts_up_with_arch(context, topic, instance_id,
#                                        instance_type)
        if not hosts:
            return hosts
        else:
            return hosts[int(random.random() * len(hosts))]
