###################### UNCLASSIFIED // OFFICIAL USE ONLY ######################
#  Notice: This computer software was prepared by Sandia Corporation,
#  hereinafter the Contractor, under Contract DE-AC04-94AL85000 with the
#  Department of Energy (DOE). All rights in the computer software are reserved
#  by DOE on behalf of the United States Government and the Contractor as
#  provided in the Contract. You are authorized to use this computer software
#  for Governmental purposes but it is not to be released or distributed to the
#  public. NEITHER THE U.S. GOVERNMENT NOR THE CONTRACTOR MAKES ANY WARRANTY,
#  EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.
#  This notice including this sentence must appear on any copies of this
#  computer software.
###############################################################################
import os, shutil

from configparser import ConfigParser, NoOptionError
from phenix_apps.apps import AppBase
from phenix_apps.common import error, logger, utils


class PST(AppBase):
    def __init__(self):
        AppBase.__init__(self, 'pst')
        self.startup_dir = f'{self.exp_dir}/startup'
        self.mako_templates_path = utils.abs_path(__file__, "templates/")
        self.execute_stage()
        # We don't (currently) let the parent AppBase class handle this step
        # just in case app developers want to do any additional manipulation
        # after the appropriate stage function has completed.
        print(self.experiment.to_json())
    
    def configure(self):
        logger.log('INFO', f"Configuring user application: {self.name}")
        nodes = self.extract_nodes_type("provider")
        for node in nodes:
            #inject pst tarball
            shutil.copy(utils.abs_path(__file__, 'snl-pstess.tar.gz'), os.path.join(self.exp_dir, 'snl-pstess.tar.gz'))
            kwargs = {'src': f'{os.path.join(self.exp_dir, "snl-pstess.tar.gz")}', 'dst': '/home/ubuntu/snl-pstess.tar.gz'}
            self.add_inject(hostname=node.hostname, inject=kwargs)
            
            #inject updated s_simu.m
            shutil.copy(utils.abs_path(__file__, 's_simu.m'), os.path.join(self.exp_dir, 's_simu.m'))
            kwargs = {'src': f'{os.path.join(self.exp_dir, "s_simu.m")}', 'dst': '/home/ubuntu/s_simu.m'}
            self.add_inject(hostname=node.hostname, inject=kwargs)
            
            #inject modelHooks
            shutil.copy(utils.abs_path(__file__, 'modelHooks.c'), os.path.join(self.exp_dir, 'modelHooks.c'))
            kwargs = {'src': f'{os.path.join(self.exp_dir, "modelHooks.c")}', 'dst': '/home/ubuntu/modelHooks.c'}
            self.add_inject(hostname=node.hostname, inject=kwargs)
            
            shutil.copy(utils.abs_path(__file__, 'modelHooks.h'), os.path.join(self.exp_dir, 'modelHooks.h'))
            kwargs = {'src': f'{os.path.join(self.exp_dir, "modelHooks.h")}', 'dst': '/home/ubuntu/modelHooks.h'}
            self.add_inject(hostname=node.hostname, inject=kwargs)
            
            #inject sovler
            kwargs = {'src': f'{node.metadata.solver}', 'dst': '/home/ubuntu/pst_solver.m'}
            self.add_inject(hostname=node.hostname, inject=kwargs)
        
            kwargs = {'src': f'{node.metadata.publish_points}', 'dst': '/home/ubuntu/publishPoints.txt'}
            self.add_inject(hostname=node.hostname, inject=kwargs)


            # copy get_path to experiment directory and inject
            get_path_file = utils.abs_path(__file__, 'get_path.m')
            shutil.copy(get_path_file, os.path.join(self.exp_dir, 'get_path.m'))
            kwargs = {'src': f'{os.path.join(self.exp_dir, "get_path.m")}', 'dst': '/home/ubuntu/get_path.m'}
            self.add_inject(hostname=node.hostname, inject=kwargs)
            
            #create startup file
            #delete startup file if injected from sceptre app then inject the pst startup
            for inject in node.topology.injections:
                if inject['dst'] == '/etc/phenix/startup/sceptre-start.sh':
                    node.topology.injections.remove(inject)
            kwargs = {'src': f'{self.startup_dir}/pst-start.sh', 'dst': '/etc/phenix/startup/sceptre-pst-start.sh'}
            self.add_inject(hostname=node.hostname, inject=kwargs)

        logger.log('INFO', f"Configured user application: {self.name}")

    def pre_start(self):
        logger.log('INFO', f"Pre-starting user application: {self.name}")
        nodes = self.extract_nodes_type("provider")
        for node in nodes:
            ipv4_address = node.topology.network.interfaces[0].address
            srv_endpoint = f"tcp://{ipv4_address}:5555"
            with open(f'{self.startup_dir}/pst-start.sh', "w") as file_:
                utils.mako_serve_template("pst-start.mako", self.mako_templates_path, file_, server_endpoint=srv_endpoint, publish_endpoint=node.metadata.publish_endpoint)
        logger.log('INFO', f"Pre-started user application: {self.name}")


def main():
    PST()
