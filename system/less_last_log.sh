#!/bin/bash

less "`ls logs/*.log | sort -n | tail -n 1`"

