#!/bin/bash

change_random_seed=0
batch_size=16
num_epochs=325
G_lr=0.00001
D_lr=0.00001
lr_decay_step=50
model="unet"
con_operator="square_and_square_root"
unet_norm="none"
use_xaviar=1
g_activation="relu"
d_pretrain_epochs=50

# ====== DATASET ======
#data_root_npy="/cs/snapless/raananf/yael_vinker/data/new_data_oct/train/hdrplus_new_f_min_log_factor1.0_crop"
data_root_npy="/cs/snapless/raananf/yael_vinker/data/new_data_crop_fix/train/"
data_root_ldr="/cs/snapless/raananf/yael_vinker/data/div2k_large/train_half2"
test_dataroot_npy="/cs/snapless/raananf/yael_vinker/data/new_data_crop_fix/test"
test_dataroot_original_hdr="/cs/labs/raananf/yael_vinker/data/test/new_test_hdr"
test_dataroot_ldr="/cs/snapless/raananf/yael_vinker/data/div2k_large/test_half"
f_factor_path="none"
gamma_log=10
use_new_f=0
factor_coeff=0.1

add_frame=0
input_dim=1
add_clipping=0
apply_exp=0

use_factorise_data=1

use_normalization=0
last_layer="sigmoid"
custom_sig_factor=3
d_model="multiLayerD_simpleD"
num_D=3
d_last_activation="sigmoid"
d_down_dim=16
d_norm="none"
milestones="200"
epoch_to_save=40
final_epoch=320
d_nlayers=3

# =================== LOSS ==================

std_method="gamma_factor_loss_bilateral"

intensity_epsilon=0.00001
apply_intensity_loss_laplacian_weights=0

loss_g_d_factor=1
train_with_D=1
multi_scale_D=0

ssim_window_size=5
struct_method="gamma_ssim"
ssim_loss_factor=1
pyramid_weight_list="1,1,1"

alpha=0.5
bilateral_sigma_r=0.07
apply_intensity_loss=0
std_pyramid_weight_list="0"
std_mul_max=0

mu_loss_factor=0
mu_pyramid_weight_list="0"
normalization="bugy_max_normalization"
max_stretch=1
min_stretch=0
bilateral_mu=1
blf_input="log"
blf_alpha=0.8

enhance_detail=0
stretch_g="none"
g_doubleConvTranspose=1
d_fully_connected=0
simpleD_maxpool=0

adv_weight_list="1,1,0.1"
data_trc="min_log"

manual_d_training=0
d_weight_mul_mode="double"
strong_details_D_weights="4,4,4"
basic_details_D_weights="0.5,0.5,0.5"

result_dir_prefix="/cs/labs/raananf/yael_vinker/Oct/10_20/results_10_20/padding_test/"
use_contrast_ratio_f=0
f_factor_path="/cs/labs/raananf/yael_vinker/data/new_lum_est_hist/train_valid/valid_hist_dict_20_bins.npy"
use_hist_fit=1
f_train_dict_path="/cs/labs/raananf/yael_vinker/data/new_lum_est_hist/fix_lum_hist/dng_hist_20_bins_all_fix.npy"

pyramid_weight_list_lst=("0.2,0.4,0.8")
pyramid_weight_list="0.2,0.4,0.8"

change_random_seed_lst=(0)
change_random_seed=0

adv_weight_list_lst=("2,2,1")
adv_weight_list="2,2,1"

factor_coeff_lst=(0.1)
factor_coeff=0.1

fid_res_path="/cs/labs/raananf/yael_vinker/Oct/10_20/fid_res/"

bilinear_lst=(0 0 0 0 1)
d_padding_lst=(0 1 1 1 1)
g_doubleConvTranspose_lst=(1 1 1 0 0)
g_padding_lst=("constant" "replicate" "reflect" "replicate" "replicate")
test_names=("d_no_padding" "g_replicate" "g_reflect" "no_doubleconvTranspose_and_convTrans" \
            "no_doubleconvTranspose_and_bilinear")
convtranspose_kernel=2
final_shape_addition=0

for ((i = 0; i < ${#bilinear_lst[@]}; ++i)); do

  bilinear="${bilinear_lst[i]}"
  d_padding="${d_padding_lst[i]}"
  padding="${g_padding_lst[i]}"
  g_doubleConvTranspose="${g_doubleConvTranspose_lst[i]}"
  test_name="${test_names[i]}"

  echo "======================================================"
  echo "tests_name $test_name"
  echo "bilinear $bilinear"
  echo "d_padding $d_padding"
  echo "padding $padding"
  echo "g_doubleConvTranspose $g_doubleConvTranspose"

  sbatch --mem=8000m -c2 --gres=gpu:1 --time=2-0 train.sh \
    $change_random_seed $batch_size $num_epochs \
    $G_lr $D_lr $model $con_operator $use_xaviar \
    $loss_g_d_factor $train_with_D $ssim_loss_factor $pyramid_weight_list $apply_intensity_loss \
    $intensity_epsilon $std_pyramid_weight_list $mu_loss_factor $mu_pyramid_weight_list \
    $data_root_npy $data_root_ldr $test_dataroot_npy $test_dataroot_original_hdr $test_dataroot_ldr \
    $result_dir_prefix $use_factorise_data $factor_coeff $add_clipping $use_normalization \
    $normalization $last_layer $d_model $d_down_dim $d_norm $milestones $add_frame $input_dim \
    $apply_intensity_loss_laplacian_weights $std_method $alpha $struct_method \
    $bilateral_sigma_r $apply_exp $f_factor_path $gamma_log $custom_sig_factor \
    $epoch_to_save $final_epoch $bilateral_mu $max_stretch $min_stretch $ssim_window_size \
    $use_new_f $blf_input $blf_alpha $std_mul_max $multi_scale_D $g_activation $d_last_activation \
    $lr_decay_step $d_nlayers $d_pretrain_epochs $num_D $unet_norm $enhance_detail \
    $stretch_g $g_doubleConvTranspose $d_fully_connected $simpleD_maxpool $data_trc $adv_weight_list \
    $manual_d_training $d_weight_mul_mode $strong_details_D_weights $basic_details_D_weights $use_contrast_ratio_f \
    $use_hist_fit $f_train_dict_path $fid_res_path $bilinear $d_padding $padding $convtranspose_kernel $final_shape_addition
  echo "======================================================"
done