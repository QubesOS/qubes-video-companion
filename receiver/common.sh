#!/bin/bash

# Copyright (C) 2021 Elliot Killick <elliotkillick@zohomail.eu>
# Licensed under the MIT License. See LICENSE file for details.

[ "$DEBUG" == 1 ] && set -x

set -E # Enable function inheritance of traps
trap exit ERR

# Test if v4l2loopback kernel module is installed
test_v4l2loopback() {
    # call modinfo via sudo because Whonix sets 0700 on /lib/modules
    sudo --non-interactive modinfo v4l2loopback &> /dev/null
}
