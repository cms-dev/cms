#!/usr/bin/env bash

./scripts/cmsDropDB -y \
    && ./scripts/cmsInitDB \
    && ./cmscontrib/AddAdmin.py myadmin -p admin
