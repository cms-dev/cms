#!/usr/bin/env bash

sed -i -e 's/fake_worker_time=0.01/fake_worker_time=None/' \
    ./cms/service/Worker.py
