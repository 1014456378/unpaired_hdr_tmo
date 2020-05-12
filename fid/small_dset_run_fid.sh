#!/bin/bash

#source /cs/labs/raananf/yael_vinker/my_venv/bin/activate

#echo "number_of_images $1"
#python3.6 fid_score_small_dset.py "/cs/dataset/CelebA/Align & Cropped/img_align_celeba" \
#  "/cs/dataset/CelebA/Align & Cropped/img_align_celeba" \
#  --batch-size 100 --dims 768 --gpu "cuda" --number_of_images $1
#echo "number_of_images $1"
python3.6 fid_score_small_dset.py --path_real "/Users/yaelvinker/PycharmProjects/lab/fid/ldr" \
  --path_fake "/Users/yaelvinker/PycharmProjects/lab/fid/fake_jpg" \
  --batch-size 10 --dims 768 --gpu "cuda" --number_of_images 10 --format "jpg"

