from math import exp

import numpy as np
import torch
import torch.nn.functional as F
from torch.autograd import Variable

from utils import params, data_loader_util
import torch
from torch import nn

# =======================================
# ============= Classes ===============
# =======================================
class OUR_CUSTOM_SSIM_PYRAMID(torch.nn.Module):
    def __init__(self, pyramid_weight_list, window_size=11, pyramid_pow=False, use_c3=False,
                 apply_sig_mu_ssim=False, struct_method="our_custom_ssim", std_norm_factor=1):
        super(OUR_CUSTOM_SSIM_PYRAMID, self).__init__()
        self.window_size = window_size
        self.channel = 1
        self.window = create_window(window_size, self.channel)
        self.mse_loss = torch.nn.MSELoss()
        self.pyramid_weight_list = pyramid_weight_list
        self.pyramid_pow = pyramid_pow
        self.use_c3 = use_c3
        self.apply_sig_mu_ssim = apply_sig_mu_ssim
        self.struct_methods = {
            "hdr_ssim": our_custom_ssim,
            "gamma_ssim": our_custom_ssim
        }
        self.struct_method = struct_method
        if struct_method not in ["hdr_ssim", "gamma_ssim", "div_ssim"]:
            assert 0, "Unsupported struct_method"
        self.struct_loss = self.struct_methods[struct_method]
        self.std_norm_factor = std_norm_factor

    def forward(self, fake, hdr_input_original_gray_norm, hdr_input):
        (_, channel, _, _) = fake.size()
        if channel == self.channel and self.window.data.type() == fake.data.type():
            window = self.window
        else:
            window = create_window(self.window_size, channel)

            if fake.is_cuda:
                window = window.cuda(fake.get_device())
            window = window.type_as(fake)

            self.window = window
            self.channel = channel
        if self.struct_method == "gamma_ssim":
            hdr_input = data_loader_util.crop_input_hdr_batch(hdr_input)
            return our_custom_ssim_pyramid(fake, hdr_input, window, self.window_size, channel,
                                           self.pyramid_weight_list,
                                           self.mse_loss, self.use_c3, self.apply_sig_mu_ssim)
        elif self.struct_method == "hdr_ssim":
            return our_custom_ssim_pyramid(fake, hdr_input_original_gray_norm, window, self.window_size,
                                           channel, self.pyramid_weight_list,
                                           self.mse_loss, self.use_c3, self.apply_sig_mu_ssim)
        elif self.struct_method == "div_ssim":
            return our_custom_ssim_pyramid_div(fake, hdr_input_original_gray_norm, window, self.window_size,
                                           channel, self.pyramid_weight_list,
                                           self.mse_loss, self.use_c3, self.apply_sig_mu_ssim)


class IntensityLoss(torch.nn.Module):
    def __init__(self, epsilon, pyramid_weight_list, alpha=1, std_method="std"):
        super(IntensityLoss, self).__init__()
        self.epsilon = epsilon
        self.window = create_window(5, 1)
        # self.window = get_gaussian_kernel2(5, 1)
        self.pyramid_weight_list = pyramid_weight_list
        self.mse_loss = torch.nn.MSELoss()
        self.std_methods = {
            "std": std_loss,
            "std_mu_fake": std_loss_mu_fake,
            "std_mu_gamma": std_loss_mu_gamma,
            "std_bilateral": std_loss_bilateral,
            "std_mu_gamma_mu_hdr": std_loss_mu_gamma_mu_hdr
        }
        self.std_loss = self.std_methods[std_method]
        self.alpha = alpha
        self.mse_loss = torch.nn.MSELoss()

    def forward(self, fake, hdr_input, hdr_original_im, r_weights=None):
        hdr_input = data_loader_util.crop_input_hdr_batch(hdr_input)
        if r_weights:
            self.std_loss = self.std_methods["std_bilateral"]
        cur_weights = None
        ssim_loss_list = []
        for i in range(len(self.pyramid_weight_list)):
            if r_weights:
                cur_weights = r_weights[i]
            ssim_loss_list.append(self.pyramid_weight_list[i] *
                                  self.std_loss(self.window, fake, hdr_input, hdr_original_im,
                                                self.epsilon, self.mse_loss,
                                                self.alpha, cur_weights))
            fake = F.interpolate(fake, scale_factor=0.5, mode='bicubic', align_corners=False)
            hdr_input = F.interpolate(hdr_input, scale_factor=0.5, mode='bicubic', align_corners=False)
        return torch.sum(torch.stack(ssim_loss_list))


