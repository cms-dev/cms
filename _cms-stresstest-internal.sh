#!/usr/bin/env bash

dropdb --host=testdb --username=postgres cmsdbfortesting
createdb --host=testdb --username=postgres cmsdbfortesting
cmsInitDB

git clone https://github.com/cms-dev/con_test.git
cd con_test

# These don't play well with the StressTest script
for i in communication communicationtwoways outputonly outputonlycomparator; do
    sed -i "/$i/d" contest.yaml
done

# Take the solution.c, solution.py, etc, files from each task, and rename them
# to taskname.c, taskname.py, etc. This is needed because the StressTest script
# needs the solution name to match the submission format (task name).
mkdir -p stress_sols
for i in batch batch_comparator batch_file batchgrader batchwithoutgen; do
    for j in $(ls -d $i/sol/*); do
        ext=${j##*.}
        cp $j stress_sols/${i%/}.$ext
    done
done

cmsImportUser --all
cmsImportContest --import-tasks .

cd ..

# Start ResourceService
cmsResourceService -a 1 &
sleep 5

python3 cmstestsuite/StressTest.py --contest-id 1 --submissions-path stress_sols/
