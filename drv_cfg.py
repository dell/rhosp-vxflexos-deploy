#! /usr/bin/env python
# Copyright (c) 2019 Dell Inc. or its subsidiaries.
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

import argparse
import fcntl
import os
import struct
import sys
import uuid
from binascii import hexlify
from functools import partial
from contextlib import contextmanager
from ctypes import c_uint32, c_uint64, Structure


CHAR_DEVICE_PATH = '/dev/scini'


def write_message(stream, message, error=False):
    stream.write(message + '\n')
    if error:
        sys.exit(1)


error_message = partial(write_message, sys.stderr, error=True)
response_message = partial(write_message, sys.stdout)


@contextmanager
def open_device(device_path=CHAR_DEVICE_PATH):
    fd = None
    try:
        fd = os.open(device_path, os.O_RDWR)
        yield fd
    except OSError as e:
        message = 'Failed to open character device: {e}'.format(e=e)
        error_message(message)
    except Exception as e:
        message = 'Unexpected error opening ' \
                  'character device: {e}'.format(e=e)
        error_message(message)
    finally:
        if fd:
            os.close(fd)


# Implementation of C++ _IO and _IOC macros
IOCPARM_MASK = 0x1fff
IOC_VOID = 0x0


def IO(_type, nr):
    return IOC(IOC_VOID, _type, nr, 0)


def IOC(direction, _type, nr, size):
    return direction | (size & IOCPARM_MASK) << 16 | ord(_type) << 8 | nr


class IoctlGUID(Structure):
    _fields_ = (('returnCode', c_uint64),
                ('uuid', c_uint32 * 4),
                ('networkIdMagicNum', c_uint32),
                ('networkIdTimeStamp', c_uint32))

    def check_return_code(self):
        rc_bytes = struct.pack('Q', self.returnCode)
        if int(hexlify(rc_bytes[0:1]), 16) != 65:
            message = 'Sdc guid is not presented in response'
            error_message(message)

    def unparse_uuid(self):
        try:
            uuid_string = hexlify(struct.pack('IIII', *self.uuid)).decode()
            return uuid.UUID(uuid_string)
        except Exception as e:
            message = 'Failed to parse sdc uuid: {e}'.format(e=e)
            error_message(message)


class IoctlRescan(Structure):
    _fields_ = (('returnCode', c_uint64), )


class IoctlRequest(object):
    @staticmethod
    def ioctl(op_code, buffer):
        try:
            with open_device() as fd:
                fcntl.ioctl(fd, op_code, buffer)
        except IOError as e:
            message = 'Failed to send ioctl request: {e}'.format(e=e)
            error_message(message)
        except Exception as e:
            message = 'Unexpected error sending ioctl request: {e}'.format(e=e)
            error_message(message)

    def query_guid(self, op_code):
        ioctl_guid = IoctlGUID()
        self.ioctl(op_code, ioctl_guid)
        ioctl_guid.check_return_code()
        _uuid = str(ioctl_guid.unparse_uuid()).upper()
        return _uuid

    def rescan(self, op_code):
        ioctl_rescan = IoctlRescan()
        return self.ioctl(op_code, ioctl_rescan)


class QueryGuid(argparse.Action):
    op_code = IO('a', 14)

    def __call__(self, parser, namespace, values, option_string=None):
        _uuid = IoctlRequest().query_guid(self.op_code)
        response_message(_uuid)


class Rescan(argparse.Action):
    op_code = IO('a', 10)

    def __call__(self, parser, namespace, values, option_string=None):
        IoctlRequest().rescan(self.op_code)


parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--query_guid', action=QueryGuid, nargs=0,
                   help='Get the unique ID of the kernel module')
group.add_argument('--rescan', action=Rescan, nargs=0,
                   help='Forces a configuration rescan operation against '
                        'all known MDMs.')
parser.parse_args()
