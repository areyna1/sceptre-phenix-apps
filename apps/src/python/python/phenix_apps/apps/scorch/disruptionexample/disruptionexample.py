import subprocess, sys
import time, random, os
from phenix_apps.apps.scorch import ComponentBase
from phenix_apps.common import logger, utils
#import phenix.apps.scorch.mm_utils as vm

class DisruptionExample(ComponentBase):
    def __init__(self):
        ComponentBase.__init__(self, 'disruptionexample')
        self.execute_stage()
    
    def start(self):

        # get all scorch object attributes (testing purposes)
        logger.log('INFO', f'Starting user component: {self.name}')
        
        mm = self.mm_init()
        
        disruption_node = self.metadata.get('nodes')
        logger.log('INFO', f'disruption node is: {disruption_node}')
        sleep_duration = int(self.metadata.get('sleep_duration'))
        logger.log('INFO', f' sleep duration is: {sleep_duration}')
        nodes = self.experiment.spec.topology.nodes
        match = False
        for node in nodes:
            hostname = node.general.hostname

            if hostname == disruption_node:
                match = True
        if match == True:
            logger.log('INFO',f'sending commands to {disruption_node}')
            mm.cc_filter("name=" +disruption_node)
            time.sleep(sleep_duration)
            mm.cc_background('bash /opt/restart_vm.sh')
        logger.log('INFO', f'{self.name} Start stage complete')

    def stop(self):
        disruption_node = self.metadata.get('nodes')
        logger.log('INFO', f'Stopping user component: {self.name}')
        mm = self.mm_init()
        mm.cc_filter("name=" +disruption_node)
        mm.cc_background('rm /opt/restart_vm.sh')
        mm.clear_cc_filter()
        logger.log('INFO', f'Stopped user component: {self.name}')


def main():
    DisruptionExample()


if __name__ == '__main__':
    main()
