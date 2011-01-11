# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 OpenStack LLC.
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

from webob import exc

from nova import wsgi
from nova.api.openstack import faults


def _translate_keys(inst):
    """ Coerces a shared IP group instance into proper dictionary format """
    return dict(sharedIpGroup=inst)


def _translate_detail_keys(inst):
    """ Coerces a shared IP group instance into proper dictionary format with
    correctly mapped attributes """
    return dict(sharedIpGroup=inst)


class Controller(wsgi.Controller):
    """ The Shared IP Groups Controller for the Openstack API """

    _serialization_metadata = {
        'application/xml': {
            'attributes': {
                'sharedIpGroup': []}}}

    def index(self, req):
        """ Returns a list of Shared IP Groups for the user """
        return dict(sharedIpGroups=[])

    def show(self, req, id):
        """ Shows in-depth information on a specific Shared IP Group """
        return _translate_keys({})

    def update(self, req, id):
        """ You can't update a Shared IP Group """
        raise faults.Fault(exc.HTTPNotImplemented())

    def delete(self, req, id):
        """ Deletes a Shared IP Group """
        raise faults.Fault(exc.HTTPNotFound())

    def detail(self, req, id):
        """ Returns a complete list of Shared IP Groups """
        return _translate_detail_keys({})

    def create(self, req):
        """ Creates a new Shared IP group """
        raise faults.Fault(exc.HTTPNotFound())
