# vim: tabstop=4 shiftwidth=4 softtabstop=4

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
Take uploaded bucket contents and register them as disk images (AMIs).
Requires decryption using keys in the manifest.
"""


import binascii
import glob
import json
import os
import shutil
import tarfile
from xml.etree import ElementTree

from nova import exception
from nova import flags
from nova import utils
from nova.objectstore import bucket


FLAGS = flags.FLAGS
flags.DEFINE_string('images_path', '$state_path/images',
                    'path to decrypted images')


class Image(object):
    def __init__(self, image_id):
        self.image_id = image_id
        self.path = os.path.abspath(os.path.join(FLAGS.images_path, image_id))
        if not self.path.startswith(os.path.abspath(FLAGS.images_path)) or \
        not os.path.isdir(self.path):
            raise exception.NotFound

    @property
    def image_path(self):
        return os.path.join(self.path, 'image')

    def delete(self):
        for fn in ['info.json', 'image']:
            try:
                os.unlink(os.path.join(self.path, fn))
            except:
                pass
        try:
            os.rmdir(self.path)
        except:
            pass

    def is_authorized(self, context, readonly=False):
        # NOTE(devcamcar): Public images can be read by anyone,
        #                  but only modified by admin or owner.
        try:
            return (self.metadata['isPublic'] and readonly) or \
                   context.is_admin or \
                   self.metadata['imageOwnerId'] == context.project_id
        except:
            return False

    def set_public(self, state):
        md = self.metadata
        md['isPublic'] = state
        with open(os.path.join(self.path, 'info.json'), 'w') as f:
            json.dump(md, f)

    def update_user_editable_fields(self, args):
        """args is from the request parameters, so requires extra cleaning"""
        fields = {'display_name': 'displayName', 'description': 'description'}
        info = self.metadata
        for field in fields.keys():
            if field in args:
                info[fields[field]] = args[field]
        with open(os.path.join(self.path, 'info.json'), 'w') as f:
            json.dump(info, f)

    @staticmethod
    def all():
        images = []
        for fn in glob.glob("%s/*/info.json" % FLAGS.images_path):
            try:
                image_id = fn.split('/')[-2]
                images.append(Image(image_id))
            except:
                pass
        return images

    @property
    def owner_id(self):
        return self.metadata['imageOwnerId']

    @property
    def metadata(self):
        with open(os.path.join(self.path, 'info.json')) as f:
            return json.load(f)

    @staticmethod
    def add(src, description, kernel=None, ramdisk=None, public=True):
        """adds an image to imagestore

        @type src: str
        @param src: location of the partition image on disk

        @type description: str
        @param description: string describing the image contents

        @type kernel: bool or str
        @param kernel: either TRUE meaning this partition is a kernel image or
                       a string of the image id for the kernel

        @type ramdisk: bool or str
        @param ramdisk: either TRUE meaning this partition is a ramdisk image
                        or a string of the image id for the ramdisk


        @type public: bool
        @param public: determine if this is a public image or private

        @rtype: str
        @return: a string with the image id
        """

        image_type = 'machine'
        image_id = utils.generate_uid('ami')

        if kernel is True:
            image_type = 'kernel'
            image_id = utils.generate_uid('aki')
        if ramdisk is True:
            image_type = 'ramdisk'
            image_id = utils.generate_uid('ari')

        image_path = os.path.join(FLAGS.images_path, image_id)
        os.makedirs(image_path)

        shutil.copyfile(src, os.path.join(image_path, 'image'))

        info = {
            'imageId': image_id,
            'imageLocation': description,
            'imageOwnerId': 'system',
            'isPublic': public,
            'architecture': 'x86_64',
            'imageType': image_type,
            'state': 'available'}

        if type(kernel) is str and len(kernel) > 0:
            info['kernelId'] = kernel

        if type(ramdisk) is str and len(ramdisk) > 0:
            info['ramdiskId'] = ramdisk

        with open(os.path.join(image_path, 'info.json'), "w") as f:
            json.dump(info, f)

        return image_id

    @staticmethod
    def register_aws_image(image_id, image_location, context):
        image_path = os.path.join(FLAGS.images_path, image_id)
        os.makedirs(image_path)

        bucket_name = image_location.split("/")[0]
        manifest_path = image_location[len(bucket_name) + 1:]
        bucket_object = bucket.Bucket(bucket_name)

        manifest = ElementTree.fromstring(bucket_object[manifest_path].read())
        image_type = 'machine'

        try:
            kernel_id = manifest.find("machine_configuration/kernel_id").text
            if kernel_id == 'true':
                image_type = 'kernel'
        except:
            kernel_id = None

        try:
            ramdisk_id = manifest.find("machine_configuration/ramdisk_id").text
            if ramdisk_id == 'true':
                image_type = 'ramdisk'
        except:
            ramdisk_id = None

        try:
            arch = manifest.find("machine_configuration/architecture").text
        except:
            arch = 'x86_64'

        info = {
            'imageId': image_id,
            'imageLocation': image_location,
            'imageOwnerId': context.project_id,
            'isPublic': False,  # FIXME: grab public from manifest
            'architecture': arch,
            'imageType': image_type}

        if kernel_id:
            info['kernelId'] = kernel_id

        if ramdisk_id:
            info['ramdiskId'] = ramdisk_id

        def write_state(state):
            info['imageState'] = state
            with open(os.path.join(image_path, 'info.json'), "w") as f:
                json.dump(info, f)

        write_state('pending')

        encrypted_filename = os.path.join(image_path, 'image.encrypted')
        with open(encrypted_filename, 'w') as f:
            for filename in manifest.find("image").getiterator("filename"):
                shutil.copyfileobj(bucket_object[filename.text].file, f)

        write_state('decrypting')

        # FIXME: grab kernelId and ramdiskId from bundle manifest
        hex_key = manifest.find("image/ec2_encrypted_key").text
        encrypted_key = binascii.a2b_hex(hex_key)
        hex_iv = manifest.find("image/ec2_encrypted_iv").text
        encrypted_iv = binascii.a2b_hex(hex_iv)
        cloud_private_key = os.path.join(FLAGS.ca_path, "private/cakey.pem")

        decrypted_filename = os.path.join(image_path, 'image.tar.gz')
        Image.decrypt_image(encrypted_filename, encrypted_key, encrypted_iv,
                            cloud_private_key, decrypted_filename)

        write_state('untarring')

        image_file = Image.untarzip_image(image_path, decrypted_filename)
        shutil.move(os.path.join(image_path, image_file),
                    os.path.join(image_path, 'image'))

        write_state('available')
        os.unlink(decrypted_filename)
        os.unlink(encrypted_filename)

    @staticmethod
    def decrypt_image(encrypted_filename, encrypted_key, encrypted_iv,
                      cloud_private_key, decrypted_filename):
        key, err = utils.execute(
                'openssl rsautl -decrypt -inkey %s' % cloud_private_key,
                process_input=encrypted_key,
                check_exit_code=False)
        if err:
            raise exception.Error(_("Failed to decrypt private key: %s")
                                  % err)
        iv, err = utils.execute(
                'openssl rsautl -decrypt -inkey %s' % cloud_private_key,
                process_input=encrypted_iv,
                check_exit_code=False)
        if err:
            raise exception.Error(_("Failed to decrypt initialization "
                                    "vector: %s") % err)

        _out, err = utils.execute(
                'openssl enc -d -aes-128-cbc -in %s -K %s -iv %s -out %s'
                 % (encrypted_filename, key, iv, decrypted_filename),
                 check_exit_code=False)
        if err:
            raise exception.Error(_("Failed to decrypt image file "
                                    "%(image_file)s: %(err)s") %
                                    {'image_file': encrypted_filename,
                                     'err': err})

    @staticmethod
    def untarzip_image(path, filename):
        tar_file = tarfile.open(filename, "r|gz")
        tar_file.extractall(path)
        image_file = tar_file.getnames()[0]
        tar_file.close()
        return image_file
