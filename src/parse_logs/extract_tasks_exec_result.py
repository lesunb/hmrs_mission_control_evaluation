import re
from collections import namedtuple
from enum import Enum
from typing import List

from .parse_base import ExperimentParser, Extractor


class TaskEndState(Enum):
    SUCCESS = True
    FAILURE = False
    UNKNOWN = None

class TaskResult:
    def __init__(self, exec_code, trial_run_code, exec_group, robot,
                start_time, skill, label, parameters):
        self.exec_code = exec_code
        self.trial_run_code = trial_run_code
        self.exec_group = exec_group
        self.robot = robot
        self.start_time = start_time
        self.skill = skill
        self.label = label
        self.parameters = parameters
        self.expent_time = None
        self.end_time = None
        self.end_state: TaskEndState = None

task_started = namedtuple('task_started', 'robot skill parameters')
task_ended = namedtuple('task_ended', 'robot skill end_state time')

def parse_experiment_result(exec_code):    
    ep = ExperimentParser(TaskStateExtractor())
    for res in ep.extract(exec_code = exec_code):
        yield res[TaskStateExtractor.name]
    return


def extract_status_and_parameters(text):
    try:
        content = re.sub(r"\((.*?)\)", r"\1", text) # remove parenteses
        p = re.compile(r"status=([\w\.]*),")
        status = p.findall(content).pop(-1)

        p2 = re.compile(r"parameters=(.*)")
        parameters = p2.findall(content).pop(-1)
        return status, eval(parameters)
    except Exception as e:
        print(e)
        return None, None

def init_task_state_interpreter(exec_code, exec_group, trial_run_code):
    running_tasks: dict[str, TaskResult] = {}
    
    tasks_results = []
    failures = []

    def start_task(time, entity, skill, parameters, label=None, **_):
        robot = entity
        label = parameters.get('label', None)
        if running_tasks.get(robot):
            if running_tasks.get(robot).label == label:
                # do not start the same task twice
                return
            # else end the last task
            print(f'{robot} started {skill} without logging end of {running_tasks[robot].skill}')
            end_task(time, robot, running_tasks[robot].skill, end_state='SUCCESS')
            
        task = TaskResult(
            exec_code=exec_code, trial_run_code=trial_run_code, exec_group=exec_group,
            robot=robot, skill=skill, label=label, parameters=parameters, start_time=time
        )
        tasks_results.append(task)
        running_tasks[robot] = task

    def end_task(time, robot, skill, end_state):
        curr_task = running_tasks[robot]
        if curr_task.skill != skill:
            failures.append(f'failure parsing "{robot}:{skill}" logs. {exec_code}:{exec_group}:{trial_run_code}')
        else:
            curr_task.end_time = time
            curr_task.end_state = end_state
            running_tasks[robot] = None
    
    def end_trial(tasks_result_to_extend):
        # TODO handle not detected end of tasks
        tasks_result_to_extend.extend(tasks_results)

    return start_task, end_task, end_trial

def parse_task_started(skill_log_info):
    if skill_log_info['status'] == 'STARTED':
        return True, {'label': skill_log_info['parameters']['label']}
    return False, None

def parse_task_ended(line):
    return False, None

class TaskStateExtractor(Extractor):
    name = 'task_states'
    def __init__(self):
            self.name = TaskStateExtractor.name
            self.tasks_results: list[TaskResult] = None
            self.handle_task_start, self.handle_task_end, self.ctx_end_trial = None, None, None
    

    def init_trial(self, exec_code, exec_group, scenario_id, trial_run_code):
        self.tasks_results: list[TaskResult] = []
        self.handle_task_start, self.handle_task_end, self.ctx_end_trial = \
            init_task_state_interpreter(exec_code, exec_group, trial_run_code)
        
        # pair fnc for parse/match and handle (in case of a match)            
        return  [(parse_task_started, self.handle_task_start, True),
                (parse_task_ended, self.handle_task_end, True)]
                #(parse_mission_end, self.handle_task_on_mission_end)]

    def end_trial(self):
        self.ctx_end_trial(self.tasks_results)
        self.handle_task_start, self.handle_task_end, self.ctx_end_trial = None, None, None

    def result(self):
        filtered_results = []
        for task in self.tasks_results:
            already_on_results = False
            for already_task in filtered_results:
                if already_task.start_time == task.start_time and \
                    already_task.label == task.label:
                    already_on_results = True
                    break
            if not already_on_results:
                filtered_results.append(task)

        # remove 
        return filtered_results