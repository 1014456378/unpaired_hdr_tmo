import numpy as np
import torch
# from __future__ import print_function
from torchvision.datasets import DatasetFolder
import utils.hdr_image_util as hdr_image_util
from utils import params
import utils.data_loader_util as data_loader_util
IMG_EXTENSIONS_local = ('.npy')


def npy_loader(path, addFrame, hdrMode, normalization, use_c3):
    """
    load npy files that contain the loaded HDR file, and binary image of windows centers.
    :param path: image path
    :return:
    """

    data = np.load(path, allow_pickle=True)
    input_im = data[()]["input_image"]
    color_im = data[()]["display_image"]
    # if addFrame and hdrMode:
    #     im = data_loader_util.add_frame_to_im(input_im)
    #     return im, color_im
    if not hdrMode:
        if normalization == "max_normalization":
            input_im = input_im / input_im.max()
        elif normalization == "bugy_max_normalization":
            input_im = input_im / 255
        elif normalization == "min_max_normalization":
            input_im = (input_im - input_im.min()) / (input_im.max() - input_im.min())
    if hdrMode:
        if addFrame:
            input_im = data_loader_util.add_frame_to_im(input_im)
        gray_original_im = hdr_image_util.to_gray_tensor(color_im)
        # if use_c3:
        gray_original_im_norm = gray_original_im / gray_original_im.max()
        return input_im, color_im, gray_original_im_norm, gray_original_im
    return input_im, color_im, input_im, input_im
    # if data.ndim == 2:
    #     data = data[:, :, None]
    # image_tensor = torch.from_numpy(data).float()
    # return image_tensor
    # return data
    # return data[()][params.image_key], data[()][params.window_image_key]


class ProcessedDatasetFolder(DatasetFolder):
    """
    A customized data loader, to load .npy file that contains a dict
    of numpy arrays that represents hdr_images and window_binary_images.
    """

    def __init__(self, root, addFrame, hdrMode, normalization, transform=None, target_transform=None,
                 loader=npy_loader, use_c3=False):
        super(ProcessedDatasetFolder, self).__init__(root, loader, IMG_EXTENSIONS_local,
                                                     transform=transform,
                                                     target_transform=target_transform)
        self.imgs = self.samples
        self.addFrame = addFrame
        self.hdrMode = hdrMode
        self.normalization = normalization
        self.use_c3 = use_c3

    def __getitem__(self, index):
        """
        Args:
            index (int): Index

        Returns:
            sample: {'hdr_image': im, 'binary_wind_image': binary_im}
        """
        path, target = self.samples[index]
        # if self.test_mode:
        # input_im, color_im = self.loader(path, self.test_mode)
        input_im, color_im, gray_original_norm, gray_original = self.loader(path, self.addFrame, self.hdrMode,
                                                        self.normalization, self.use_c3)
        return {"input_im": input_im, "color_im": color_im, "original_gray_norm": gray_original_norm, "original_gray": gray_original}
        # else:
        #     input_im = self.loader(path, self.test_mode)
        # image, binary_window = self.loader(path)
        # sample = {params.image_key: image, params.window_image_key: binary_window}
        # if self.transform:
        #     image = self.transform(image)
        # return input_im, target
