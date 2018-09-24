#!/usr/bin/env bash

./cmstestsuite/scripts/reinit.sh \
    && ./cmstestsuite/scripts/fake_enable.sh \
    && ./cmstestsuite/RunTimeTest.py -w 16 -s 100 -l 'EvaluationService:20';
./cmstestsuite/scripts/fake_disable.sh
