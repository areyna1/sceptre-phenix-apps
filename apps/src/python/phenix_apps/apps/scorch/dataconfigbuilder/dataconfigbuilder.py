import subprocess, sys
import time, random, os, shutil
import json, yaml
from configparser import ConfigParser
from phenix_apps.apps.scorch import ComponentBase
from phenix_apps.common import logger, utils
#import phenix.apps.scorch.mm_utils as vm

class DataConfigBuilder(ComponentBase):
    #logger.log('INFO', f'ComponentBase is: {ComponentBase}')
    #attrs = vars(ComponentBase)
    #logger.log('INFO', f'ComponentBase attributes are: {attrs}')
    def __init__(self):
        ComponentBase.__init__(self, 'dataconfigbuilder')

        # Assume RevRun has set up /phenix/topology/?/revrun_staging
        topo_path = self.metadata.get('topo_path')
        if not os.path.isdir(topo_path):
            logger.log('ERROR', f'Topo path {topo_path} is not valid')

        staging = os.path.join(topo_path, "revrun_staging")
        self.staging = staging
        self.datastream_spec = os.path.join(staging, "data_config.json")
        self.config_templates = os.path.join(staging, "templates")
        self.config_dest = os.path.join(topo_path, "injects", "datacollection_configs")

        if not os.path.isdir(self.config_dest):
            os.mkdir(self.config_dest)

        for f in os.listdir(self.staging):
            fn = os.path.join(self.staging, f)
            if os.path.isfile(fn):
                new_path = os.path.join(self.config_dest, f)
                os.system(f'cp {fn} {new_path}')

        self.execute_stage()
    
    def configure(self):
        logger.log('INFO', f'Configuring user component: {self}')
        attrs = vars(self)
        try:
            with open(self.datastream_spec, 'r') as datafile:
                data = json.load(datafile)
                datastreams = data["datastreams"]
                logger.log('INFO', f'datastream file loaded') 
        except:
            logger.log('WARN', f'cannot open datastream spec file')
        
        tools = set([d["tool"] for d in datastreams])

        if "bennu" in tools:

            # Map publish_endpoints -> hostname lists
            endpoints_to_hosts = self.metadata.get('publish_endpoints')

            # Map hostname -> filters to build upon
            hostname_lists = endpoints_to_hosts.values()
            hostnames = list()
            for hl in hostname_lists:
                hostnames = hostnames + hl
            hostnames = set(hostnames)

            host_to_filter = dict()

            # Build filters for each provider host
            streams = [d for d in datastreams if d["tool"]=="bennu"]
            for s in streams:
                comps = s["name"].split('.')
                device = comps[0]
                if len(comps) > 1:
                    field = comps[1]
                else:
                    field = "" 

                f = "//{}/{}/ ".format(device, field)

                if s["subgroup"] in hostnames:
                    this_host = s["subgroup"]
                else:
                    this_host = "nohost"

                if this_host not in host_to_filter:
                    host_to_filter[this_host] = ""

                logger.log('INFO', f'DCB: About to concatenate.')

                host_to_filter[this_host] = host_to_filter[this_host] + f

            logger.log('INFO', f'DCB AFTER PARSING:')
            logger.log('INFO', f'ENDPOINTS: {endpoints_to_hosts}')
            logger.log('INFO', f'HOSTNAMES: {hostnames}')
            logger.log('INFO', f'FILTERS  : {host_to_filter}')

            # Read template physical_process config
            phys_config_fn = "gt_config.ini"
            pconfig = ConfigParser()
            phys_config_src = os.path.join(self.config_templates, phys_config_fn)
            logger.log('INFO', f'phys_config_src is: {phys_config_src}')
            pconfig.read(phys_config_src)

            logger.log('INFO', f'READ TEMPLATE CONFIG')

            # Write custom config for each publish point
            for point in endpoints_to_hosts.keys():

                this_filter = ""
                for h in endpoints_to_hosts[point]:

                    if h in host_to_filter:
                        this_filter = this_filter + host_to_filter[h]

                if "nohost" in host_to_filter:
                    this_filter = this_filter + host_to_filter["nohost"]

                if this_filter == "":
                    logger.log('INFO', f'NO FILTER. SKIPPING POINT {point}')
                    continue

                logger.log('INFO', f'THIS FILTER: {this_filter}')

                pconfig.set('groundtruth-monitor','publish-endpoint', point)
                pconfig.set('groundtruth-monitor','filter', this_filter)

                logger.log('INFO', f"CONFIG POINTS SET")

                hosttag = ("-").join(endpoints_to_hosts[point])
                thisfile = hosttag + "-" + phys_config_fn

                logger.log('INFO', f'FILENAME: {thisfile}')

                with open(os.path.join(self.config_dest, thisfile), 'w') as pfile:
                    pconfig.write(pfile)


        if "packetbeat" in tools:
            # No filters needed
            pb1_config_fn = "packetbeat.yml"
            pb2_config_fn = "packetbeat_meta_fields.yml"

            shutil.copy(os.path.join(self.config_templates, pb1_config_fn), os.path.join(self.config_dest, pb1_config_fn))
            shutil.copy(os.path.join(self.config_templates, pb2_config_fn), os.path.join(self.config_dest, pb2_config_fn))
            logger.log('INFO', f'copied templates/configs')


        if "heartbeat" in tools:
            streams = [d for d in datastreams if d["tool"]=="heartbeat"]

            filters = list()
            for u in streams:
                filters.append(str(u["name"]))

            # Write heartbeat config
            heart_config_fn = "heartbeat.yml"
            with open(os.path.join(self.config_templates, heart_config_fn), 'r') as hfile:
                hconfig = yaml.safe_load(hfile)
                logger.log('INFO', f'loaded yaml file')
            hconfig["heartbeat.monitors"][0]["hosts"] = filters
            with open(os.path.join(self.config_dest, heart_config_fn), 'w') as hfile:
                yaml.dump(hconfig, hfile)

        if "metricbeat" in tools:
            logger.log('INFO', f'Metricbeat not supported for component: {self}')

        logger.log('INFO', f'Configured user component: {self}')

    def cleanup(self):
        logger.log('INFO', f'Cleaning up user component: {self.name}')

        shutil.rmtree(self.config_dest)

        logger.log('INFO', f'Cleaned up user component: {self.name}')


def main():
    DataConfigBuilder()


if __name__ == '__main__':
    main()
