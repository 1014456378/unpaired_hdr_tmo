import os

import imageio
import matplotlib.pyplot as plt
import numpy as np
import torch
import tranforms as custom_transform
# from old_files import TMQI
from utils import printer
import tranforms
import utils.data_loader_util as data_loader_util
import utils.hdr_image_util as hdr_image_util
import utils.image_quality_assessment_util as image_quality_assessment_util
import utils.plot_util as plot_util
import data_generator.create_dng_npy_data as create_dng_npy_data
from utils.ProcessedDatasetFolder import hdr_windows_loader

class Tester:
    def __init__(self, device, loss_g_d_factor_, ssim_loss_g_factor_, log_factor_, args):
        self.args = args
        self.to_crop = args.add_frame
        self.test_data_loader_npy, self.test_data_loader_ldr = \
            data_loader_util.load_data(args.test_dataroot_npy, args.test_dataroot_ldr, args.batch_size, args.add_frame,
                                       title="test", normalization=args.normalization, use_c3=args.use_c3_in_ssim,
                                       apply_wind_norm=args.apply_wind_norm, device=args.device)
        self.accG_counter, self.accDreal_counter, self.accDfake_counter = 0, 0, 0
        self.G_accuracy_test, self.D_accuracy_real_test, self.D_accuracy_fake_test = [], [], []
        self.real_label, self.fake_label = 1, 0
        self.device = device
        self.test_D_losses, self.test_D_loss_fake, self.test_D_loss_real = [], [], []
        self.test_G_losses_d, self.test_G_loss_ssim = [], []
        self.ssim_loss_g_factor = ssim_loss_g_factor_
        self.loss_g_d_factor = loss_g_d_factor_
        self.test_num_iter = 0
        self.Q_arr, self.S_arr, self.N_arr = [], [], []
        self.log_factor = log_factor_
        self.test_original_hdr_images = self.load_original_test_hdr_images(args.test_dataroot_original_hdr)
        self.max_normalization = custom_transform.MaxNormalization()
        self.min_max_normalization = custom_transform.MinMaxNormalization()
        self.clip_transform = custom_transform.Clip()
        self.apply_wind_norm = args.apply_wind_norm
        self.wind_size = args.ssim_window_size

    def load_original_test_hdr_images(self, root):
        original_hdr_images = []
        counter = 1
        for img_name in os.listdir(root):
            im_path = os.path.join(root, img_name)
            rgb_img, gray_im_log = create_dng_npy_data.hdr_preprocess(im_path, self.args.use_factorise_data,
                                                                      self.args.use_factorise_gamma_data,
                                                                      self.args.factor_coeff, reshape=True,
                                                                      window_tone_map=self.args.window_tm_data)
            rgb_img, gray_im_log = tranforms.hdr_im_transform(rgb_img), tranforms.hdr_im_transform(gray_im_log)
            if self.to_crop:
                gray_im_log = data_loader_util.add_frame_to_im(gray_im_log)
            original_hdr_images.append({'im_name': str(counter),
                                        'im_hdr_original': rgb_img,
                                        'im_log_normalize_tensor': gray_im_log,
                                        'epoch': 0})
            # if counter == 1 or counter == 2:
            #     self.get_test_image_special_factor(im_path, original_hdr_images, counter)

            # plt.imshow(gray_im_log.clone().permute(1, 2, 0).detach().cpu().squeeze().numpy(), cmap='gray')
            # title = "max %.4f min %.4f mean %.4f" % (gray_im_log.max().item(),gray_im_log.min().item(), gray_im_log.mean().item())
            # plt.title(title, fontSize=8)
            # plt.show()
            counter += 1
        return original_hdr_images

    def get_test_image_special_factor(self, im_path, original_hdr_images, counter):
        special_factors = [self.args.factor_coeff * 0.01, 5, 10]
        for f in special_factors:
            rgb_img, gray_im_log = create_dng_npy_data.hdr_preprocess_change_f(im_path, self.args, f, reshape=True)
            rgb_img, gray_im_log = tranforms.hdr_im_transform(rgb_img), tranforms.hdr_im_transform(gray_im_log)

            # im_hdr_original_to_save = gray_im_log.clone().permute(1, 2, 0).detach().cpu().numpy()
            # self.save_best_acc_result_imageio_temo("out", str(counter) + "_" + str(f), im_hdr_original_to_save, 0, color='original')
            if self.to_crop:
                gray_im_log = data_loader_util.add_frame_to_im(gray_im_log)
            original_hdr_images.append({'im_name': str(counter) + "_" + str(f),
                                        'im_hdr_original': rgb_img,
                                        'im_log_normalize_tensor': gray_im_log,
                                        'epoch': 0})

    def update_test_loss(self, netD, criterion, ssim_loss, b_size, num_epochs, first_b_tonemap, fake, hdr_input, epoch):
        self.accG_counter, self.accDreal_counter, self.accDfake_counter = 0, 0, 0
        with torch.no_grad():
            test_D_output_on_real = netD(first_b_tonemap.detach()).view(-1)
            self.accDreal_counter += (test_D_output_on_real > 0.5).sum().item()

            real_label = torch.full(test_D_output_on_real.shape, self.real_label, device=self.device)
            test_errD_real = criterion(test_D_output_on_real, real_label)
            self.test_D_loss_real.append(test_errD_real.item())

            fake_label = torch.full(test_D_output_on_real.shape, self.fake_label, device=self.device)
            output_on_fake = netD(fake.detach()).view(-1)
            self.accDfake_counter += (output_on_fake <= 0.5).sum().item()

            test_errD_fake = criterion(output_on_fake, fake_label)
            test_loss_D = test_errD_real + test_errD_fake
            self.test_D_loss_fake.append(test_errD_fake.item())
            self.test_D_losses.append(test_loss_D.item())

            # output_on_fakake = self.netD(fake.detach()).view(-1)
            self.accG_counter += (output_on_fake > 0.5).sum().item()
            # if self.loss_g_d_factor != 0:
            test_errGd = criterion(output_on_fake, real_label)
            self.test_G_losses_d.append(test_errGd.item())
            if self.ssim_loss_g_factor != 0:
                if self.to_crop:
                    hdr_input = data_loader_util.crop_input_hdr_batch(hdr_input)
                fake_rgb_n = fake + 1
                hdr_input_rgb_n = hdr_input + 1
                test_errGssim = self.ssim_loss_g_factor * (1 - ssim_loss(fake_rgb_n, hdr_input_rgb_n))
                self.test_G_loss_ssim.append(test_errGssim.item())
            self.update_accuracy()
            printer.print_test_epoch_losses_summary(num_epochs, epoch, test_loss_D, test_errGd, self.accDreal_test,
                                                    self.accDfake_test, self.accG_test)

    @staticmethod
    def get_fake_test_images(first_b_hdr, netG):
        with torch.no_grad():
            fake = netG(first_b_hdr.detach())
            return fake

    def update_accuracy(self):
        len_hdr_test_dset = len(self.test_data_loader_npy.dataset)
        len_ldr_test_dset = len(self.test_data_loader_ldr.dataset)
        self.accG_test = self.accG_counter / len_hdr_test_dset
        self.accDreal_test = self.accDreal_counter / len_ldr_test_dset
        self.accDfake_test = self.accDfake_counter / len_ldr_test_dset
        self.G_accuracy_test.append(self.accG_test)
        self.D_accuracy_real_test.append(self.accDreal_test)
        self.D_accuracy_fake_test.append(self.accDfake_test)

    def save_test_loss(self, epoch, out_dir):
        acc_path = os.path.join(out_dir, "accuracy")
        loss_path = os.path.join(out_dir, "loss_plot")
        plot_util.plot_general_losses(self.test_G_losses_d, self.test_G_loss_ssim,
                                      self.test_D_loss_fake, self.test_D_loss_real,
                                      "TEST epoch loss = " + str(epoch), self.test_num_iter, loss_path,
                                      (self.loss_g_d_factor != 0), (self.ssim_loss_g_factor != 0))

        plot_util.plot_general_accuracy(self.G_accuracy_test, self.D_accuracy_fake_test, self.D_accuracy_real_test,
                                        "TEST epoch acc = " + str(epoch), epoch, acc_path)

    def save_test_images(self, epoch, out_dir, input_images_mean, netD, netG, criterion, ssim_loss, num_epochs):
        out_dir = os.path.join(out_dir, "result_images")
        new_out_dir = os.path.join(out_dir, "images_epoch=" + str(epoch))

        if not os.path.exists(new_out_dir):
            os.mkdir(new_out_dir)

        self.test_num_iter += 1
        test_real_batch = next(iter(self.test_data_loader_ldr))
        test_real_first_b = test_real_batch["input_im"].to(self.device)

        test_hdr_batch = next(iter(self.test_data_loader_npy))
        # test_hdr_batch_image = test_hdr_batch[params.image_key].to(self.device)
        test_hdr_batch_image = test_hdr_batch["input_im"].to(self.device)
        printer.print_g_progress_tensor(test_hdr_batch_image, "from test")
        fake = self.get_fake_test_images(test_hdr_batch_image, netG)
        printer.print_g_progress_tensor(fake, "from test res")
        test_real_batch_frame = data_loader_util.add_frame_to_im_batch(test_real_batch["input_im"])
        printer.print_g_progress_tensor(test_real_batch_frame, "ldr from test")
        # fake_ldr = self.get_fake_test_images(test_real_batch_frame.to(self.device), netG)
        # printer.print_g_progress_tensor(fake_ldr, "fake ldr from test")
        plot_util.save_groups_images(test_hdr_batch, test_real_batch, fake, fake,
                                     new_out_dir, len(self.test_data_loader_npy.dataset), epoch,
                                     input_images_mean)
        # self.update_test_loss(netD, criterion, ssim_loss, test_real_first_b.size(0), num_epochs,
        #                       test_real_first_b, fake, test_hdr_batch_image, epoch)

    def save_best_acc_result_imageio(self, out_dir, im_and_q, im, epoch, color):
        file_name = im_and_q["im_name"] + "_epoch_" + str(epoch) + "_" + color + ".png"
        im = hdr_image_util.to_0_1_range(im)
        im = (im * 255).astype('uint8')
        imageio.imwrite(os.path.join(out_dir, file_name), im, format='PNG-FI')

    def save_best_acc_result_imageio_temo(self, out_dir, im_and_q, im, epoch, color):
        file_name = im_and_q + "_epoch_" + str(epoch) + "_" + color + ".png"
        im = hdr_image_util.to_0_1_range(im)
        im = (im * 255).astype('uint8')
        imageio.imwrite(os.path.join(out_dir, file_name), im, format='PNG-FI')

    def save_result_imageio_no_stretch(self, out_dir, im_and_q, im, epoch, color):
        file_name = im_and_q["im_name"] + "_epoch_" + str(epoch) + "_" + color + ".png"
        im = (im * 255).astype('uint8')
        im = np.clip(im, 0, 255)
        imageio.imwrite(os.path.join(out_dir, file_name), im, format='PNG-FI')

    def save_images_for_model(self, netG, out_dir, epoch):
        out_dir = os.path.join(out_dir, "model_results", str(epoch))
        if not os.path.exists(out_dir):
            os.mkdir(out_dir)
            print("Directory ", out_dir, " created")
        with torch.no_grad():
            for im_and_q in self.test_original_hdr_images:
                im_hdr_original = im_and_q['im_hdr_original']
                im_log_normalize_tensor = im_and_q['im_log_normalize_tensor'].to(self.device)
                printer.print_g_progress(im_log_normalize_tensor, "tester")
                if self.apply_wind_norm:
                    gray_original_im = hdr_image_util.to_gray_tensor(im_hdr_original)
                    gray_original_im_norm = gray_original_im / gray_original_im.max()
                    im_log_normalize_tensor = hdr_windows_loader(self.wind_size, gray_original_im_norm,
                                                                 im_log_normalize_tensor)
                fake = netG(im_log_normalize_tensor.unsqueeze(0).detach())
                printer.print_g_progress(fake, "fake")
                fake_im_color = hdr_image_util.back_to_color_batch(im_hdr_original.unsqueeze(0), fake)
                fake_im_color_numpy = fake_im_color[0].clone().permute(1, 2, 0).detach().cpu().numpy()
                self.save_best_acc_result_imageio(out_dir, im_and_q, fake_im_color_numpy, epoch, color='rgb')
                fake_im_gray = torch.squeeze(fake[0], dim=0)
                fake_im_gray_numpy = fake_im_gray.clone().detach().cpu().numpy()
                self.save_result_imageio_no_stretch(out_dir, im_and_q, fake_im_gray_numpy, epoch, color='gray_source')
                self.save_best_acc_result_imageio(out_dir, im_and_q, fake_im_gray_numpy, epoch, color='gray')

