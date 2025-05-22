import subprocess, sys
import time, random, os, shutil
import datetime
import json, yaml
from configparser import ConfigParser
from phenix_apps.apps.scorch import ComponentBase
from phenix_apps.common import logger, utils
#import phenix.apps.scorch.mm_utils as vm

class SleepySheepy(ComponentBase):
    def __init__(self):
        ComponentBase.__init__(self, 'sleepysheepy')

        # Assume RevRun has set up /phenix/topology/?/revrun_staging 

        self.sleep_time = self.metadata.get("sleep_time")

        try:
            self.log_path = self.metadata.get("log_path")
        except:
            self.log_path = None

        id_list = self.metadata.get("run_ids")
        self.exp_id = str(id_list[self.loop])

        self.temp_path = "./mytime.json"
        self.epoch_time = datetime.datetime(1970, 1, 1, 0, 0, 0, 0, datetime.timezone.utc)
        self.sleep_secs = self.sleep_time * 60.

        self.execute_stage()

    def configure(self):
        time = datetime.datetime.now(datetime.timezone.utc)
        start_time = float((time - self.epoch_time).total_seconds())
        end_time = start_time + self.sleep_secs

        with open(self.temp_path, 'w') as path:
            json.dump({'start_time':start_time, 'end_time':end_time}, path)

        logger.log('INFO', f'Config component: {self.name} - stored start time: {start_time}')
    
    def start(self):
        logger.log('INFO', f'Starting user component: {self.name} - calculate sleep time')

        with open(self.temp_path, 'r') as path:
            start_time = float(json.load(path)['start_time'])

        now = datetime.datetime.now(datetime.timezone.utc)
        now_secs = float((now - self.epoch_time).total_seconds())

        diff_secs = now_secs - start_time
        duration = self.sleep_secs - diff_secs
        if duration > 0:
            logger.log('INFO', f'From user component: {self.name} - the sheep will sleep for {duration} secs')
            time.sleep(duration)

        logger.log('INFO', f'Started user component: {self.name} - the sheep is awake')

    def cleanup(self):
        logger.log('INFO', f'Cleaning up user component: {self.name}')

        with open(self.temp_path, 'r') as path:
            times = json.load(path)
            start_time = float(times['start_time'])
            end_time = float(times['end_time'])

        entry = "{} {} {}\n".format(self.exp_id, start_time, end_time)

        try:
            if self.log_path:
                with open(self.log_path, 'a') as log:
                    log.write(entry)
        except Exception as e:
            logger.log('INFO', f'ERROR {e}')

        os.system(f'rm {self.temp_path}')

        logger.log('INFO', f'Cleaned up user component: {self.name}')

def main():
    SleepySheepy()


if __name__ == '__main__':
    main()
