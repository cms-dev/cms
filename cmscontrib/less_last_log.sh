#!/bin/bash

less -r "`ls logs/*.log | sort -n | tail -n 1`"

