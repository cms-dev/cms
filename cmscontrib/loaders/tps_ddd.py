#!/usr/bin/env python3
import logging
from .tps import TpsTaskLoader

logger = logging.getLogger(__name__)

class TpsDDDTaskLoader(TpsTaskLoader):
    def _get_task_type_parameters(self, data, task_type, evaluation_param):
        if task_type == "Online":
            params = super()._get_task_type_parameters(data, "Communication", evaluation_param)
        else:
            params = super()._get_task_type_parameters(data, task_type, evaluation_param)
        # We don't want to compile with stubs, so we make the communication happen through stdin.
        if task_type == "Online":
            params[1] = "alone"
            params[2] = "std_io"
        return params
