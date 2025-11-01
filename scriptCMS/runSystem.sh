#!/bin/bash
cd /home/singto1597/Documents/program-project/cmsPiriyalai
echo "Now I'm in cms"

sudo chmod -R 777 .dev/postgres-data
docker compose -p cms-main -f docker/docker-compose.dev.yml up -d devdb
docker ps 
echo "Now Database has running!"

./docker/cms-dev.sh
