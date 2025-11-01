#!/bin/bash
CMS_DIR="/home/singto1597/Documents/program-project/cmsPiriyalai"
cd "$CMS_DIR" || { echo "❌ CMS directory not found"; exit 1; }
echo "📂 Switched to CMS dir: $(pwd)"

# Detect container ID of devcms
CONTAINER_ID=""
#CONTAINER_ID=$(docker ps --filter "ancestor=cms-main-devcms" --format "{{.ID}}")
echo "⏳ Waiting for devcms container to appear..."
while [ -z "$CONTAINER_ID" ]; do
    CONTAINER_ID=$(docker ps --filter "ancestor=cms-main-devcms" --format "{{.ID}}")
    sleep 1
done
if [ -z "$CONTAINER_ID" ]; then
    echo "❌ ERROR: Cannot find container ID for devcms service"
    exit 1
fi

echo "✅ Found CMS container: $CONTAINER_ID"


TITLE_PREFIX="CMS - "




echo "Starting Web Server in the current terminal..."
tilix -a session-add-right --title="$TITLE_PREFIX Web Server" -x "docker exec -it $CONTAINER_ID sh -c 'cmsContestWebServer'"



# 1. รัน Service ตัวแรกใน Terminal ปัจจุบัน (แทนที่ Shell ของสคริปต์)
echo "Starting Admin Web Server in the current terminal..."
tilix -a session-add-down --title="$TITLE_PREFIX Admin Web Server" -x "docker exec -it $CONTAINER_ID sh -c 'cmsAdminWebServer'"


# 2. รัน Service ตัวที่เหลือใน Split Panes
# (เราใช้ tilix -a session-add-right/down เพื่อสั่งให้ Tilix ที่กำลังรันอยู่ทำงาน)

# Service 2: Evaluation Service (Split Right)
tilix -a session-add-right --title="$TITLE_PREFIX Evaluation Service" -x "docker exec -it $CONTAINER_ID sh -c 'cmsEvaluationService'"
sleep 0.1

# Service 3: Worker (Split Down)
tilix -a session-add-down --title="$TITLE_PREFIX Worker" -x "docker exec -it $CONTAINER_ID sh -c 'cmsWorker'"
sleep 0.1

# Service 4: Scoring Service (Split Right on Worker)
tilix -a session-add-right --title="$TITLE_PREFIX Scoring Service" -x "docker exec -it $CONTAINER_ID sh -c 'cmsScoringService'"
sleep 0.1

# Service 5: Log Service (Split Down on Scoring)
tilix -a session-add-down --title="$TITLE_PREFIX Log Service" -x "docker exec -it $CONTAINER_ID sh -c 'cmsLogService'"
sleep 0.1

# Service 6: Checker (Split Right on Log Service)
tilix -a session-add-right --title="$TITLE_PREFIX Checker" -x "docker exec -it $CONTAINER_ID sh -c 'cmsChecker'"
sleep 0.1

# Service 7, 8, 9: ใช้ session-add-down/right ต่อไปตามรูปแบบที่คุณต้องการ
tilix -a session-add-down --title="$TITLE_PREFIX Printing Service" -x "docker exec -it $CONTAINER_ID sh -c 'cmsPrintingService'"
sleep 0.1
tilix -a session-add-right --title="$TITLE_PREFIX Proxy Service" -x "docker exec -it $CONTAINER_ID sh -c 'cmsProxyService'"
sleep 0.1
tilix -a session-add-down --title="$TITLE_PREFIX Resource Service" -x "docker exec -it $CONTAINER_ID sh -c 'cmsResourceService'"
sleep 0.1


echo "Finished launching all CMS services in split panes."