class IntensityLossLaplacian(torch.nn.Module):
    def __init__(self, epsilon, pyramid_weight_list):
        super(IntensityLossLaplacian, self).__init__()
        self.epsilon = epsilon
        self.gaussian_kernel = get_gaussian_kernel(window_size=5, channel=1)
        self.laplacian_kernel = get_laplacian_kernel(kernel_size=5)
        self.pyramid_weight_list = pyramid_weight_list
        self.mse_loss = torch.nn.MSELoss()
        self.kernel_size = 5

    def forward(self, fake, gamma_input):
        gamma_input = data_loader_util.crop_input_hdr_batch(gamma_input)
        ssim_loss_list = []
        for i in range(len(self.pyramid_weight_list)):
            ssim_loss_list.append(self.pyramid_weight_list[i] *
                                  std_loss_laplac(self.gaussian_kernel, self.laplacian_kernel,
                                                  fake, self.epsilon, gamma_input))
            fake = F.interpolate(fake, scale_factor=0.5, mode='bicubic', align_corners=False)
        return torch.sum(torch.stack(ssim_loss_list))


class MuLoss(torch.nn.Module):
    def __init__(self, pyramid_weight_list):
        super(MuLoss, self).__init__()
        self.window = create_window(5, 1)
        # self.window = get_gaussian_kernel2(5, 1)
        self.pyramid_weight_list = pyramid_weight_list
        self.mse_loss = torch.nn.MSELoss()
        self.mu_loss_method = mu_loss

    def forward(self, fake, img2, hdr_input, r_weights):
        hdr_input = data_loader_util.crop_input_hdr_batch(hdr_input)
        if r_weights:
            self.mu_loss_method = mu_loss_bilateral
        cur_weights = None
        mu_loss_list = []
        for i in range(len(self.pyramid_weight_list)):
            if r_weights:
                cur_weights = r_weights[i]
            mu_loss_list.append(self.pyramid_weight_list[i] * self.mu_loss_method(self.window, fake, hdr_input,
                                                                      self.mse_loss, cur_weights))
            fake = F.interpolate(fake, scale_factor=0.5, mode='bicubic', align_corners=False)
            hdr_input = F.interpolate(hdr_input, scale_factor=0.5, mode='bicubic', align_corners=False)
        return torch.sum(torch.stack(mu_loss_list))


class OUR_SIGMA_SSIM(torch.nn.Module):
    def __init__(self, window_size=11):
        super(OUR_SIGMA_SSIM, self).__init__()
        self.window_size = window_size
        self.channel = 1
        self.window = create_window(window_size, self.channel)
        self.mse_loss = torch.nn.MSELoss()

    def forward(self, img1, img2):
        (_, channel, _, _) = img1.size()

        if channel == self.channel and self.window.data.type() == img1.data.type():
            window = self.window
        else:
            window = create_window(self.window_size, channel)

            if img1.is_cuda:
                window = window.cuda(img1.get_device())
            window = window.type_as(img1)

            self.window = window
            self.channel = channel

        return our_custom_sigma_loss(img1, img2, window, self.window_size, channel, self.mse_loss)


