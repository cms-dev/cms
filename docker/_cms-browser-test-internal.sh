#!/usr/bin/env bash

dropdb --if-exists --host=testdb --username=postgres cmsdbfortesting
createdb --host=testdb --username=postgres cmsdbfortesting

pytest cmstestsuite/browser_tests
