#!/bin/bash

for i in $(seq 70 10 80); do
    for j in $(seq 0.1 0.1 0.1); do
        python evaluate.py val.candidate.captions_mscoco_init_pred-${i}_${j}.pkl \
        result_mscoco_init_pred-${i}_${j}.txt
    done
done