import torch
import torch.nn.functional as F
from utils import params, data_loader_util


# =======================================
# ============= Classes ===============
# =======================================
class StructLoss(torch.nn.Module):
    def __init__(self, pyramid_weight_list, window_size=5, pyramid_pow=False, use_c3=False,
                 struct_method="gamma_struct", crop_input=True,
                 final_shape_addition=0):
        super(StructLoss, self).__init__()
        self.window_size = window_size
        self.final_shape_addition = final_shape_addition
        self.crop_input = crop_input
        self.channel = 1
        self.window = create_window(window_size, self.channel)
        self.mse_loss = torch.nn.MSELoss()
        self.pyramid_weight_list = pyramid_weight_list
        self.pyramid_pow = pyramid_pow
        self.use_c3 = use_c3
        self.struct_method = struct_method

    def forward(self, fake, hdr_input_original_gray_norm, hdr_input, pyramid_weight_list):
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
        if self.crop_input:
            hdr_input = data_loader_util.crop_input_hdr_batch(hdr_input, self.final_shape_addition,
                                                              self.final_shape_addition)
        return our_custom_ssim_pyramid(fake, hdr_input, window, self.window_size, channel,
                                       pyramid_weight_list,
                                       self.mse_loss)


class SSIMLoss(torch.nn.Module):
    def __init__(self, pyramid_weight_list, window_size=5, pyramid_pow=False, use_c3=False,
                 struct_method="gamma_ssim", crop_input=True,
                 final_shape_addition=0):
        super(SSIMLoss, self).__init__()
        self.window_size = window_size
        self.final_shape_addition = final_shape_addition
        self.crop_input = crop_input
        self.channel = 1
        self.window = create_window(window_size, self.channel)
        self.mse_loss = torch.nn.MSELoss()
        self.pyramid_weight_list = pyramid_weight_list
        self.pyramid_pow = pyramid_pow
        self.use_c3 = use_c3
        self.struct_method = struct_method

    def forward(self, fake, hdr_input_original_gray_norm, hdr_input, pyramid_weight_list):
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
        if self.crop_input:
            hdr_input = data_loader_util.crop_input_hdr_batch(hdr_input, self.final_shape_addition,
                                                              self.final_shape_addition)
        return ssim_pyramid(fake, hdr_input, window, self.window_size, channel,
                                       pyramid_weight_list,
                                       self.mse_loss)
# =======================================
# ========== Loss Functions =============
# =======================================
def our_custom_ssim_pyramid(img1, img2, window, window_size, channel, pyramid_weight_list, mse_loss):
    ssim_loss_list = []
    for i in range(len(pyramid_weight_list)):
        ssim_loss_list.append(pyramid_weight_list[i] * our_custom_ssim(img1, img2, window, window_size,
                                                                       channel, mse_loss))

        img1 = F.interpolate(img1, scale_factor=0.5, mode='bicubic', align_corners=False)
        img2 = F.interpolate(img2, scale_factor=0.5, mode='bicubic', align_corners=False)
    return torch.sum(torch.stack(ssim_loss_list))


def our_custom_ssim(img1, img2, window, window_size, channel, mse_loss):
    """

    :param img1: fake
    :param img2: input gamma
    :param window:
    :param window_size:
    :param channel:
    :param mse_loss:
    :param use_c3:
    :param apply_sig_mu_ssim:
    :param cur_weights:
    :return:
    """
    window = window / window.sum()
    mu1 = F.conv2d(img1, window, groups=channel)
    mu2 = F.conv2d(img2, window,  groups=channel)

    mu1_sq = mu1.pow(2)
    mu2_sq = mu2.pow(2)

    sigma1_sq = F.conv2d(img1 * img1, window, groups=1) - mu1_sq
    sigma2_sq = F.conv2d(img2 * img2, window, groups=1) - mu2_sq

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
    img2 = img2 / (std2 + params.epsilon2)
    return mse_loss(img1, img2)

def ssim_pyramid(img1, img2, window, window_size, channel, pyramid_weight_list, mse_loss):
    ssim_loss_list = []
    for i in range(len(pyramid_weight_list)):
        ssim_loss_list.append(pyramid_weight_list[i] * ssim_loss(img1, img2, window, window_size,
                                                                       channel, mse_loss))

        img1 = F.interpolate(img1, scale_factor=0.5, mode='bicubic', align_corners=False)
        img2 = F.interpolate(img2, scale_factor=0.5, mode='bicubic', align_corners=False)
    return torch.sum(torch.stack(ssim_loss_list))


def ssim_loss(img1, img2, window, window_size, channel, mse_loss):
    window = window / window.sum()
    mu1 = F.conv2d(img1, window, padding = window_size//2, groups=channel)
    mu2 = F.conv2d(img2, window,  padding = window_size//2, groups=channel)

    mu1_sq = mu1.pow(2)
    mu2_sq = mu2.pow(2)

    mu1_mu2 = mu1 * mu2

    sigma1_sq = F.conv2d(img1 * img1, window, padding = window_size//2,groups=1) - mu1_sq
    sigma2_sq = F.conv2d(img2 * img2, window, padding = window_size//2,groups=1) - mu2_sq
    sigma12 = F.conv2d(img1 * img2, window, padding=window_size // 2, groups=channel) - mu1_mu2

    C1 = 0.01 ** 2
    C2 = 0.03 ** 2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))
    return ssim_map.mean()

# =======================================
# ========= Helper Functions ============
# =======================================
def create_window(window_size, channel):
    window = torch.ones((1, channel, window_size, window_size))
    return window / window.sum()


def get_im_as_windows(a, wind_size):
    windows = a.unfold(dimension=2, size=wind_size, step=1)
    windows = windows.unfold(dimension=3, size=wind_size, step=1)
    windows = windows.reshape(windows.shape[0], windows.shape[1],
                              windows.shape[2], windows.shape[3],
                              wind_size * wind_size)
    return windows
