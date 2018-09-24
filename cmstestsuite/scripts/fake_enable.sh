#!/usr/bin/env bash

sed -i -e 's/fake_worker_time=None/fake_worker_time=0.01/' \
    ./cms/service/Worker.py
