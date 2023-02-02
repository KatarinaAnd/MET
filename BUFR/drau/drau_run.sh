#!/bin/bash -f
#$ -N wrapper
#$ -S /bin/bash
#$ -l h_rt=01:30:00
#$ -l h_vmem=24G
#$ -q research-el7.q
#$ -pe mpi 1
#$ -j y

source /modules/centos7/conda/Feb2021/etc/profile.d/conda.sh
conda activate secondenv

python /home/katarinana/work_desk/BUFR/drau/main_drau.py -c /home/katarinana/work_desk/BUFR/drau/drau_config.cfg -s 2023-01-23 -e 2023-01-23 -t buoy -a

