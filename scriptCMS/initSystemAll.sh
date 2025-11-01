#!/bin/bash

echo "Do you want to Init? if you have old system, it will delete all."
read choise
if [["$choise" != "Y" || "$choise" != "y"]]; then
	exit 0
fi

cd /home/singto1597/Documents/program-project/cmsPiriyalai
echo "Now I'm in cms"

sudo ufw disable
echo "Disable firewall"

wallsudo ufw allow 8888:8890/tcp
sudo ufw reload
echo "Open 8888 8890 Port And reload"

cd .. 
sudo chown -R singto1597:singto1597 cmsPiriyalai
sudo chmod -R 777 cmsPiriyalai
cd cmsPiriyalai
sudo rm -rf .dev/postgres-data
sudo rm -rf .dev/postgres-conf


./docker/cms-dev.sh
echo "Opened Script"
