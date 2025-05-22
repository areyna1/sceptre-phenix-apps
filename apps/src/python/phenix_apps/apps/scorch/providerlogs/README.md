Provider logs is a draft component capability for verifying that provider logs did not error out mid-experiment.

The component is currently custom for a Simulink provider. Because it is not yet generalized, it is not included in the RevRun experiment
by default. However, if you would like to include it, RevRun does have support for processing the logs.

## To include this component in a RevRun-driven experiment:

 * Make sure to copy this folder ("`providerlogs`") to `/opt/phenix/apps/src/python/phenix/apps/scorch/` and add an entry for `providerlogs` into `/opt/phenix/apps/src/python/setup.py`. To do this, follow the instructions from the README in the parent of this folder.

### Integrating as a "disruption":
In your RevRun Project Folder for your analysis, for each experiment that should run this tool, do the following. Note that if you are using DRE, you only need to make these changes in the `baseline` folder:
 * Include a copy of the example config yaml for this component. Rename the file to `providerlogs.yaml`. 
 * Edit `providerlogs.yaml` to hard-code the correct topo_path and run_ids configuration. `topo_path` should be the path to the topology folder. `run_ids` should be a list the contains the ID of the current experiment that you are configuring.
 * Edit `experiment_config.yaml` to set the disruption. 
    * If you are using older source code (pre-integration of Candlebox updates), only one disruption is allowed. Set the `disruption` field to "providerlogs". Note that if you are already using a different disruption, then it may make more sense to integrate providerlogs into your local RevRun source code, as described below.
    * If you are using newer source code (post-integration of Candlebox updates), you may list multiple disruptions. Make sure that "providerlogs" is somewhere on the list, and that it is listed in a location that makes sense with the rest of the components listed.  

### Integrating into your local RevRun source code
 * In `src/run_sceptre_scorch/baseconfigs/scenario_generator.py`, in the `merge_scorch` function, under the section labeled "Fill in metadata for RevRun-specific apps", add the following lines.
    ```
    pl_ind = new_names.index("providerlogs")
    new_sco_app["metadata"]["components"][pl_ind]["metadata"]["topo_path"] = self.dir_path
    new_sco_app["metadata"]["components"][pl_ind]["metadata"]["run_ids"] = self.run_ids
    ```
 * In `src/run_sceptre_scorch/baseconfigs/template_scenario.yaml`, in the configuration block for the SCORCH app...
    * Under the dictionary for component metadata, add an entry for `providerlogs`:
        ```
        - name: providerlogs
          type: providerlogs
          metadata:
            topo_path: ""
            run_ids: []
        ```
    * Under the definition of runs, add `providerlogs` to the list for the `stop` phase; it should be listed **after** the `retrievedata` component. 
