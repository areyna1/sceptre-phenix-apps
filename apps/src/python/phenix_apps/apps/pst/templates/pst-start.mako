mkdir /home/ubuntu/snl-pstess
tar -xzvf /home/ubuntu/snl-pstess.tar.gz -C /home/ubuntu/snl-pstess

cp /home/ubuntu/pst_solver.m /home/ubuntu/snl-pstess/data
cp /home/ubuntu/get_path.m /home/ubuntu/snl-pstess/pstess
cp /home/ubuntu/s_simu.m /home/ubuntu/snl-pstess/pstess
cp /home/ubuntu/publishPoints.txt /home/ubuntu/snl-pstess/pstess

mkdir -p /etc/sceptre/log

/usr/local/MATLAB/R2022b/bin/matlab -nodisplay -nosplash -nodesktop -batch "mex /home/ubuntu/modelHooks.c -R2018a -outdir /home/ubuntu/snl-pstess/pstess"

/usr/local/MATLAB/R2022b/bin/matlab -nodisplay -nosplash -nodesktop -batch "run('/home/ubuntu/snl-pstess/pstess/s_simu.m');exit;" 2>&1 > /etc/sceptre/log/solver.log &

sleep 60

bennu-simulink-provider --server-endpoint '${server_endpoint}' --publish-endpoint '${publish_endpoint}' --debug 'true' 2>&1 > /etc/sceptre/log/provider.log &
