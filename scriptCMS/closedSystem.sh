#!/bin/bash
cd /home/singto1597/Documents/program-project/cmsPiriyalai
echo "Now I'm in cms"

docker compose -p cms-main -f docker/docker-compose.dev.yml down
echo "Docker Down"