# =======================================
# ========== Loss Functions =============
# =======================================
def our_custom_ssim(img1, img2, window, window_size, channel, mse_loss, use_c3, apply_sig_mu_ssim):
    window = window / window.sum()
    mu1 = F.conv2d(img1, window, padding=window_size // 2, groups=channel)
    mu2 = F.conv2d(img2, window, padding=window_size // 2, groups=channel)

    mu1_sq = mu1.pow(2)
    mu2_sq = mu2.pow(2)

    sigma1_sq = F.conv2d(img1 * img1, window, padding=window_size // 2, groups=1) - mu1_sq
    sigma2_sq = F.conv2d(img2 * img2, window, padding=window_size // 2, groups=1) - mu2_sq

    std1 = torch.pow(torch.max(sigma1_sq, torch.zeros_like(sigma1_sq)) + params.epsilon2, 0.5)
    std2 = torch.pow(torch.max(sigma2_sq, torch.zeros_like(sigma2_sq)) + params.epsilon2, 0.5)

    mu1 = mu1.unsqueeze(dim=4).expand(-1, -1, -1, -1, window_size * window_size)
    mu2 = mu2.unsqueeze(dim=4).expand(-1, -1, -1, -1, window_size * window_size)

    std1 = std1.unsqueeze(dim=4).expand(-1, -1, -1, -1, window_size * window_size)
    std2 = std2.unsqueeze(dim=4).expand(-1, -1, -1, -1, window_size * window_size)

    img1 = get_im_as_windows(img1, window_size)
    img2 = get_im_as_windows(img2, window_size)
    img1 = (img1 - mu1)
    img1 = img1 / (std1 + params.epsilon2)
    img2 = (img2 - mu2)
    img2 = (img2) / (std2 + params.epsilon2)
    return mse_loss(img1, img2)


def our_custom_ssim2(img1, img2, window, window_size, channel, mse_loss, use_c3, apply_sig_mu_ssim):
    window = window / window.sum()

    mu1 = F.conv2d(img1, window, padding=window_size // 2, groups=channel)
    mu2 = F.conv2d(img2, window, padding=window_size // 2, groups=channel)

    mu1_sq = mu1.pow(2)
    mu2_sq = mu2.pow(2)

    sigma1_sq = F.conv2d(img1 * img1, window, padding=window_size // 2, groups=1) - mu1_sq
    sigma2_sq = F.conv2d(img2 * img2, window, padding=window_size // 2, groups=1) - mu2_sq

    std1 = torch.pow(torch.max(sigma1_sq, torch.zeros_like(sigma1_sq)) + params.epsilon2, 0.5)
    std2 = torch.pow(torch.max(sigma2_sq, torch.zeros_like(sigma2_sq)) + params.epsilon2, 0.5)

    mu1 = mu1.unsqueeze(dim=4).expand(-1, -1, -1, -1, window_size * window_size)
    mu2 = mu2.unsqueeze(dim=4).expand(-1, -1, -1, -1, window_size * window_size)

    std1 = std1.unsqueeze(dim=4).expand(-1, -1, -1, -1, window_size * window_size)
    std2 = std2.unsqueeze(dim=4).expand(-1, -1, -1, -1, window_size * window_size)

    img1 = get_im_as_windows(img1, window_size)
    img2 = get_im_as_windows(img2, window_size)
    img1 = (img1 - mu1)
    img1 = img1 / (std1 + params.epsilon2)
    img2 = (img2 - mu2)
    img2 = (img2) / (std2 + params.epsilon2)
    ones = torch.ones(img2.shape)
    if img2.is_cuda:
        ones = ones.cuda(img2.get_device())
    ones = ones.type_as(img2)
    return mse_loss(ones / (img1 + params.epsilon2), ones / (img2 + params.epsilon2))


def struct_loss_laplac(gaussian_kernel, laplacian_kernel, fake, epsilon, gamma_input):
    b, c, h, w = fake.shape
    ones = torch.ones(fake.shape)
    if fake.is_cuda:
        gaussian_kernel = gaussian_kernel.cuda(fake.get_device())
        laplacian_kernel = laplacian_kernel.cuda(fake.get_device())
        ones = ones.cuda(fake.get_device())
    gaussian_kernel = gaussian_kernel.type_as(fake)
    laplacian_kernel = laplacian_kernel.type_as(fake)
    laplacian_kernel = laplacian_kernel.repeat(c, 1, 1, 1)
    ones = ones.type_as(fake)
    mu1 = F.conv2d(fake, gaussian_kernel, padding=5 // 2, groups=1)
    gamma_input_gaussian = F.conv2d(gamma_input, gaussian_kernel, padding=5 // 2, groups=1)
    laplacian_res = F.conv2d(gamma_input_gaussian, laplacian_kernel, padding=5 // 2, stride=1, groups=c)
    laplacian_res[laplacian_res < 0] = 0
    laplacian_res = laplacian_res.max() - (laplacian_res)
    laplacian_res = laplacian_res ** 2

    import matplotlib.pyplot as plt
    plt.imshow(laplacian_res[1,0].numpy(), cmap='gray')
    plt.show()
    # compute std
    mu1_sq = mu1.pow(2)
    sigma1_sq = F.conv2d(fake * fake, gaussian_kernel, padding=5 // 2, groups=1) - mu1_sq
    std1 = torch.pow(torch.max(sigma1_sq, torch.zeros_like(sigma1_sq)) + 1e-10, 0.5)
    res = laplacian_res * (ones - (std1[0, 0] / (std1[0, 0] + epsilon)))
    return res.mean()


def our_custom_sigma_loss(img1, img2, window, window_size, channel, mse_loss):
    window = window / window.sum()
    mu1 = F.conv2d(img1, window, padding=window_size // 2, groups=channel)
    mu2 = F.conv2d(img2, window, padding=window_size // 2, groups=channel)

    mu1_sq = mu1.pow(2)
    mu2_sq = mu2.pow(2)

    sigma1_sq = F.conv2d(img1 * img1, window, padding=window_size // 2, groups=1) - mu1_sq
    sigma2_sq = F.conv2d(img2 * img2, window, padding=window_size // 2, groups=1) - mu2_sq

    std1 = torch.pow(torch.max(sigma1_sq, torch.zeros_like(sigma1_sq)) + params.epsilon, 0.5)
    std2 = torch.pow(torch.max(sigma2_sq, torch.zeros_like(sigma2_sq)) + params.epsilon, 0.5)
    std2_normalise = std2 / (torch.max(mu2, torch.zeros_like(sigma2_sq) + params.epsilon))
    std2_normalise = torch.pow(std2_normalise, 0.8)
    # std2 = torch.pow(std2, 0.85)
    return mse_loss(std1, std2_normalise)


def our_custom_ssim_pyramid(img1, img2, window, window_size, channel, pyramid_weight_list,
                            mse_loss, use_c3, apply_sig_mu_ssim):
    ssim_loss_list = []
    for i in range(len(pyramid_weight_list)):
        ssim_loss_list.append(pyramid_weight_list[i] * our_custom_ssim(img1, img2, window, window_size,
                                                                       channel, mse_loss, use_c3, apply_sig_mu_ssim))

        img1 = F.interpolate(img1, scale_factor=0.5, mode='bicubic', align_corners=False)
        img2 = F.interpolate(img2, scale_factor=0.5, mode='bicubic', align_corners=False)
    return torch.sum(torch.stack(ssim_loss_list))


def our_custom_ssim_pyramid_div(img1, img2, window, window_size, channel, pyramid_weight_list,
                            mse_loss, use_c3, apply_sig_mu_ssim):
    ssim_loss_list = []
    for i in range(len(pyramid_weight_list)):
        ssim_loss_list.append(pyramid_weight_list[i] * our_custom_ssim2(img1, img2, window, window_size,
                                                                       channel, mse_loss, use_c3, apply_sig_mu_ssim))

        img1 = F.interpolate(img1, scale_factor=0.5, mode='bicubic', align_corners=False)
        img2 = F.interpolate(img2, scale_factor=0.5, mode='bicubic', align_corners=False)
    return torch.sum(torch.stack(ssim_loss_list))


def std_loss(window, fake, gamma_hdr, hdr_original_im, epsilon, mse_loss=None, alpha=1, r_weights=None):
    ones = torch.ones(fake.shape)
    # print("ones", ones.shape)
    if fake.is_cuda:
        window = window.cuda(fake.get_device())
        ones = ones.cuda(fake.get_device())
    window = window.type_as(fake)
    ones = ones.type_as(fake)
    window = window / window.sum()
    mu1 = F.conv2d(fake, window, padding=5 // 2, groups=1)
    mu1_sq = mu1.pow(2)
    sigma1_sq = F.conv2d(fake * fake, window, padding=5 // 2, groups=1) - mu1_sq
    std1 = torch.pow(torch.max(sigma1_sq, torch.zeros_like(sigma1_sq)) + 1e-10, 0.5)
    # print("std1", std1.shape)
    # print("std1[0,0]", std1[0,0].shape)
    res = ones - (std1 / (std1 + epsilon))
    # print("res", res.shape)
    return res.mean()


def std_loss_bilateral(window, fake, gamma_hdr, hdr_original_im, epsilon, mse_loss=None, alpha=1, r_weights=None, wind_size=5):
    ones = torch.ones(fake.shape)
    if fake.is_cuda:
        window = window.cuda(fake.get_device())
        ones = ones.cuda(fake.get_device())
    window = window.type_as(fake)
    window = window.reshape(1, wind_size * wind_size, 1, 1).contiguous()
    distance_gause = window.expand(1, -1, r_weights.shape[2], r_weights.shape[3])
    weights_map = distance_gause * r_weights
    weights_map_sum = torch.sum(weights_map, axis=1).unsqueeze(dim=1)

    fake_windows = get_im_as_windows(fake, wind_size)
    fake_windows = fake_windows.squeeze(dim=1)
    fake_windows = fake_windows.permute(0, 3, 1, 2)
    fake_bf = torch.sum(fake_windows * weights_map, axis=1).unsqueeze(dim=1) / weights_map_sum
    fake_bf = fake_bf.expand(-1, wind_size * wind_size, -1, -1)

    fake_minus_mean_sq = (fake_windows - fake_bf) * (fake_windows - fake_bf)
    # mu1_sq = fake_bf.pow(2)
    # sigma1_sq = F.conv2d(fake * fake, window, padding=5 // 2, groups=1) - mu1_sq
    sigma1_sq = torch.sum(fake_minus_mean_sq * weights_map, axis=1).unsqueeze(dim=1) / weights_map_sum
    std1 = torch.pow(torch.max(sigma1_sq, torch.zeros_like(sigma1_sq)) + params.epsilon, 0.5)
    res = ones - (std1 / (std1 + epsilon))
    return res.mean()


def std_loss_mu_fake(window, fake, gamma_hdr, hdr_original_im, epsilon, mse_loss, alpha, r_weights=None):
    if fake.is_cuda:
        window = window.cuda(fake.get_device())
    window = window.type_as(fake)
    window = window / window.sum()
    mu1 = F.conv2d(fake, window, padding=5 // 2, groups=1)
    mu1_sq = mu1.pow(2)
    sigma1_sq = F.conv2d(fake * fake, window, padding=5 // 2, groups=1) - mu1_sq
    std1 = torch.pow(torch.max(sigma1_sq, torch.zeros_like(sigma1_sq)) + 1e-10, 0.5)
    return mse_loss(std1, alpha * mu1)


def std_loss_mu_gamma(window, fake, gamma_hdr, hdr_original_im, epsilon, mse_loss, alpha, r_weights=None):
    if fake.is_cuda:
        window = window.cuda(fake.get_device())
    window = window.type_as(fake)
    window = window / window.sum()
    mu1 = F.conv2d(fake, window, padding=5 // 2, groups=1)
    mu2 = F.conv2d(gamma_hdr, window, padding=5 // 2, groups=1)
    mu1_sq = mu1.pow(2)
    sigma1_sq = F.conv2d(fake * fake, window, padding=5 // 2, groups=1) - mu1_sq
    std1 = torch.pow(torch.max(sigma1_sq, torch.zeros_like(sigma1_sq)) + 1e-10, 0.5)
    return mse_loss(std1, alpha * mu2)


def std_loss_mu_gamma_mu_hdr(window, fake, gamma_hdr, hdr_original_im, epsilon, mse_loss, alpha, r_weights=None):
    if fake.is_cuda:
        window = window.cuda(fake.get_device())
    window = window.type_as(fake)
    window = window / window.sum()
    mu_fake = F.conv2d(fake, window, padding=5 // 2, groups=1)
    mu_gamma = F.conv2d(gamma_hdr, window, padding=5 // 2, groups=1)
    mu_hdr = F.conv2d(hdr_original_im, window, padding=5 // 2, groups=1)

    mu_fake_sq = mu_fake.pow(2)
    sigma1_sq = F.conv2d(fake * fake, window, padding=5 // 2, groups=1) - mu_fake_sq
    std1 = torch.pow(torch.max(sigma1_sq, torch.zeros_like(sigma1_sq)) + 1e-10, 0.5)

    mu_hdr_sq = mu_hdr.pow(2)
    sigma_hdr_sq = F.conv2d(hdr_original_im * hdr_original_im, window, padding=5 // 2, groups=1) - mu_hdr_sq
    std_hdr = torch.pow(torch.max(sigma_hdr_sq, torch.zeros_like(sigma_hdr_sq)) + 1e-10, 0.5)
    res = (std_hdr / (mu_hdr + 1e-10)) * mu_gamma
    return mse_loss(std1, alpha * res)


def std_loss_laplac(gaussian_kernel, laplacian_kernel, fake, epsilon, gamma_input):
    b, c, h, w = fake.shape
    ones = torch.ones(fake.shape)
    if fake.is_cuda:
        gaussian_kernel = gaussian_kernel.cuda(fake.get_device())
        laplacian_kernel = laplacian_kernel.cuda(fake.get_device())
        ones = ones.cuda(fake.get_device())
    gaussian_kernel = gaussian_kernel.type_as(fake)
    laplacian_kernel = laplacian_kernel.type_as(fake)
    laplacian_kernel = laplacian_kernel.repeat(c, 1, 1, 1)
    ones = ones.type_as(fake)
    mu1 = F.conv2d(fake, gaussian_kernel, padding=5 // 2, groups=1)
    gamma_input_gaussian = F.conv2d(gamma_input, gaussian_kernel, padding=5 // 2, groups=1)
    laplacian_res = F.conv2d(gamma_input_gaussian, laplacian_kernel, padding=5 // 2, stride=1, groups=c)
    # laplacian_res_max = laplacian_res.view(laplacian_res.shape[0], -1).max(dim=1)[0].reshape(laplacian_res.shape[0], 1, 1, 1)
    # laplacian_res = laplacian_res / laplacian_res_max
    laplacian_res[laplacian_res < 0] = 0
    # laplacian_res = ones / (laplacian_res + params.epsilon2)
    laplacian_res = laplacian_res.max() - (laplacian_res)
    laplacian_res = laplacian_res ** 2
    # laplacian_res = (laplacian_res - laplacian_res.min()) / (laplacian_res.max() - laplacian_res.min())
    print("laplacian_res max[%.4f] min[%.4f] mean[%.4f]" % (laplacian_res[1,0].max(), laplacian_res[1,0].min(), laplacian_res[1,0].mean()))
    import matplotlib.pyplot as plt
    plt.imshow(laplacian_res[1,0].numpy(), cmap='gray')
    plt.show()
    # compute std
    mu1_sq = mu1.pow(2)
    sigma1_sq = F.conv2d(fake * fake, gaussian_kernel, padding=5 // 2, groups=1) - mu1_sq
    std1 = torch.pow(torch.max(sigma1_sq, torch.zeros_like(sigma1_sq)) + 1e-10, 0.5)
    res = laplacian_res * (ones - (std1[0, 0] / (std1[0, 0] + epsilon)))
    return res.mean()


def mu_loss(window, fake, hdr_input, mse_loss, r_weights):
    if fake.is_cuda:
        window = window.cuda(fake.get_device())
    window = window.type_as(fake)
    window = window / window.sum()
    mu1 = F.conv2d(fake, window, padding=5 // 2, groups=1)
    mu2 = F.conv2d(hdr_input, window, padding=5 // 2, groups=1)
    return mse_loss(mu1, mu2.detach())


def mu_loss_bilateral(window, fake, hdr_input, mse_loss, r_weights, wind_size=5):
    if fake.is_cuda:
        window = window.cuda(fake.get_device())
    window = window.type_as(fake)
    window = window.reshape(1, wind_size * wind_size, 1, 1).contiguous()
    distance_gause = window.expand(1, -1, r_weights.shape[2], r_weights.shape[3])
    weights_map = distance_gause * r_weights
    weights_map_sum = torch.sum(weights_map, axis=1).unsqueeze(dim=1)

    fake_windows = get_im_as_windows(fake, wind_size)
    fake_windows = fake_windows.squeeze(dim=1)
    fake_windows = fake_windows.permute(0, 3, 1, 2)
    fake_bf = torch.sum(fake_windows * weights_map, axis=1).unsqueeze(dim=1) / weights_map_sum

    hdr_input_windows = get_im_as_windows(hdr_input, wind_size)
    hdr_input_windows = hdr_input_windows.squeeze(dim=1)
    hdr_input_windows = hdr_input_windows.permute(0, 3, 1, 2)
    hdr_input_bf = torch.sum(hdr_input_windows * weights_map, axis=1).unsqueeze(dim=1) / weights_map_sum
    return mse_loss(fake_bf, hdr_input_bf.detach())


def sig_loss(window, img1, epsilon, img2):
    ones = torch.ones(img1.shape)
    if img1.is_cuda:
        window = window.cuda(img1.get_device())
        ones = ones.cuda(img1.get_device())
    window = window.type_as(img1)
    ones = ones.type_as(img1)
    window = window / window.sum()
    mu1 = F.conv2d(img1, window, padding=5 // 2, groups=1)
    mu2 = F.conv2d(img2, window, padding=5 // 2, groups=1)
    mu1_mu2 = mu1 * mu2
    sigma12 = F.conv2d(img1 * img2, window, padding=5 // 2, groups=1) - mu1_mu2
    res = ones - (sigma12[0, 0] / (sigma12[0, 0] + epsilon))
    return res.mean()


# =======================================
# ========= Helper Functions ============
# =======================================
def gaussian(window_size, sigma):
    gauss = torch.Tensor([exp(-((x - window_size // 2) ** 2 / float(2 * sigma ** 2))) for x in range(window_size)])
    # return gauss / gauss.sum()
    return gauss

# def get_bilateral_filter(window_size)


def create_window(window_size, channel):
    window = torch.ones((1, channel, window_size, window_size))
    return window


def fix_shape(windows):
    windows = windows.permute(0, 4, 2, 3, 1)
    windows = windows.squeeze(dim=4)
    return windows


def get_window_and_set_device(wind_size, a, b):
    if a.dim() < 4:
        a = torch.unsqueeze(a, dim=0)
    if b.dim() < 4:
        b = torch.unsqueeze(b, dim=0)
    window = torch.ones((1, 1, wind_size, wind_size))
    window = window / window.sum()
    if a.is_cuda:
        window = window.cuda(a.get_device())
        if not b.is_cuda:
            b = b.cuda(a.get_device())
    b = b.type_as(a)
    window = window.type_as(a)
    return a, b, window


def get_im_as_windows(a, wind_size):
    m = nn.ZeroPad2d(wind_size // 2)
    a = m(a)
    windows = a.unfold(dimension=2, size=wind_size, step=1)
    windows = windows.unfold(dimension=3, size=wind_size, step=1)
    windows = windows.reshape(windows.shape[0], windows.shape[1],
                              windows.shape[2], windows.shape[3],
                              wind_size * wind_size)
    return windows


def get_mu(x, window, wind_size):
    mu = F.conv2d(x, window, padding=0, groups=1)
    mu = mu.unsqueeze(dim=4)
    mu = mu.expand(-1, -1, -1, -1, wind_size * wind_size)
    return mu


def get_std(windows, mu1, wind_size):
    x_minus_mu = windows - mu1
    x_minus_mu = x_minus_mu.squeeze(dim=1)
    x_minus_mu = x_minus_mu.permute(0, 3, 1, 2)
    wind_a = torch.ones((1, wind_size * wind_size, 1, 1))
    if windows.is_cuda:
        wind_a = wind_a.cuda(windows.get_device())
    wind_a = wind_a / wind_a.sum()
    mu_x_minus_mu_sq = F.conv2d(x_minus_mu * x_minus_mu, wind_a, padding=0, groups=1)
    std1 = torch.pow(torch.max(mu_x_minus_mu_sq, torch.zeros_like(mu_x_minus_mu_sq)) + params.epsilon, 0.5)
    std1 = std1.expand(-1, wind_size * wind_size, -1, -1)
    std1 = std1.permute(0, 2, 3, 1)
    std1 = std1.unsqueeze(dim=1)
    return std1


def get_gaussian_kernel(window_size, channel):
    _1D_window = gaussian(window_size, 1.5).unsqueeze(1)
    _2D_window = _1D_window.mm(_1D_window.t()).float().unsqueeze(0).unsqueeze(0)
    window = _2D_window.expand(channel, 1, window_size, window_size).contiguous()
    return window


def get_gaussian_kernel2(window_size, channel):
    sigma = 5
    _1D_window = gaussian(window_size, sigma).unsqueeze(1)
    _2D_window = _1D_window.mm(_1D_window.t()).float().unsqueeze(0).unsqueeze(0)
    window = _2D_window.expand(channel, 1, window_size, window_size).contiguous()
    return window


def get_laplacian_kernel(kernel_size):
    """Returns a 2D Laplacian kernel array."""
    kernel = torch.ones((kernel_size, kernel_size))
    mid = kernel_size // 2
    kernel[mid, mid] = 1 - kernel_size ** 2
    return kernel.double()


def get_radiometric_weights(gamma_input, wind_size):
    gamma_input = data_loader_util.crop_input_hdr_batch(gamma_input)
    sigma_r = 0.4
    m = nn.ZeroPad2d(5 // 2)
    radiometric_weights_arr = []
    for i in range(4):
        centers_gamma = gamma_input.expand(-1, wind_size * wind_size, -1, -1)
        a = m(gamma_input)
        windows = a.unfold(dimension=2, size=wind_size, step=1)
        windows = windows.unfold(dimension=3, size=wind_size, step=1)
        windows = windows.reshape(windows.shape[0], windows.shape[1],
                                  windows.shape[2], windows.shape[3],
                                  wind_size * wind_size)
        windows = windows.squeeze(dim=1)
        windows = windows.permute(0, 3, 1, 2)
        radiometric_dist = torch.abs(windows - centers_gamma)
        k = radiometric_dist ** 2 / (2 * sigma_r ** 2)
        radiometric_gaus = torch.exp(-k)
        radiometric_gaus = radiometric_gaus.type_as(gamma_input)
        radiometric_weights_arr.append(radiometric_gaus)
        gamma_input = F.interpolate(gamma_input, scale_factor=0.5, mode='bicubic', align_corners=False)
    return radiometric_weights_arr
