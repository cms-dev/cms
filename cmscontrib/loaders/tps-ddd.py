#!/usr/bin/env python3
import logging
from tps import TpsTaskLoader

logger = logging.getLogger(__name__)

class TpsDDDTaskLoader(TpsTaskLoader):
    def _get_task_type_parameters(self, data, task_type, evaluation_param):
        params = super()._get_task_type_parameters(data, task_type, evaluation_param)
        # We don't want to compile with stubs, so we make the communication happen through stdin.
        if task_type == "Communication":
            params[1] = "alone"
            params[2] = "std_io"
        return params
