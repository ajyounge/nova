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

"""Implementation of an image service that uses Glance as the backend"""

import httplib
import json
import urlparse

from nova import exception
from nova import flags
from nova import log as logging
from nova.image import service


LOG = logging.getLogger('nova.image.glance')

FLAGS = flags.FLAGS
flags.DEFINE_string('glance_teller_address', 'http://127.0.0.1',
                    'IP address or URL where Glance\'s Teller service resides')
flags.DEFINE_string('glance_teller_port', '9191',
                    'Port for Glance\'s Teller service')
flags.DEFINE_string('glance_parallax_address', 'http://127.0.0.1',
                    'IP address or URL where Glance\'s Parallax service '
                    'resides')
flags.DEFINE_string('glance_parallax_port', '9292',
                    'Port for Glance\'s Parallax service')


class TellerClient(object):

    def __init__(self):
        self.address = FLAGS.glance_teller_address
        self.port = FLAGS.glance_teller_port
        url = urlparse.urlparse(self.address)
        self.netloc = url.netloc
        self.connection_type = {'http': httplib.HTTPConnection,
                                'https': httplib.HTTPSConnection}[url.scheme]


class ParallaxClient(object):

    def __init__(self):
        self.address = FLAGS.glance_parallax_address
        self.port = FLAGS.glance_parallax_port
        url = urlparse.urlparse(self.address)
        self.netloc = url.netloc
        self.connection_type = {'http': httplib.HTTPConnection,
                                'https': httplib.HTTPSConnection}[url.scheme]

    def get_image_index(self):
        """
        Returns a list of image id/name mappings from Parallax
        """
        try:
            c = self.connection_type(self.netloc, self.port)
            c.request("GET", "images")
            res = c.getresponse()
            if res.status == 200:
                # Parallax returns a JSONified dict(images=image_list)
                data = json.loads(res.read())['images']
                return data
            else:
                LOG.warn(_("Parallax returned HTTP error %d from "
                           "request for /images"), res.status_int)
                return []
        finally:
            c.close()

    def get_image_details(self):
        """
        Returns a list of detailed image data mappings from Parallax
        """
        try:
            c = self.connection_type(self.netloc, self.port)
            c.request("GET", "images/detail")
            res = c.getresponse()
            if res.status == 200:
                # Parallax returns a JSONified dict(images=image_list)
                data = json.loads(res.read())['images']
                return data
            else:
                LOG.warn(_("Parallax returned HTTP error %d from "
                           "request for /images/detail"), res.status_int)
                return []
        finally:
            c.close()

    def get_image_metadata(self, image_id):
        """
        Returns a mapping of image metadata from Parallax
        """
        try:
            c = self.connection_type(self.netloc, self.port)
            c.request("GET", "images/%s" % image_id)
            res = c.getresponse()
            if res.status == 200:
                # Parallax returns a JSONified dict(image=image_info)
                data = json.loads(res.read())['image']
                return data
            else:
                # TODO(jaypipes): log the error?
                return None
        finally:
            c.close()

    def add_image_metadata(self, image_metadata):
        """
        Tells parallax about an image's metadata
        """
        try:
            c = self.connection_type(self.netloc, self.port)
            body = json.dumps(image_metadata)
            c.request("POST", "images", body)
            res = c.getresponse()
            if res.status == 200:
                # Parallax returns a JSONified dict(image=image_info)
                data = json.loads(res.read())['image']
                return data['id']
            else:
                # TODO(jaypipes): log the error?
                return None
        finally:
            c.close()

    def update_image_metadata(self, image_id, image_metadata):
        """
        Updates Parallax's information about an image
        """
        try:
            c = self.connection_type(self.netloc, self.port)
            body = json.dumps(image_metadata)
            c.request("PUT", "images/%s" % image_id, body)
            res = c.getresponse()
            return res.status == 200
        finally:
            c.close()

    def delete_image_metadata(self, image_id):
        """
        Deletes Parallax's information about an image
        """
        try:
            c = self.connection_type(self.netloc, self.port)
            c.request("DELETE", "images/%s" % image_id)
            res = c.getresponse()
            return res.status == 200
        finally:
            c.close()


class GlanceImageService(service.BaseImageService):
    """Provides storage and retrieval of disk image objects within Glance."""

    def __init__(self):
        self.teller = TellerClient()
        self.parallax = ParallaxClient()

    def index(self, context):
        """
        Calls out to Parallax for a list of images available
        """
        images = self.parallax.get_image_index()
        return images

    def detail(self, context):
        """
        Calls out to Parallax for a list of detailed image information
        """
        images = self.parallax.get_image_details()
        return images

    def show(self, context, id):
        """
        Returns a dict containing image data for the given opaque image id.
        """
        image = self.parallax.get_image_metadata(id)
        if image:
            return image
        raise exception.NotFound

    def create(self, context, data):
        """
        Store the image data and return the new image id.

        :raises AlreadyExists if the image already exist.

        """
        return self.parallax.add_image_metadata(data)

    def update(self, context, image_id, data):
        """Replace the contents of the given image with the new data.

        :raises NotFound if the image does not exist.

        """
        self.parallax.update_image_metadata(image_id, data)

    def delete(self, context, image_id):
        """
        Delete the given image.

        :raises NotFound if the image does not exist.

        """
        self.parallax.delete_image_metadata(image_id)

    def delete_all(self):
        """
        Clears out all images
        """
        pass
