#!/bin/bash
change_random_seed=0
batch_size=16
num_epochs=500
G_lr=0.00001
D_lr=0.000005
model="unet"
con_operator="original_unet"
unet_norm="none"
last_layer="none"
use_xaviar=0
ssim_loss_factor=2
pyramid_loss=1
pyramid_weight_list="1,1,1"
data_root_npy="/cs/labs/raananf/yael_vinker/data/train/hdrplus_log1000"
data_root_ldr="/cs/labs/raananf/yael_vinker/data/train/ldr_flicker_dict"
test_dataroot_npy="/cs/labs/raananf/yael_vinker/data/test/hdrplus_log1000"
test_dataroot_original_hdr="/cs/labs/raananf/yael_vinker/data/test/tmqi_test_hdr"
test_dataroot_ldr="/cs/labs/raananf/yael_vinker/data/test/large_ldr_gray_dict"
result_dir_prefix="/cs/snapless/raananf/yael_vinker/02_06/run_all/results"
use_factorise_data=0
add_clipping=1
use_normalization=1
factor_coeff=1

echo "change_random_seed $change_random_seed"
echo "batch_size $batch_size"
echo "num_epochs $num_epochs"
echo "G_lr $G_lr"
echo "D_lr $D_lr"
echo "model $model"
echo "con_operator $con_operator"
echo "unet_norm $unet_norm"
echo "last_layer $last_layer"
echo "use_xaviar $use_xaviar"
echo "ssim_loss_factor $ssim_loss_factor"
echo "pyramid_loss $pyramid_loss"
echo "pyramid_weight_list $pyramid_weight_list"
echo "data_root_npy $data_root_npy"
echo "data_root_ldr $data_root_ldr"
echo "test_dataroot_npy $test_dataroot_npy"
echo "test_dataroot_original_hdr $test_dataroot_original_hdr"
echo "test_dataroot_ldr $test_dataroot_ldr"
echo "result_dir_prefix $result_dir_prefix"
echo "use_factorise_data $use_factorise_data"
echo "add_clipping $add_clipping"
echo "use_normalization $use_normalization"
echo "factor_coeff $factor_coeff"

sbatch --mem=4000m -c2 --gres=gpu:2 --time=2-0 train.sh $change_random_seed $batch_size $num_epochs $G_lr \
  $D_lr $model $con_operator $unet_norm $last_layer $use_xaviar $ssim_loss_factor $pyramid_loss \
  $pyramid_weight_list $data_root_npy $data_root_ldr $test_dataroot_npy $test_dataroot_original_hdr \
  $test_dataroot_ldr $result_dir_prefix $use_factorise_data $add_clipping $use_normalization $factor_coeff