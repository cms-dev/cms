#!/usr/bin/env bash

set -e

# Start LogService first (needed by AdminWebServer)
echo "Starting LogService..."
cmsLogService 0 &
LOG_PID=$!
sleep 2

# Start AdminWebServer (needed to create contest properly)
echo "Starting AdminWebServer..."
cmsAdminWebServer 0 &
AWS_PID=$!

# Wait for AdminWebServer to be ready
echo "Waiting for AdminWebServer..."
for i in {1..20}; do
    if curl -s http://localhost:8889 > /dev/null 2>&1; then
        break
    fi
    if [ $i -eq 20 ]; then
        echo "AdminWebServer failed to start"
        kill $AWS_PID $LOG_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# Create admin and contest via FunctionalTestFramework (creates proper main_group)
echo "Setting up admin and contest..."
CONTEST_ID=$(python3 << 'EOF'
import datetime
import os
import sys

from cms import TOKEN_MODE_FINITE
from cmscommon.datetime import get_system_timezone
from cmstestsuite import CONFIG
from cmstestsuite.functionaltestframework import FunctionalTestFramework

CONFIG["CONFIG_PATH"] = os.path.join(sys.prefix, "etc/cms.toml")
if "CMS_CONFIG" in os.environ:
    CONFIG["CONFIG_PATH"] = os.environ["CMS_CONFIG"]

framework = FunctionalTestFramework()
framework.initialize_aws()

start_time = datetime.datetime.utcnow()
stop_time = start_time + datetime.timedelta(hours=2)

contest_id, _ = framework.add_contest(
    name="test_contest",
    description="Browser test contest",
    languages=["C++17 / g++"],
    allow_password_authentication="checked",
    start=start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
    stop=stop_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
    timezone=get_system_timezone(),
    allow_user_tests="checked",
    token_mode=TOKEN_MODE_FINITE,
    token_max_number="100",
    token_min_interval="0",
    token_gen_initial="100",
    token_gen_number="0",
    token_gen_interval="1",
    token_gen_max="100",
)
print(contest_id)
EOF
)

echo "Created contest with ID: $CONTEST_ID"

# Start ContestWebServer with the proper contest
echo "Starting ContestWebServer for contest $CONTEST_ID..."
cmsContestWebServer -c $CONTEST_ID 0 &
CWS_PID=$!

# Wait for ContestWebServer to be ready
echo "Waiting for ContestWebServer..."
for i in {1..20}; do
    if curl -s http://localhost:8888 > /dev/null 2>&1; then
        echo "Services are ready!"
        break
    fi
    if [ $i -eq 20 ]; then
        echo "ContestWebServer failed to start"
        kill $CWS_PID $AWS_PID $LOG_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# Run the browser tests
echo "Running browser tests..."
pytest cmstestsuite/browser_tests/ "$@"
TEST_EXIT=$?

# Cleanup
echo "Stopping services..."
kill $CWS_PID $AWS_PID $LOG_PID 2>/dev/null || true
wait 2>/dev/null || true

exit $TEST_EXIT
