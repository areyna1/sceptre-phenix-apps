import subprocess, sys
import time, random, os, shutil
import json, yaml
from configparser import ConfigParser
from phenix_apps.apps.scorch import ComponentBase
from phenix_apps.common import logger, utils
#import phenix.apps.scorch.mm_utils as vm

class RetrieveData(ComponentBase):
    def __init__(self):
        ComponentBase.__init__(self, 'retrievedata')

        # Assume RevRun has set up /phenix/topology/?/revrun_staging 

        topo_path = self.metadata.get("topo_path")

        # TODO: Test lines below
        id_list = self.metadata.get("run_ids")
        self.exp_id = str(id_list[self.loop])

        self.staging = os.path.join(topo_path, "revrun_staging")
        self.config_dest = os.path.join(topo_path, "injects", "datacollection_configs")
        # TODO: Can we assume that this always exists?

        self.data_dest = os.path.join(self.staging, "Data")
        
        if not os.path.isdir(self.data_dest):
            os.mkdir(self.data_dest)

        self.elk_found = False
        nodes = self.experiment.spec.topology.nodes
        for node in nodes:
            hostname = node.general.hostname
            if hostname == "elk":
                self.elk_found = True

        self.execute_stage()

    def start(self):
        logger.log('INFO', f'Starting user component: {self}')

        # Generate injection pairs for ELK VM
        injects = list()
        for f in os.listdir(self.config_dest):
            src = os.path.join(self.config_dest, f)

            try:
                if os.path.isfile(src):
                    if "packetbeat" in f:
                        header = "root"
                        if f == "packetbeat_meta_fields.yml":
                            f = "packetbeat_fields.yml"
                    elif "heartbeat" in f:
                        header = "root"
                    else:
                        header = os.path.join("etc", "phenix", "analytics", "files")

                    dest = os.path.join(header, f)
                    injects.append((src, dest))
            except Exception as e:
                logger.log('ERROR', f'{e}')

        mm = self.mm_init()
        
        if self.elk_found:
            
            temp_dir = os.path.join("/", "phenix", self.exp_id)
            if not os.path.isdir(temp_dir):
                os.mkdir(temp_dir)

            trycount=0
            stopcount=10
            while trycount < stopcount:
                try:
                    mm.cc_mount('elk', temp_dir)
                    break
                except:
                    logger.log('INFO', f'Issue mounting host ELK. Trying again...')
                    
                    trycount += 1
                    if trycount == stopcount:
                        logger.log('ERROR', f'COULD NOT MOUNT ELK VM. Exiting.')
                        raise Exception("Component retrievedata could not mount ELK VM")

                    time.sleep(10)

            for src,dst in injects:
                full_dst = os.path.join(temp_dir, dst)
                dst_folder = os.path.dirname(full_dst)

                if not os.path.isdir(dst_folder):
                    os.makedirs(dst_folder)

                os.system(f'cp {src} {full_dst}')

            mm.clear_cc_mount('elk')
            logger.log('INFO', f'Copied ALL files')

            mm.cc_filter("name=elk")
            mm.cc_background("./etc/phenix/startup/elk-start.sh")
            mm.clear_cc_filter()
            logger.log('INFO', f'Started elk tools')

        logger.log('INFO', f'Started user component: {self}')
    
    def stop(self):
        logger.log('INFO', f'Stopping user component: {self.name}')

        mm = self.mm_init()

        if self.elk_found:
            mm.cc_filter('name=elk')

            # Tell in-experiment ELK box to pull all ES indices
            logger.log('INFO', f'About to run es_pull_all')
            mm.cc_background("bash -c 'cd /etc/phenix/analytics/files; ./es_pull_all;'")

            # TODO: Change how we handle waiting for file I/O on the ELK box. See utils.mm_exec_wait?
            time.sleep(3*60)

            # Mount the ELK VM
            temp_dir = os.path.join("/", "phenix", self.exp_id)
            if not os.path.isdir(temp_dir):
                os.mkdir(temp_dir)

            trycount=0
            stopcount=10
            while trycount < stopcount:
                try:
                    mm.cc_mount('elk', temp_dir)
                    break
                except:
                    logger.log('INFO', f'Issue mounting host ELK. Trying again...')

                    trycount += 1
                    if trycount == stopcount:
                        logger.log('ERROR', f'COULD NOT MOUNT ELK VM. Exiting.')
                        raise Exception("Component retrievedata could not mount ELK VM")

                    time.sleep(10)

            # Extract files from inside ELK box ES
            temp_dest = os.path.join(self.data_dest, self.exp_id)
            if not os.path.isdir(temp_dest):
                os.mkdir(temp_dest)

            mounted_files = os.path.join(temp_dir, "etc", "phenix", "analytics", "files")

            try:
                os.system(f'chmod 777 {mounted_files}/*.scd')
                os.system(f'cp {mounted_files}/*.scd {temp_dest}')
            except Exception as e:
                logger.log('INFO', f'Count not find scd files. ERROR {e}')

            logger.log('INFO', f'Wrote to: {temp_dest}')

            mm.clear_cc_mount('elk')
            os.system(f'rm -r {temp_dir}')

            logger.log('INFO', f'Cleaned up mount')

            # TODO: Send ELK box command to remove staged files
            #mm.cc_exec("bash -c 'rm -r /etc/phenix/analytics/files/*.scd'")
 
            # Locally rename all files
            for filename in os.listdir(temp_dest):
                if filename.endswith(".scd"):
                    og_path = os.path.join(temp_dest, filename)
                    simple_name = (filename[:-4]).split('-')[0]
                    tagged_name = "id{}-{}.scd".format(self.exp_id, simple_name)
                    new_path = os.path.join(self.data_dest, tagged_name.lower())
                
                    os.system(f'mv {og_path} {new_path}')

            os.system(f'rm -r {temp_dest}')

            mm.clear_cc_filter()

        logger.log('INFO', f'Stopped user component: {self.name}')


def main():
    RetrieveData()


if __name__ == '__main__':
    main()
