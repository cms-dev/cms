
task_info = {
    "name": "batchstdio",
    "title": "Test Batch Task with stdin/stdout",
    "time_limit": "0.1",
    "memory_limit": "64",
    "task_type": "Batch",
    "TaskTypeOptions_Batch_compilation": "alone",
    "TaskTypeOptions_Batch_io_0_inputfile": "",
    "TaskTypeOptions_Batch_io_1_outputfile": "",
    "TaskTypeOptions_Batch_output_eval": "diff",
    "submission_format": "simple",
    "score_type": "Sum",
    "score_parameters": "50",
}

test_cases = [
    ("1.in", "1.out", True),
    ("2.in", "2.out", False),
]
