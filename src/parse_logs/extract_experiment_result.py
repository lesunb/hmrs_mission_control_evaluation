from .parse_base import ExperimentParser, Extractor, asdic
from flatten_json import flatten

class MissionData:
    def __init__(self):
        self.tasks_result = []
        self.navigation_segments = []


class NavSegmentResult:
    def __init__(self, origin, destination, distance, robot, time):
        self.origin = origin
        self.destination = destination
        self.distance = distance
        self.robot = robot
        self.time = time



class TrialRun():
    def __init__(self, exec_group, scenario_id, code):
        # identification
        self.exec_group, self.scenario_id, self.code = exec_group, int(scenario_id), code
        # independent variables
        self.factors = {}
        self.treatment = None
        self.executor = None
        # dependent variables / results 
        self.ttc = None
        self.failure_time = None
        self.end_state = None
        self.has_failure = False
        # metadata
        self.total_time_wall_clock = None

    def to_dict(self):
        _dic = {
            'exec_group': self.exec_group,
            'scenario_id': self.scenario_id,
            'code': self.code,
            'treatment': self.treatment,
            'executor': self.executor,
            'ttc': self.ttc,
            'failure_time': self.failure_time,
            'end_state': self.end_state,
            'total_time_wall_clock': self.total_time_wall_clock,
            'has_failure': self.has_failure,
            #'factors': self.factors,
        }
        return flatten(_dic) ## flat nested dicts, such as factors




def parse_experiment_result(exec_code):    
    ep = ExperimentParser(TrialEndStateExtractor())
    for res, meta in ep.extract(exec_code = exec_code):
        yield res[TrialEndStateExtractor.name]
    return

def check_all_fields_on(origin, model):
    for key, value in model.items():
        if value != asdic(origin).get(key, None):
            return False
    return True
    
##
def parse_executor_robot(skill_log_info):
    if skill_log_info.get('parameters', None) and \
        skill_log_info.get('parameters').get('label', None) == 'navto_room':
        # and \
        #skill_log_info['skill-life-cycle'] == 'STARTED':
        return True, {'executor': skill_log_info['entity']} 
    else:
        return False, None

def parse_sample_received(skill_log_info):
    if skill_log_info['entity'] == 'lab_arm' and \
        skill_log_info.get('status', None) == 'sample-received':
        return True, {'end_state': 'success'} 
    else:
        return False, None

def parse_low_battery(skill_log_info):
    if skill_log_info.get('content', None) == 'ENDLOWBATT':
        return True, {'end_state': 'low-battery', 'has_failure': True}
    return False, None


def parse_no_skill_failure(skill_log_info):
    if skill_log_info.get('status', None) == 'UNAVAILABLE-SKILL':
        return True, {'end_state': 'no-skill', 'has_failure': True}
    else:
        return False, None

def parse_timeout_sim(skill_log_info):
    if skill_log_info.get('content', None) == 'ENDTIMEOUTSIM':
        return True, {'end_state': 'timeout-sim'}
    return False, None

def parse_timeout_wallclock(skill_log_info):
    if skill_log_info.get('entity') == 'trial-watcher' and \
        'False: wall-clock' in skill_log_info.get('content', ''):
        return True, {'end_state': 'timeout-wall'}
    return False, None

def parse_wallclock_time(skill_log_info):
    if skill_log_info.get('entity') == 'trial-watcher':
        return True, {'total_time_wall_clock': skill_log_info.get('time')}
    return False, None

# def parse_mission_end(skill_log_info):
#     if skill_log_info.get('content', None) == 'end!':
#         return True, {''}
#     return False, None
    

def init_trial_state_interpreter(exec_group, scenario_id, trial_run_code):
    trial_run_result = TrialRun(exec_group=exec_group, scenario_id=scenario_id, code=trial_run_code)

    def handle_assigned_robot(assigned, **kargs):
        trial_run_result.assigned = assigned

    def handle_mission_end_success(end_state, time, **kargs):
        trial_run_result.end_state = end_state
        trial_run_result.ttc = time

    def handle_mission_end_failure(end_state, time, **kargs):
        trial_run_result.end_state = end_state
        trial_run_result.failure_time = time
        trial_run_result.has_failure = True

    return handle_assigned_robot, handle_mission_end_success, handle_mission_end_failure, trial_run_result


class TrialEndStateExtractor(Extractor):
    name = 'trial_end_state'
    def __init__(self):
        self.name = TrialEndStateExtractor.name
        self.trial_run: TrialRun = None

    def init_trial(self, exec_code, exec_group, scenario_id, trial_run_code):
        self.handle_assigned_robot, self.handle_mission_success_end, self.handle_mission_fail_end, curr_trial = \
            init_trial_state_interpreter(exec_group, scenario_id, trial_run_code)
        
        self.trial_run = curr_trial

        def get_setter(field):
            def setter(**kvalue):
                setattr(curr_trial, field, kvalue[field])
            return setter

        # each parser is called for each line, when a match is found, 
        #   the handle is called with the appropriate end_state
        return [(parse_executor_robot, get_setter('executor'), True),
                (parse_sample_received, self.handle_mission_success_end, True),
                (parse_low_battery, self.handle_mission_fail_end, False),
                (parse_timeout_sim, self.handle_mission_fail_end, False),
                (parse_no_skill_failure, self.handle_mission_fail_end, False),
                (parse_timeout_wallclock, get_setter('end_state'), False),
                (parse_wallclock_time, get_setter('total_time_wall_clock'), False)]
    
    # def end_trial():
    #     pass

    def result(self):
        return self.trial_run



