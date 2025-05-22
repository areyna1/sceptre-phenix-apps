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
import socket, sys, os, stat

from phenix_apps.apps import AppBase
from phenix_apps.common import logger, utils

import phenix.services.minimega as mm

class CarnacInternet(AppBase):
    """Carnac internet user application

    This user application will give the specified hosts internet access.
    Note that this app requires the use of the mgmt_tap app.
    E.g.
        -name: mgmt_tap
        - name: carnac_internet 
          hosts:
          - hostname: host1 
            metadata:
              interface: eth0
          - hostname: host2  
            metadata:
              interface: eth1
    """
    
    def __init__(self):
        AppBase.__init__(self, 'carnac_internet')
        logger.log('INFO', self)
    
        self.startup_dir = f"{self.exp_dir}/startup"
        os.makedirs(self.startup_dir, exist_ok=True)

        #get name of mgmt tap
        self.trunc_exp_name = self.exp_name[:9]
        self.tap = f"{self.trunc_exp_name}_mgmt"

        #get mm hosts
        self.mm_hosts = ','.join([x['name'] for x in mm.host_info()])
    
        #get hosts from carnac_internet app
        self.hosts = self.extract_all_nodes()
        
        self.execute_stage()
        # We don't (currently) let the parent AppBase class handle this step
        # just in case app developers want to do any additional manipulation
        # after the appropriate stage function has completed.
        print(self.experiment.to_json())

    def configure(self):
        logger.log('INFO', f"Running configure for user application: {self.name}")

        #Create startup script for each host
        for host in self.hosts:
            if host.topology.hardware.os_type == "linux":
                kwargs = {"src": f"{self.startup_dir}/{host.hostname}-start-internet.sh", "dst": "/etc/phenix/startup/sceptre-internet-start.sh", "description": "Configuration for internet connectivity"}
                self.add_inject(hostname=host.hostname, inject=kwargs)
            else:
                #TODO - implement startup scripts for windows too
                pass

        logger.log('INFO', f"Completed configure for user application: {self.name}")

    def pre_start(self):
        logger.log('INFO', f"Running pre_start for user application: {self.name}")

        #Write startup script for each host to (1) add default route and (2) add carnac DNS
        for host in self.hosts:
            if "metadata" not in host:
                msg = f"No metadata for {host.hostname}"
                logger.log("WARN", msg)
                continue
            interface = host.metadata.get("interface", "eth0")

            if host.topology.hardware.os_type == "linux":
                startup_file = f"{self.startup_dir}/{host.hostname}-start-internet.sh"
                with open(startup_file, "w") as file_:
                    file_.write('route delete default gw 172.16.1.1 eth0\n')
                    file_.write('route add default gw 172.16.111.1 eth0\n')
                    file_.write('echo "nameserver 192.168.36.61" > /etc/resolv.conf')
                st_ = os.stat(startup_file)
                os.chmod(startup_file, st_.st_mode | stat.S_IEXEC)
            else:
                #TODO - implement startup scripts for windows too
                pass
        logger.log('INFO', f"Completed pre_start for user application: {self.name}")
        
    def post_start(self):
        logger.log('INFO', f"Running post_start for user application: {self.name}")

        #do ip tables stuff on all mm hosts
        cmd1 = f"iptables -A FORWARD -o eth0 -i {self.tap} -s 172.16.0.0/16 -m conntrack --ctstate NEW -j ACCEPT"
        cmd2 = f"iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE"
        cmd3 = f"iptables -A FORWARD -i eth0 -o {self.tap} -m state --state RELATED,ESTABLISHED -j ACCEPT"
        cmd4 = f"iptables -A FORWARD -i {self.tap} -o eth0 -j ACCEPT"
        cmd5 = "echo 1 > /proc/sys/net/ipv4/ip_forward"
        mm.compute_cmd(experiment=self.exp_name, computes=self.mm_hosts, command=cmd1)
        mm.compute_cmd(experiment=self.exp_name, computes=self.mm_hosts, command=cmd2)
        mm.compute_cmd(experiment=self.exp_name, computes=self.mm_hosts, command=cmd3)
        mm.compute_cmd(experiment=self.exp_name,  computes=self.mm_hosts,command=cmd4)
        mm.compute_cmd(experiment=self.exp_name, computes=self.mm_hosts, command=cmd5)

        logger.log('INFO', f"Completed post_start for user application: {self.name}")
        
    def cleanup(self):
        logger.log('INFO', f"Running cleanup for user application: {self.name}")

        #need to clean up all iptables stuff
        cmd1 = f"iptables -D FORWARD -s 172.16.0.0/16 -i {self.tap} -o eth0 -m conntrack --ctstate NEW -j ACCEPT"
        cmd2 = f"iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE"
        cmd3 = f"iptables -D FORWARD -i eth0 -o {self.tap} -m state --state RELATED,ESTABLISHED -j ACCEPT"
        cmd4 = f"iptables -D FORWARD -i {self.tap} -o eth0 -j ACCEPT"
        mm.compute_cmd(experiment=self.exp_name, computes=self.mm_hosts, command=cmd1)
        mm.compute_cmd(experiment=self.exp_name, computes=self.mm_hosts, command=cmd2)
        mm.compute_cmd(experiment=self.exp_name, computes=self.mm_hosts, command=cmd3)
        mm.compute_cmd(experiment=self.exp_name, computes=self.mm_hosts, command=cmd4)

        logger.log('INFO', f"Completed cleanup for user application: {self.name}")


def main():
    CarnacInternet()
