import subprocess, sys
import time, random, os, shutil
import json, yaml
from configparser import ConfigParser
from phenix_apps.apps.scorch import ComponentBase
from phenix_apps.common import logger, utils
#import phenix.apps.scorch.mm_utils as vm

class ProviderLogs(ComponentBase):
    def __init__(self):
        ComponentBase.__init__(self, 'providerlogs')

        # Assume RevRun has set up /phenix/topology/?/revrun_staging 
        topo_path = self.metadata.get("topo_path")
               # TODO: Test lines below
        id_list = self.metadata.get("run_ids")
        self.exp_id = str(id_list[self.loop])

        self.staging = os.path.join(topo_path, "revrun_staging")

        self.log_dest = os.path.join(self.staging, "providerlogs")
        
        if not os.path.isdir(self.log_dest):
            os.mkdir(self.log_dest)

        self.execute_stage()

    def start(self):
        logger.log('INFO', f'Starting user component: {self}')

    def stop(self):
        logger.log('INFO', f'Stopping user component: {self.name}')
    
        mm = self.mm_init()
        for app in self.experiment.spec.scenario.apps:
            if app['name'] == 'sceptre':
                for host in app.hosts:
                    if host.metadata.type == 'provider':
                        provider_name = host.hostname
                        #todo generalize this for other providers
                        log_path = '/etc/sceptre/log/solver.log' 

                        logger.log('INFO', f'About to pull solver log for {provider_name}')
                        
                        provider_temp_dir = os.path.join("/", "phenix", self.exp_id)
                        if not os.path.isdir(provider_temp_dir):
                            os.mkdir(provider_temp_dir)

                        mm.cc_mount(provider_name, provider_temp_dir)

                        temp_dest = os.path.join(self.log_dest)
                        if not os.path.isdir(temp_dest):
                            os.mkdir(temp_dest)

                        try:
                            os.system(f'cp {provider_temp_dir}{log_path} {temp_dest}/{provider_name}.log')
                        except Exception as e:
                            logger.log('INFO', f'Count not find provider log. ERROR {e}')

                        logger.log('INFO', f'Wrote {provider_temp_dir}{log_path} to {temp_dest}/{provider_name}.log')

                        mm.clear_cc_mount(provider_name)
                        os.system(f'rm -r {provider_temp_dir}')

        logger.log('INFO', f'Stopped user component: {self.name}')


def main():
    ProviderLogs()


if __name__ == '__main__':
    main()

