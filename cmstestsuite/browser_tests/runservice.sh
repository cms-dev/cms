#!/usr/bin/env bash

set -e

echo "Creating test contest..."
CONTEST_ID=$(python3 << 'EOF'
from cms.db import Contest, SessionGen

with SessionGen() as session:
    contest = Contest(
        name="test_contest",
        description="Browser test contest",
    )
    session.add(contest)
    session.commit()
    print(contest.id)
EOF
)

echo "Created contest with ID: $CONTEST_ID"

# Start minimal services for browser tests
echo "Starting LogService..."
cmsLogService 0 &
LOG_PID=$!
sleep 2

echo "Starting AdminWebServer..."
cmsAdminWebServer 0 &
AWS_PID=$!

echo "Starting ContestWebServer for contest $CONTEST_ID..."
cmsContestWebServer -c $CONTEST_ID 0 &
CWS_PID=$!

# Wait for services to be ready
echo "Waiting for services to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8889 > /dev/null 2>&1 && \
       curl -s http://localhost:8888 > /dev/null 2>&1; then
        echo "Services are ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Services failed to start within 30 seconds"
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
