#!/usr/bin/env bash
set -x

GIT_BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)

docker compose -p $GIT_BRANCH_NAME -f docker-compose.test.yml run --build --rm testcms
